from datetime import timedelta

from django.test.utils import override_settings
from django.utils import timezone

import pytest

from baserow.contrib.database.data_import.constants import (
    IMPORT_MODE_APPEND,
    IMPORT_MODE_REPLACE,
    IMPORT_MODE_UPSERT,
    IMPORT_RECORD_STATUS_FAILED,
    IMPORT_RECORD_STATUS_FINISHED,
    IMPORT_RECORD_STATUS_RUNNING,
)
from baserow.contrib.database.data_import.exceptions import ImportSchemaMismatch
from baserow.contrib.database.data_import.handler import (
    TableImportRecordHandler,
    get_importable_fields,
    payload_digest,
    validate_strict_mapping,
)
from baserow.contrib.database.data_import.models import TableImportRecord
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED, JOB_FINISHED


@pytest.fixture
def table_with_two_fields(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    return user, table, [name, amount]


@pytest.mark.django_db
def test_get_importable_fields_excludes_password_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_password_field(table=table, name="Secret")
    data_fixture.create_formula_field(table=table, name="Derived", formula="'x'")

    # A password field is writable but can never round-trip through a spreadsheet,
    # and a formula field is read only, so neither may be required by a strict import.
    assert [field.id for field in get_importable_fields(table)] == [name.id]


@pytest.mark.django_db
def test_validate_strict_mapping_accepts_a_total_mapping(table_with_two_fields):
    _, table, fields = table_with_two_fields

    validate_strict_mapping(
        table,
        IMPORT_MODE_UPSERT,
        ["Name", "Amount"],
        [fields[0].id, fields[1].id],
    )


@pytest.mark.django_db
def test_validate_strict_mapping_is_order_independent(table_with_two_fields):
    _, table, fields = table_with_two_fields

    validate_strict_mapping(
        table,
        IMPORT_MODE_REPLACE,
        ["Amount", "Name"],
        [fields[1].id, fields[0].id],
    )


@pytest.mark.django_db
def test_validate_strict_mapping_rejects_an_unmapped_file_column(
    table_with_two_fields,
):
    _, table, fields = table_with_two_fields

    with pytest.raises(ImportSchemaMismatch) as exc:
        validate_strict_mapping(
            table,
            IMPORT_MODE_UPSERT,
            ["Name", "Amount", "Extra"],
            [fields[0].id, fields[1].id, 0],
        )

    assert exc.value.unmapped_file_columns == ["Extra"]
    assert exc.value.uncovered_fields == []


@pytest.mark.django_db
def test_validate_strict_mapping_rejects_an_uncovered_field(table_with_two_fields):
    _, table, fields = table_with_two_fields

    with pytest.raises(ImportSchemaMismatch) as exc:
        validate_strict_mapping(table, IMPORT_MODE_REPLACE, ["Name"], [fields[0].id])

    assert exc.value.uncovered_fields == ["Amount"]
    assert exc.value.unmapped_file_columns == []


@pytest.mark.django_db
def test_validate_strict_mapping_rejects_a_duplicated_field(table_with_two_fields):
    _, table, fields = table_with_two_fields

    with pytest.raises(ImportSchemaMismatch) as exc:
        validate_strict_mapping(
            table,
            IMPORT_MODE_UPSERT,
            ["Name", "Name again"],
            [fields[0].id, fields[0].id],
        )

    assert exc.value.duplicate_fields == ["Name"]
    assert exc.value.uncovered_fields == ["Amount"]


@pytest.mark.django_db
def test_validate_strict_mapping_rejects_a_mismatched_length(table_with_two_fields):
    _, table, fields = table_with_two_fields

    with pytest.raises(ImportSchemaMismatch):
        validate_strict_mapping(
            table, IMPORT_MODE_UPSERT, ["Name", "Amount"], [fields[0].id]
        )


@pytest.mark.django_db
def test_validate_strict_mapping_leaves_append_alone(table_with_two_fields):
    _, table, fields = table_with_two_fields

    # Append keeps the lenient mapping it has always had: skipping a column and
    # leaving a field uncovered are both allowed.
    validate_strict_mapping(table, IMPORT_MODE_APPEND, ["Name", "Extra"], [0, 0])


def test_payload_digest_is_stable_and_content_addressed():
    digest_a, size_a = payload_digest([["a", 1], ["b", 2]])
    digest_b, size_b = payload_digest([["a", 1], ["b", 2]])
    digest_c, _ = payload_digest([["a", 1], ["b", 3]])

    assert digest_a == digest_b
    assert size_a == size_b > 0
    assert digest_a != digest_c


@pytest.mark.django_db
def test_create_and_finish_record(table_with_two_fields):
    user, table, fields = table_with_two_fields
    handler = TableImportRecordHandler()

    record = handler.create_record(
        user,
        table,
        IMPORT_MODE_UPSERT,
        [["a", 1], ["b", 2]],
        configuration={
            "file_header": ["Name", "Amount"],
            "field_mapping": [fields[0].id, fields[1].id],
            "upsert_fields": [fields[0].id],
        },
    )

    assert record.status == IMPORT_RECORD_STATUS_RUNNING
    assert record.rows_in_file == 2
    assert record.workspace_name == table.database.workspace.name
    assert record.table_name == table.name
    assert record.user_email == user.email
    assert record.field_mapping == [
        {"column": "Name", "field_id": fields[0].id},
        {"column": "Amount", "field_id": fields[1].id},
    ]
    assert record.upsert_field_ids == [fields[0].id]
    assert len(record.payload_sha256) == 64

    handler.finish_record(
        record,
        rows_created=1,
        rows_updated=1,
        report={"failing_rows": {"3": {"non_field_errors": ["nope"]}}},
    )

    record.refresh_from_db()
    assert record.status == IMPORT_RECORD_STATUS_FINISHED
    assert (record.rows_created, record.rows_updated, record.rows_failed) == (1, 1, 1)
    assert record.finished_on is not None


@pytest.mark.django_db
def test_record_survives_the_job_being_cleaned_up(
    data_fixture, table_with_two_fields, patch_filefield_storage
):
    user, table, _ = table_with_two_fields
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table
        )
    record = TableImportRecordHandler().create_record(
        user, table, IMPORT_MODE_APPEND, [["a", 1]], job=job
    )

    job.delete()

    record.refresh_from_db()
    assert record.job_id is None
    assert record.table_id == table.id
    assert record.table_name == table.name


@pytest.mark.django_db
@pytest.mark.parametrize("job_state", [JOB_FAILED, JOB_CANCELLED, JOB_FINISHED])
def test_reconcile_closes_records_left_running(
    data_fixture, table_with_two_fields, patch_filefield_storage, job_state
):
    user, table, _ = table_with_two_fields
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table, state=job_state
        )
    record = TableImportRecordHandler().create_record(
        user, table, IMPORT_MODE_REPLACE, [["a", 1]], job=job
    )

    assert TableImportRecordHandler().reconcile_stale_records() == 1

    record.refresh_from_db()
    assert record.status == IMPORT_RECORD_STATUS_FAILED
    assert record.error != ""


@pytest.mark.django_db
def test_reconcile_leaves_a_finished_record_alone(
    data_fixture, table_with_two_fields, patch_filefield_storage
):
    user, table, _ = table_with_two_fields
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table, state=JOB_FINISHED
        )
    record = TableImportRecordHandler().create_record(
        user, table, IMPORT_MODE_APPEND, [["a", 1]], job=job
    )
    TableImportRecordHandler().finish_record(record, rows_created=1)

    assert TableImportRecordHandler().reconcile_stale_records() == 0

    record.refresh_from_db()
    assert record.status == IMPORT_RECORD_STATUS_FINISHED


@pytest.mark.django_db
@override_settings(BASEROW_TABLE_IMPORT_RECORD_RETENTION_DAYS=0)
def test_records_are_kept_forever_by_default(table_with_two_fields):
    user, table, _ = table_with_two_fields
    TableImportRecordHandler().create_record(
        user, table, IMPORT_MODE_APPEND, [["a", 1]]
    )
    TableImportRecord.objects.update(started_on=timezone.now() - timedelta(days=3650))

    assert TableImportRecordHandler().delete_expired_records() == 0
    assert TableImportRecord.objects.count() == 1


@pytest.mark.django_db
@override_settings(BASEROW_TABLE_IMPORT_RECORD_RETENTION_DAYS=30)
def test_records_past_their_retention_are_deleted(table_with_two_fields):
    user, table, _ = table_with_two_fields
    TableImportRecordHandler().create_record(
        user, table, IMPORT_MODE_APPEND, [["a", 1]]
    )
    kept = TableImportRecordHandler().create_record(
        user, table, IMPORT_MODE_APPEND, [["b", 2]]
    )
    TableImportRecord.objects.exclude(id=kept.id).update(
        started_on=timezone.now() - timedelta(days=31)
    )

    assert TableImportRecordHandler().delete_expired_records() == 1
    assert list(TableImportRecord.objects.values_list("id", flat=True)) == [kept.id]
