import pytest
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)

from baserow.contrib.database.data_import.constants import (
    IMPORT_MODE_APPEND,
    IMPORT_MODE_REPLACE,
    IMPORT_MODE_UPSERT,
)
from baserow.contrib.database.data_import.models import TableImportRecord
from baserow.contrib.database.table.operations import (
    ImportRowsDatabaseTableOperationType,
    ReadDatabaseTableOperationType,
    UpsertRowsDatabaseTableOperationType,
)
from baserow.core.models import Operation
from baserow.core.roles.models import Role


@pytest.fixture
def import_table(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    return {
        "user": user,
        "token": token,
        "workspace": workspace,
        "table": table,
        "url": reverse(
            "api:database:tables:import_async", kwargs={"table_id": table.id}
        ),
        "configuration": {
            "file_header": ["Name", "Amount"],
            "field_mapping": [name.id, amount.id],
        },
        "name": name,
        "amount": amount,
    }


@pytest.mark.django_db
def test_import_defaults_to_append(api_client, import_table):
    response = api_client.post(
        import_table["url"],
        HTTP_AUTHORIZATION=f"JWT {import_table['token']}",
        data={"data": [["a", 1]]},
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["mode"] == IMPORT_MODE_APPEND


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [IMPORT_MODE_UPSERT, IMPORT_MODE_REPLACE])
def test_strict_modes_require_the_file_mapping(api_client, import_table, mode):
    response = api_client.post(
        import_table["url"],
        HTTP_AUTHORIZATION=f"JWT {import_table['token']}",
        data={"data": [["a", 1]], "mode": mode},
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_strict_mode_rejects_an_unmapped_column(api_client, import_table):
    response = api_client.post(
        import_table["url"],
        HTTP_AUTHORIZATION=f"JWT {import_table['token']}",
        data={
            "data": [["a", 1, "x"]],
            "mode": IMPORT_MODE_REPLACE,
            "configuration": {
                "file_header": ["Name", "Amount", "Extra"],
                "field_mapping": [
                    import_table["name"].id,
                    import_table["amount"].id,
                    0,
                ],
            },
        },
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"] == "ERROR_TABLE_IMPORT_SCHEMA_MISMATCH"
    assert "Extra" in body["detail"]
    # Nothing was queued: the request is refused before a job exists.
    assert TableImportRecord.objects.count() == 0


@pytest.mark.django_db
def test_strict_mode_rejects_an_uncovered_field(api_client, import_table):
    response = api_client.post(
        import_table["url"],
        HTTP_AUTHORIZATION=f"JWT {import_table['token']}",
        data={
            "data": [["a"]],
            "mode": IMPORT_MODE_UPSERT,
            "configuration": {
                "file_header": ["Name"],
                "field_mapping": [import_table["name"].id],
            },
        },
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"] == "ERROR_TABLE_IMPORT_SCHEMA_MISMATCH"
    assert "Amount" in body["detail"]


@pytest.mark.django_db
def test_strict_mode_accepts_a_total_mapping(api_client, import_table):
    response = api_client.post(
        import_table["url"],
        HTTP_AUTHORIZATION=f"JWT {import_table['token']}",
        data={
            "data": [["a", 1]],
            "mode": IMPORT_MODE_REPLACE,
            "configuration": import_table["configuration"],
        },
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["mode"] == IMPORT_MODE_REPLACE
    # The record is opened up front so a crashed worker still leaves a trace.
    record = TableImportRecord.objects.get()
    assert record.mode == IMPORT_MODE_REPLACE
    assert record.rows_in_file == 1


@pytest.mark.django_db
def test_a_role_can_grant_append_without_replace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()
    role = Role.objects.create(workspace=workspace, name="Importer")
    role.operations.set(
        Operation.objects.filter(
            name__in=[
                ReadDatabaseTableOperationType.type,
                ImportRowsDatabaseTableOperationType.type,
            ]
        )
    )
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="MEMBER", role=role
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    url = reverse("api:database:tables:import_async", kwargs={"table_id": table.id})
    configuration = {"file_header": ["Name"], "field_mapping": [name.id]}

    append = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"data": [["a"]], "mode": IMPORT_MODE_APPEND},
        format="json",
    )
    assert append.status_code == HTTP_200_OK

    replace = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={
            "data": [["a"]],
            "mode": IMPORT_MODE_REPLACE,
            "configuration": configuration,
        },
        format="json",
    )
    assert replace.status_code == HTTP_401_UNAUTHORIZED
    assert replace.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_a_role_granting_upsert_allows_it(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()
    role = Role.objects.create(workspace=workspace, name="Upserter")
    role.operations.set(
        Operation.objects.filter(
            name__in=[
                ReadDatabaseTableOperationType.type,
                UpsertRowsDatabaseTableOperationType.type,
            ]
        )
    )
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="MEMBER", role=role
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    url = reverse("api:database:tables:import_async", kwargs={"table_id": table.id})

    response = api_client.post(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={
            "data": [["a"]],
            "mode": IMPORT_MODE_UPSERT,
            "configuration": {
                "file_header": ["Name"],
                "field_mapping": [name.id],
                "upsert_fields": [name.id],
                "upsert_values": [["a"]],
            },
        },
        format="json",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_import_records_are_listed_for_the_table(api_client, import_table):
    api_client.post(
        import_table["url"],
        HTTP_AUTHORIZATION=f"JWT {import_table['token']}",
        data={
            "data": [["a", 1]],
            "mode": IMPORT_MODE_REPLACE,
            "configuration": import_table["configuration"],
            "original_file_name": "contacts.xlsx",
        },
        format="json",
    )

    url = reverse(
        "api:database:tables:import_records",
        kwargs={"table_id": import_table["table"].id},
    )
    response = api_client.get(
        url, HTTP_AUTHORIZATION=f"JWT {import_table['token']}", format="json"
    )

    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["mode"] == IMPORT_MODE_REPLACE
    assert results[0]["original_file_name"] == "contacts.xlsx"
    assert results[0]["user"]["email"] == import_table["user"].email
    assert len(results[0]["payload_sha256"]) == 64
