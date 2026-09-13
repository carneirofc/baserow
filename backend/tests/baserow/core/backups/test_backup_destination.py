import hashlib
import json

from django.core.management import call_command
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from baserow.core.backups.destination import BackupDestinationHandler
from baserow.core.backups.exceptions import (
    RemoteBackupCorrupted,
    RemoteBackupTrustNotAllowed,
)
from baserow.core.backups.handler import BackupHandler
from baserow.core.backups.schedule_handler import BackupScheduleHandler
from baserow.core.data_destinations.config import parse_data_destinations_env
from baserow.core.data_destinations.exceptions import InvalidDataDestinationKey
from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportResourceUntrustedSignature,
)
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import Application, ImportExportTrustedSource


@pytest.fixture
def backup_destination(settings, tmp_path):
    root = tmp_path / "offsite"
    settings.BASEROW_DATA_DESTINATIONS = parse_data_destinations_env(
        json.dumps(
            [
                {
                    "name": "offsite",
                    "type": "filesystem",
                    "root": str(root),
                    "purposes": ["backup"],
                    "allow_trust_public_key": True,
                }
            ]
        )
    )
    return root


def _backup(data_fixture, user, name="Sales"):
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace, name=name)
    job = BackupHandler().start_backup(
        user, workspace.id, destination="offsite", sync=True
    )
    assert job.state == JOB_FINISHED, job.error
    return workspace, job


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_backup_is_uploaded_with_a_sidecar(
    data_fixture, backup_destination, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace, job = _backup(data_fixture, user)

    assert job.remote_key.startswith(f"backups/workspace={workspace.id}/")
    archive = backup_destination / job.remote_key
    sidecar = json.loads((backup_destination / f"{job.remote_key}.json").read_text())

    assert sidecar["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert sidecar["workspace"] == {"id": workspace.id, "name": workspace.name}
    assert [application["name"] for application in sidecar["applications"]] == ["Sales"]
    assert sidecar["public_key_pem"]
    assert sidecar["instance_id"] == CoreHandler().get_settings().instance_id

    backups = BackupDestinationHandler().list_remote_backups(
        user, workspace.id, "offsite"
    )
    assert [backup["key"] for backup in backups] == [job.remote_key]


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_remote_backup_is_restored_into_another_workspace(
    data_fixture, backup_destination, use_tmp_media_root
):
    user = data_fixture.create_user()
    _, job = _backup(data_fixture, user)
    target = data_fixture.create_workspace(user=user)

    import_job = BackupDestinationHandler().restore_remote_backup(
        user, target.id, "offsite", job.remote_key, sync=True
    )

    assert import_job.state == JOB_FINISHED, import_job.error
    assert Application.objects.filter(workspace=target, name="Sales").exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_backup_of_another_instance_needs_its_key_to_be_trusted(
    data_fixture, backup_destination, use_tmp_media_root
):
    member = data_fixture.create_user()
    staff = data_fixture.create_user(is_staff=True)
    _, job = _backup(data_fixture, staff)
    target = data_fixture.create_workspace(members=[member, staff])

    # Pretend the backup was made elsewhere: this instance no longer knows the key.
    ImportExportTrustedSource.objects.all().delete()
    settings = CoreHandler().get_settings()
    settings.verify_import_signature = True
    settings.save()

    handler = BackupDestinationHandler()

    with pytest.raises(ImportExportResourceUntrustedSignature):
        handler.restore_remote_backup(
            staff, target.id, "offsite", job.remote_key, sync=True
        )

    with pytest.raises(RemoteBackupTrustNotAllowed):
        handler.restore_remote_backup(
            member, target.id, "offsite", job.remote_key, trust_public_key=True
        )

    import_job = handler.restore_remote_backup(
        staff, target.id, "offsite", job.remote_key, trust_public_key=True, sync=True
    )

    assert import_job.state == JOB_FINISHED, import_job.error
    assert ImportExportTrustedSource.objects.filter(
        name__startswith="destination:offsite:"
    ).exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_tampered_remote_backup_is_refused(
    data_fixture, backup_destination, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace, job = _backup(data_fixture, user)
    archive = backup_destination / job.remote_key
    archive.write_bytes(archive.read_bytes() + b"tampered")

    with pytest.raises(RemoteBackupCorrupted):
        BackupDestinationHandler().restore_remote_backup(
            user, workspace.id, "offsite", job.remote_key
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "key", ["backups/../../etc/passwd.zip", "elsewhere/archive.zip", "backups/a.json"]
)
def test_restore_only_accepts_backup_archive_keys(
    data_fixture, backup_destination, key
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(InvalidDataDestinationKey):
        BackupDestinationHandler().restore_remote_backup(
            user, workspace.id, "offsite", key
        )


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_remote_retention_keeps_the_newest_backups_of_the_schedule(
    data_fixture,
    backup_destination,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)
    schedule = data_fixture.create_backup_schedule(
        user=user, workspace=workspace, destination="offsite", keep_last=1
    )
    handler = BackupScheduleHandler()

    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True):
            handler.run_schedule(schedule)

    destination_handler = BackupDestinationHandler()
    backups = destination_handler.list_backups("offsite", workspace.id)
    assert len(backups) == 2
    assert {backup["schedule_id"] for backup in backups} == {schedule.id}

    assert destination_handler.apply_remote_retention(schedule) == 1

    remaining = destination_handler.list_backups("offsite", workspace.id)
    assert [backup["key"] for backup in remaining] == [backups[0]["key"]]
    assert not (backup_destination / backups[1]["key"]).exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_list_remote_backups_endpoint(
    api_client, data_fixture, backup_destination, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace, job = _backup(data_fixture, user)

    response = api_client.get(
        reverse(
            "api:backups:remote_list",
            kwargs={"destination": "offsite", "workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    [backup] = response.json()["results"]
    assert backup["key"] == job.remote_key
    assert backup["applications"][0]["name"] == "Sales"

    response = api_client.get(
        reverse(
            "api:backups:remote_list",
            kwargs={"destination": "missing", "workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DATA_DESTINATION_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_backup_and_restore_management_commands(
    data_fixture, backup_destination, use_tmp_media_root, capsys
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace, name="Stock")
    target = data_fixture.create_workspace(user=user)

    call_command(
        "backup_to_destination",
        str(workspace.id),
        "--destination",
        "offsite",
        "--user-email",
        user.email,
    )
    call_command(
        "list_destination_backups",
        "--destination",
        "offsite",
        "--workspace-id",
        str(workspace.id),
    )
    listed = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    assert len(listed) == 1

    call_command(
        "restore_from_destination",
        "--destination",
        "offsite",
        "--key",
        listed[0]["key"],
        "--workspace-id",
        str(target.id),
        "--user-email",
        user.email,
    )

    assert Application.objects.filter(workspace=target, name="Stock").exists()
