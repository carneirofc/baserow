from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet
from django.utils import timezone

from celery.schedules import crontab

from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import ExportApplicationsJob, Workspace

from .exceptions import BackupScheduleDoesNotExist, InvalidBackupScheduleCron
from .handler import BackupHandler
from .models import BackupSchedule
from .operations import (
    CreateBackupScheduleOperationType,
    DeleteBackupScheduleOperationType,
    ListBackupSchedulesOperationType,
    ReadBackupScheduleOperationType,
    UpdateBackupScheduleOperationType,
)

# A cron expression that never matches within four years is treated as invalid rather
# than looping forever. Four years covers the leap year cycle.
MAX_DAYS_LOOKAHEAD = 366 * 4


class BackupScheduleHandler:
    def parse_cron(self, expression: str) -> crontab:
        """
        Turns a five field cron expression into a celery crontab schedule.

        :param expression: A `minute hour day_of_month month day_of_week` expression.
        :raises InvalidBackupScheduleCron: When the expression cannot be parsed.
        :return: The parsed schedule.
        """

        fields = expression.split()

        if len(fields) != 5:
            raise InvalidBackupScheduleCron(
                "A cron expression must have exactly five fields: minute, hour, "
                "day_of_month, month_of_year and day_of_week."
            )

        minute, hour, day_of_month, month_of_year, day_of_week = fields

        try:
            # `crontab` expands every field into a set of allowed values in its
            # constructor, so an invalid expression is rejected here instead of at run
            # time.
            return crontab(
                minute=minute,
                hour=hour,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                day_of_week=day_of_week,
            )
        except (ValueError, KeyError) as exc:
            raise InvalidBackupScheduleCron(
                f"The cron expression '{expression}' is invalid: {exc}"
            )

    def validate_timezone(self, name: str) -> str:
        """
        Checks that the given timezone name is known.

        :param name: An IANA timezone name.
        :raises InvalidBackupScheduleCron: When the timezone is unknown.
        :return: The validated name.
        """

        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidBackupScheduleCron(f"The timezone '{name}' is not known.")

        return name

    def compute_next_run_on(
        self,
        cron: str,
        tz_name: str = "UTC",
        after: Optional[datetime] = None,
    ) -> datetime:
        """
        Computes the first moment the cron expression is due after the given moment.

        :param cron: The cron expression.
        :param tz_name: The timezone the expression is evaluated in.
        :param after: The moment to start from, defaults to now. The returned moment
            is always strictly after it.
        :raises InvalidBackupScheduleCron: When the expression never matches.
        :return: The next due moment, as an aware UTC datetime.
        """

        schedule = self.parse_cron(cron)
        tz = ZoneInfo(self.validate_timezone(tz_name))
        after = (after or timezone.now()).astimezone(tz)

        hours = sorted(schedule.hour)
        minutes = sorted(schedule.minute)

        # Start looking from the next whole minute so the result is never the moment
        # we were asked to look after.
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for day in range(MAX_DAYS_LOOKAHEAD):
            if self._day_matches(schedule, candidate):
                for hour in hours:
                    if hour < candidate.hour:
                        continue
                    for minute in minutes:
                        if hour == candidate.hour and minute < candidate.minute:
                            continue
                        found = candidate.replace(hour=hour, minute=minute)
                        return found.astimezone(ZoneInfo("UTC"))

            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)

        raise InvalidBackupScheduleCron(
            f"The cron expression '{cron}' does not match any moment within "
            f"{MAX_DAYS_LOOKAHEAD} days."
        )

    def _day_matches(self, schedule: crontab, moment: datetime) -> bool:
        """
        Whether the date part of the given moment satisfies the schedule.

        Both `day_of_month` and `day_of_week` must match. Note that this is stricter
        than the OR semantics of some cron implementations, and matches how celery
        itself evaluates a crontab.
        """

        # Python counts weekdays from Monday, cron counts them from Sunday.
        cron_weekday = (moment.weekday() + 1) % 7

        return (
            moment.month in schedule.month_of_year
            and moment.day in schedule.day_of_month
            and cron_weekday in schedule.day_of_week
        )

    def list_schedules(self, user: AbstractUser, workspace_id: int) -> QuerySet:
        """
        Lists the backup schedules of a workspace.

        :param user: The user on whose behalf the schedules are listed.
        :param workspace_id: The workspace to list the schedules of.
        :return: A queryset of backup schedules.
        """

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            user,
            ListBackupSchedulesOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        return BackupSchedule.objects.filter(workspace=workspace).select_related(
            "workspace", "user"
        )

    def get_schedule(
        self, user: AbstractUser, schedule_id: int, for_update: bool = False
    ) -> BackupSchedule:
        """
        Fetches a single backup schedule.

        :param user: The user on whose behalf the schedule is requested.
        :param schedule_id: The id of the requested schedule.
        :param for_update: Whether the row should be locked.
        :raises BackupScheduleDoesNotExist: When the schedule does not exist.
        :return: The fetched schedule.
        """

        queryset = BackupSchedule.objects.select_related("workspace", "user")

        if for_update:
            queryset = queryset.select_for_update(of=("self",))

        try:
            schedule = queryset.get(id=schedule_id)
        except BackupSchedule.DoesNotExist:
            raise BackupScheduleDoesNotExist(
                f"The backup schedule with id {schedule_id} does not exist."
            )

        CoreHandler().check_permissions(
            user,
            ReadBackupScheduleOperationType.type,
            workspace=schedule.workspace,
            context=schedule,
        )

        return schedule

    def create_schedule(
        self,
        user: AbstractUser,
        workspace: Workspace,
        name: str,
        cron: str,
        tz_name: str = "UTC",
        application_ids: Optional[List[int]] = None,
        only_structure: bool = False,
        keep_last: Optional[int] = None,
        keep_days: Optional[int] = None,
        is_active: bool = True,
    ) -> BackupSchedule:
        """
        Creates a new backup schedule for a workspace.

        :param user: The user on whose behalf the scheduled backups will run.
        :param workspace: The workspace to back up.
        :param name: The human readable name of the schedule.
        :param cron: The cron expression describing when the backup runs.
        :param tz_name: The timezone the cron expression is evaluated in.
        :param application_ids: The applications to back up, None means all of them.
        :param only_structure: If true the row data is left out of the archive.
        :param keep_last: Count based retention, None disables it.
        :param keep_days: Age based retention in days, None disables it.
        :param is_active: Whether the schedule runs.
        :return: The created schedule.
        """

        CoreHandler().check_permissions(
            user,
            CreateBackupScheduleOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        tz_name = self.validate_timezone(tz_name)

        return BackupSchedule.objects.create(
            name=name,
            workspace=workspace,
            user=user,
            cron=cron,
            timezone=tz_name,
            application_ids=application_ids,
            only_structure=only_structure,
            keep_last=keep_last,
            keep_days=keep_days,
            is_active=is_active,
            next_run_on=self.compute_next_run_on(cron, tz_name),
        )

    def update_schedule(
        self, user: AbstractUser, schedule: BackupSchedule, **values
    ) -> BackupSchedule:
        """
        Updates an existing backup schedule. Only the provided fields are changed.

        :param user: The user on whose behalf the schedule is updated.
        :param schedule: The schedule to update.
        :param values: The fields to change.
        :return: The updated schedule.
        """

        CoreHandler().check_permissions(
            user,
            UpdateBackupScheduleOperationType.type,
            workspace=schedule.workspace,
            context=schedule,
        )

        allowed = [
            "name",
            "cron",
            "timezone",
            "application_ids",
            "only_structure",
            "keep_last",
            "keep_days",
            "is_active",
        ]

        for field in allowed:
            if field in values:
                setattr(schedule, field, values[field])

        schedule.timezone = self.validate_timezone(schedule.timezone)

        if "cron" in values or "timezone" in values or values.get("is_active"):
            schedule.next_run_on = self.compute_next_run_on(
                schedule.cron, schedule.timezone
            )

        schedule.save()
        return schedule

    def delete_schedule(self, user: AbstractUser, schedule: BackupSchedule):
        """
        Deletes a backup schedule. Backups it already made are kept.

        :param user: The user on whose behalf the schedule is deleted.
        :param schedule: The schedule to delete.
        """

        CoreHandler().check_permissions(
            user,
            DeleteBackupScheduleOperationType.type,
            workspace=schedule.workspace,
            context=schedule,
        )

        schedule.delete()

    def run_schedule(
        self, schedule: BackupSchedule, requested_by: Optional[AbstractUser] = None
    ) -> ExportApplicationsJob:
        """
        Starts the backup of a schedule right now, on behalf of the schedule's user.

        This does not advance `next_run_on`, the periodic task owns that.

        :param schedule: The schedule to run.
        :param requested_by: The user asking for the run, when it is triggered
            manually. Because the backup itself runs as the schedule's own user,
            triggering one requires permission to change the schedule, not merely to
            read it. Leave it out for the periodic task.
        :return: The started export job.
        """

        if requested_by is not None:
            CoreHandler().check_permissions(
                requested_by,
                UpdateBackupScheduleOperationType.type,
                workspace=schedule.workspace,
                context=schedule,
            )

        return BackupHandler().start_backup(
            schedule.user,
            schedule.workspace_id,
            application_ids=schedule.application_ids,
            only_structure=schedule.only_structure,
        )

    def apply_retention(self, schedule: BackupSchedule) -> int:
        """
        Marks the backups of a schedule's workspace that fall outside its retention
        window for deletion.

        Retention only ever considers backups owned by the schedule's user in the
        schedule's workspace, so a manual backup made by another member is never
        removed by somebody else's schedule.

        :param schedule: The schedule whose retention rules are applied.
        :return: The number of backups marked for deletion.
        """

        if schedule.keep_last is None and schedule.keep_days is None:
            return 0

        backups = list(
            ExportApplicationsJob.objects.filter(
                workspace_id=schedule.workspace_id,
                user_id=schedule.user_id,
                resource__is_valid=True,
                resource__marked_for_deletion=False,
            )
            .select_related("resource")
            .order_by("-updated_on", "-id")
        )

        to_delete = []

        if schedule.keep_last is not None:
            to_delete.extend(backups[schedule.keep_last :])

        if schedule.keep_days is not None:
            cutoff = timezone.now() - timedelta(days=schedule.keep_days)
            to_delete.extend(backup for backup in backups if backup.updated_on < cutoff)

        import_export_handler = ImportExportHandler()
        deleted_resource_ids = set()

        for backup in to_delete:
            if backup.resource_id in deleted_resource_ids:
                continue
            try:
                import_export_handler.mark_resource_for_deletion(
                    schedule.user, backup.resource_id
                )
                deleted_resource_ids.add(backup.resource_id)
            except Exception:
                # A resource that is currently being imported cannot be removed yet.
                # The next run of the schedule will try again.
                continue

        return len(deleted_resource_ids)
