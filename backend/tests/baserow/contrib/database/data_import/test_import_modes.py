from django.test.utils import override_settings

import pytest

from baserow.contrib.database.data_import.constants import (
    IMPORT_MODE_APPEND,
    IMPORT_MODE_REPLACE,
    IMPORT_MODE_UPSERT,
    IMPORT_RECORD_STATUS_FINISHED,
)
from baserow.contrib.database.data_import.models import TableImportRecord
from baserow.contrib.database.rows.actions import (
    ReplaceRowsFromFileActionType,
    UpsertRowsFromFileActionType,
)
from baserow.contrib.database.rows.models import RowHistory
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.trash.handler import TrashHandler


@pytest.fixture
def contacts_table(data_fixture):
    """
    A two field table with three rows, and the mapping a strict import needs.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")

    model = table.get_model()
    rows = [
        model.objects.create(**{name.db_column: "Ada", amount.db_column: 1}),
        model.objects.create(**{name.db_column: "Grace", amount.db_column: 2}),
        model.objects.create(**{name.db_column: "Linus", amount.db_column: 3}),
    ]
    return {
        "user": user,
        "table": table,
        "name": name,
        "amount": amount,
        "rows": rows,
        "configuration": {
            "file_header": ["Name", "Amount"],
            "field_mapping": [name.id, amount.id],
        },
    }


def run_import(user, table, mode, data, configuration, patch_filefield_storage):
    with patch_filefield_storage():
        job = JobHandler().create_and_start_job(
            user,
            "file_import",
            sync=True,
            data=data,
            table=table,
            database=table.database,
            mode=mode,
            configuration=configuration,
            importer_type="excel",
            original_file_name="contacts.xlsx",
        )
    job.refresh_from_db()
    return job


def field_signature(table):
    return sorted(
        (field.id, field.name, field.get_type().type) for field in table.field_set.all()
    )


def row_values(table, name_field, amount_field):
    model = table.get_model()
    return sorted(
        (getattr(row, name_field.db_column), getattr(row, amount_field.db_column))
        for row in model.objects.all()
    )


@pytest.mark.django_db(transaction=True)
def test_append_mode_keeps_the_existing_rows(contacts_table, patch_filefield_storage):
    ctx = contacts_table
    before = field_signature(ctx["table"])

    job = run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_APPEND,
        [["Ada", 9]],
        ctx["configuration"],
        patch_filefield_storage,
    )

    assert job.state == JOB_FINISHED
    assert len(row_values(ctx["table"], ctx["name"], ctx["amount"])) == 4
    assert field_signature(ctx["table"]) == before


@pytest.mark.django_db(transaction=True)
def test_upsert_mode_updates_matched_rows_and_inserts_the_rest(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table
    before = field_signature(ctx["table"])
    configuration = {
        **ctx["configuration"],
        "upsert_fields": [ctx["name"].id],
        "upsert_values": [["Ada"], ["Margaret"]],
    }

    job = run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_UPSERT,
        [["Ada", 42], ["Margaret", 7]],
        configuration,
        patch_filefield_storage,
    )

    assert job.state == JOB_FINISHED
    assert row_values(ctx["table"], ctx["name"], ctx["amount"]) == [
        ("Ada", 42),
        ("Grace", 2),
        ("Linus", 3),
        ("Margaret", 7),
    ]
    # The table's fields are untouched: only cell values changed.
    assert field_signature(ctx["table"]) == before

    record = TableImportRecord.objects.get(table=ctx["table"])
    assert record.status == IMPORT_RECORD_STATUS_FINISHED
    assert record.mode == IMPORT_MODE_UPSERT
    assert record.rows_updated == 1
    assert record.rows_created == 1
    assert record.rows_deleted == 0
    assert record.original_file_name == "contacts.xlsx"
    assert record.row_history_truncated is False


@pytest.mark.django_db(transaction=True)
def test_replace_mode_swaps_the_contents_and_keeps_the_old_rows_in_the_trash(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table
    before = field_signature(ctx["table"])

    job = run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_REPLACE,
        [["Margaret", 7], ["Katherine", 8]],
        ctx["configuration"],
        patch_filefield_storage,
    )

    assert job.state == JOB_FINISHED
    assert row_values(ctx["table"], ctx["name"], ctx["amount"]) == [
        ("Katherine", 8),
        ("Margaret", 7),
    ]
    assert field_signature(ctx["table"]) == before

    record = TableImportRecord.objects.get(table=ctx["table"])
    assert record.mode == IMPORT_MODE_REPLACE
    assert record.rows_deleted == 3
    assert record.rows_created == 2
    assert record.trashed_rows_entry_id is not None

    # The previous contents are recoverable, which is what makes a replace safe.
    TrashHandler.restore_item(
        ctx["user"],
        "rows",
        record.trashed_rows_entry_id,
        parent_trash_item_id=ctx["table"].id,
    )
    assert len(row_values(ctx["table"], ctx["name"], ctx["amount"])) == 5


@pytest.mark.django_db(transaction=True)
def test_upsert_writes_row_history_with_before_and_after_values(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table
    configuration = {
        **ctx["configuration"],
        "upsert_fields": [ctx["name"].id],
        "upsert_values": [["Ada"]],
    }

    run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_UPSERT,
        [["Ada", 42]],
        configuration,
        patch_filefield_storage,
    )

    entry = RowHistory.objects.get(
        table=ctx["table"], action_type=UpsertRowsFromFileActionType.type
    )
    assert entry.row_id == ctx["rows"][0].id
    assert entry.field_names == [ctx["amount"].db_column]
    assert str(entry.before_values[ctx["amount"].db_column]) == "1"
    assert str(entry.after_values[ctx["amount"].db_column]) == "42"


@pytest.mark.django_db(transaction=True)
def test_replace_writes_row_history_for_removed_and_added_rows(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table

    run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_REPLACE,
        [["Margaret", 7]],
        ctx["configuration"],
        patch_filefield_storage,
    )

    entries = RowHistory.objects.filter(
        table=ctx["table"], action_type=ReplaceRowsFromFileActionType.type
    )
    removed = {
        entry.row_id
        for entry in entries
        if entry.after_values.get(ctx["name"].db_column) is None
    }
    assert removed == {row.id for row in ctx["rows"]}
    assert entries.count() == 4


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_MAX_ROW_HISTORY_ENTRIES_PER_IMPORT=2)
def test_row_history_is_capped_and_the_record_says_so(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table

    run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_REPLACE,
        [["Margaret", 7], ["Katherine", 8]],
        ctx["configuration"],
        patch_filefield_storage,
    )

    assert (
        RowHistory.objects.filter(
            table=ctx["table"], action_type=ReplaceRowsFromFileActionType.type
        ).count()
        == 2
    )
    record = TableImportRecord.objects.get(table=ctx["table"])
    assert record.row_history_truncated is True
    # The summary counters stay complete even when the per-row detail is capped.
    assert record.rows_deleted == 3
    assert record.rows_created == 2


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_MAX_ROW_HISTORY_ENTRIES_PER_IMPORT=1)
def test_a_capped_upsert_still_counts_every_updated_row(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table
    configuration = {
        **ctx["configuration"],
        "upsert_fields": [ctx["name"].id],
        "upsert_values": [["Ada"], ["Grace"], ["Linus"]],
    }

    run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_UPSERT,
        [["Ada", 10], ["Grace", 20], ["Linus", 30]],
        configuration,
        patch_filefield_storage,
    )

    record = TableImportRecord.objects.get(table=ctx["table"])
    assert record.rows_updated == 3
    assert record.rows_created == 0
    assert record.row_history_truncated is True
    assert (
        RowHistory.objects.filter(
            table=ctx["table"], action_type=UpsertRowsFromFileActionType.type
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_ROW_HISTORY_RETENTION_DAYS=0)
def test_no_row_history_is_written_when_it_is_disabled(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table

    run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_REPLACE,
        [["Margaret", 7]],
        ctx["configuration"],
        patch_filefield_storage,
    )

    assert RowHistory.objects.filter(table=ctx["table"]).count() == 0
    assert TableImportRecord.objects.get(table=ctx["table"]).rows_deleted == 3


@pytest.mark.django_db(transaction=True)
def test_a_strict_mode_import_with_a_bad_mapping_fails_the_job(
    contacts_table, patch_filefield_storage
):
    ctx = contacts_table

    job = run_import(
        ctx["user"],
        ctx["table"],
        IMPORT_MODE_REPLACE,
        [["Margaret"]],
        {"file_header": ["Name"], "field_mapping": [ctx["name"].id]},
        patch_filefield_storage,
    )

    assert job.state == "failed"
    # Nothing was written: the check runs before any row is touched.
    assert len(row_values(ctx["table"], ctx["name"], ctx["amount"])) == 3
