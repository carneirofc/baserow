from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)

from baserow.core.backups.exceptions import InvalidBackupScheduleCron
from baserow.core.backups.models import BackupSchedule
from baserow.core.backups.schedule_handler import BackupScheduleHandler
from baserow.core.backups.tasks import run_due_backup_schedules
from baserow.core.models import ExportApplicationsJob, ImportExportResource


def utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


@pytest.mark.parametrize(
    "cron,after,expected",
    [
        # Every night at 03:00.
        ("0 3 * * *", utc(2026, 1, 1, 0, 0), utc(2026, 1, 1, 3, 0)),
        ("0 3 * * *", utc(2026, 1, 1, 3, 0), utc(2026, 1, 2, 3, 0)),
        ("0 3 * * *", utc(2026, 1, 1, 4, 0), utc(2026, 1, 2, 3, 0)),
        # Every 15 minutes.
        ("*/15 * * * *", utc(2026, 1, 1, 9, 7), utc(2026, 1, 1, 9, 15)),
        ("*/15 * * * *", utc(2026, 1, 1, 9, 45), utc(2026, 1, 1, 10, 0)),
        # Only on the first of the month.
        ("30 2 1 * *", utc(2026, 1, 5, 0, 0), utc(2026, 2, 1, 2, 30)),
        # Only on Mondays, cron counts weekdays from Sunday.
        ("0 6 * * 1", utc(2026, 1, 1, 0, 0), utc(2026, 1, 5, 6, 0)),
        # Only in June.
        ("0 0 1 6 *", utc(2026, 7, 1, 0, 0), utc(2027, 6, 1, 0, 0)),
    ],
)
def test_compute_next_run_on(cron, after, expected):
    assert BackupScheduleHandler().compute_next_run_on(cron, "UTC", after) == expected


def test_compute_next_run_on_respects_the_timezone():
    handler = BackupScheduleHandler()

    # 03:00 in Sao Paulo (UTC-3) is 06:00 UTC.
    assert handler.compute_next_run_on(
        "0 3 * * *", "America/Sao_Paulo", utc(2026, 1, 1, 0, 0)
    ) == utc(2026, 1, 1, 6, 0)


def test_compute_next_run_on_is_always_in_the_future():
    handler = BackupScheduleHandler()
    moment = utc(2026, 1, 1, 3, 0)

    # Asking from exactly the due moment must move on to the next one, otherwise a
    # schedule would keep firing on the same tick forever.
    assert handler.compute_next_run_on("0 3 * * *", "UTC", moment) > moment


@pytest.mark.parametrize(
    "cron",
    ["not a cron", "0 3 * *", "0 3 * * * *", "99 3 * * *", "0 99 * * *"],
)
def test_invalid_cron_is_rejected(cron):
    with pytest.raises(InvalidBackupScheduleCron):
        BackupScheduleHandler().compute_next_run_on(cron)


def test_invalid_timezone_is_rejected():
    with pytest.raises(InvalidBackupScheduleCron):
        BackupScheduleHandler().compute_next_run_on("0 3 * * *", "Mars/Olympus_Mons")


@pytest.mark.django_db
def test_create_schedule_computes_the_next_run(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:backups:schedule_list", kwargs={"workspace_id": workspace.id}),
        {"name": "Nightly", "cron": "0 3 * * *", "keep_last": 7},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["cron"] == "0 3 * * *"
    assert response_json["keep_last"] == 7
    assert response_json["is_active"] is True
    assert response_json["next_run_on"] is not None


@pytest.mark.django_db
def test_create_schedule_with_an_invalid_cron(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:backups:schedule_list", kwargs={"workspace_id": workspace.id}),
        {"name": "Broken", "cron": "every night please"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_BACKUP_SCHEDULE_CRON"


@pytest.mark.django_db
def test_update_schedule_recomputes_the_next_run(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    schedule = data_fixture.create_backup_schedule(
        user=user, workspace=workspace, cron="0 3 * * *"
    )
    original_next_run = schedule.next_run_on

    response = api_client.patch(
        reverse("api:backups:schedule_item", kwargs={"schedule_id": schedule.id}),
        {"cron": "0 4 * * *"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    schedule.refresh_from_db()
    assert schedule.cron == "0 4 * * *"
    assert schedule.next_run_on != original_next_run


@pytest.mark.django_db
def test_delete_schedule(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    schedule = data_fixture.create_backup_schedule(user=user, workspace=workspace)

    response = api_client.delete(
        reverse("api:backups:schedule_item", kwargs={"schedule_id": schedule.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert not BackupSchedule.objects.filter(id=schedule.id).exists()


@pytest.mark.django_db
def test_list_schedules_of_a_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    schedule = data_fixture.create_backup_schedule(user=user, workspace=workspace)
    data_fixture.create_backup_schedule(user=user, workspace=other_workspace)

    response = api_client.get(
        reverse("api:backups:schedule_list", kwargs={"workspace_id": workspace.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [entry["id"] for entry in response.json()] == [schedule.id]


@pytest.mark.django_db
def test_schedule_of_another_workspace_is_not_readable(api_client, data_fixture):
    owner = data_fixture.create_user()
    _, outsider_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=owner)
    schedule = data_fixture.create_backup_schedule(user=owner, workspace=workspace)

    response = api_client.get(
        reverse("api:backups:schedule_item", kwargs={"schedule_id": schedule.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {outsider_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_run_schedule_now(
    api_client, data_fixture, django_capture_on_commit_callbacks, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)
    schedule = data_fixture.create_backup_schedule(user=user, workspace=workspace)

    with django_capture_on_commit_callbacks(execute=True):
        token = data_fixture.generate_token(user)
        response = api_client.post(
            reverse("api:backups:schedule_run", kwargs={"schedule_id": schedule.id}),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_202_ACCEPTED
    assert ExportApplicationsJob.objects.filter(workspace=workspace).count() == 1


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_periodic_task_only_runs_due_active_schedules(
    data_fixture, django_capture_on_commit_callbacks, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    due = data_fixture.create_backup_schedule(
        user=user,
        workspace=workspace,
        next_run_on=datetime.now(dt_timezone.utc) - timedelta(minutes=1),
    )
    not_due = data_fixture.create_backup_schedule(
        user=user,
        workspace=workspace,
        next_run_on=datetime.now(dt_timezone.utc) + timedelta(days=1),
    )
    inactive = data_fixture.create_backup_schedule(
        user=user,
        workspace=workspace,
        is_active=False,
        next_run_on=datetime.now(dt_timezone.utc) - timedelta(minutes=1),
    )

    with django_capture_on_commit_callbacks(execute=True):
        run_due_backup_schedules()

    assert ExportApplicationsJob.objects.count() == 1

    due.refresh_from_db()
    not_due.refresh_from_db()
    inactive.refresh_from_db()

    assert due.last_run_on is not None
    assert due.last_error == ""
    assert due.next_run_on > datetime.now(dt_timezone.utc)
    assert not_due.last_run_on is None
    assert inactive.last_run_on is None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_retention_marks_the_oldest_backups_for_deletion(
    data_fixture, django_capture_on_commit_callbacks, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)
    schedule = data_fixture.create_backup_schedule(
        user=user, workspace=workspace, keep_last=1
    )

    handler = BackupScheduleHandler()

    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True):
            handler.run_schedule(schedule)

    assert ImportExportResource.objects.count() == 2

    marked = handler.apply_retention(schedule)

    assert marked == 1
    # `objects` filters out anything marked for deletion, only the newest survives.
    assert ImportExportResource.objects.count() == 1
    assert ImportExportResource.objects_and_trash.count() == 2


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_retention_does_nothing_when_it_is_not_configured(
    data_fixture, django_capture_on_commit_callbacks, use_tmp_media_root
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)
    schedule = data_fixture.create_backup_schedule(user=user, workspace=workspace)

    handler = BackupScheduleHandler()

    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True):
            handler.run_schedule(schedule)

    assert handler.apply_retention(schedule) == 0
    assert ImportExportResource.objects.count() == 2
