from rest_framework import serializers

from baserow.core.backups.models import BackupSchedule
from baserow.core.job_types import ExportApplicationsJobType

# A finished backup is the export job that produced it: the same serializer already
# exposes the archive name and its download URL.
BackupSerializer = ExportApplicationsJobType().response_serializer_class


class ListBackupsSerializer(serializers.Serializer):
    results = BackupSerializer(many=True)


class CreateBackupSerializer(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
        help_text=(
            "The applications to back up. Leave it out to back up every application "
            "of the workspace."
        ),
    )
    only_structure = serializers.BooleanField(
        required=False,
        default=False,
        help_text="If true the backup holds the structure but not the row data.",
    )


class RestoreBackupSerializer(serializers.Serializer):
    resource_id = serializers.IntegerField(
        min_value=1,
        help_text="The id of the backup resource to restore.",
    )
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
        help_text=(
            "The applications from the backup to restore. Leave it out to restore all "
            "of them."
        ),
    )


class BackupScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupSchedule
        fields = (
            "id",
            "name",
            "workspace",
            "cron",
            "timezone",
            "application_ids",
            "only_structure",
            "keep_last",
            "keep_days",
            "is_active",
            "next_run_on",
            "last_run_on",
            "last_error",
            "created_on",
            "updated_on",
        )
        read_only_fields = fields


class CreateBackupScheduleSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    cron = serializers.CharField(
        max_length=100,
        help_text=(
            "A five field crontab expression: minute, hour, day_of_month, "
            "month_of_year, day_of_week. For example `0 3 * * *` runs every night at "
            "three."
        ),
    )
    timezone = serializers.CharField(
        max_length=64,
        required=False,
        default="UTC",
        help_text="The IANA timezone the cron expression is evaluated in.",
    )
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
        default=None,
    )
    only_structure = serializers.BooleanField(required=False, default=False)
    keep_last = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    keep_days = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    is_active = serializers.BooleanField(required=False, default=True)


class UpdateBackupScheduleSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    cron = serializers.CharField(max_length=100, required=False)
    timezone = serializers.CharField(max_length=64, required=False)
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        allow_empty=True,
    )
    only_structure = serializers.BooleanField(required=False)
    keep_last = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    keep_days = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
