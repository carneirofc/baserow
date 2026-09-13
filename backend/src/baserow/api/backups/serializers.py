from rest_framework import serializers

from baserow.core.backups.models import BackupSchedule
from baserow.core.job_types import ExportApplicationsJobType

_ExportJobSerializer = ExportApplicationsJobType().response_serializer_class


class BackupSerializer(_ExportJobSerializer):
    """
    A finished backup is the export job that produced it: the export serializer
    already exposes the archive name and its download URL. The resource id is what
    the restore and delete endpoints take, and the destination fields tell whether
    the archive was also uploaded to external storage.
    """

    resource_id = serializers.IntegerField(read_only=True, allow_null=True)
    destination = serializers.SerializerMethodField(
        help_text="The data destination the archive was uploaded to, if any."
    )
    remote_key = serializers.SerializerMethodField(
        help_text="The key of the uploaded archive on the destination, if any."
    )

    class Meta(_ExportJobSerializer.Meta):
        ref_name = "BackupSerializer"
        fields = tuple(_ExportJobSerializer.Meta.fields) + (
            "resource_id",
            "destination",
            "remote_key",
        )

    def _destination_job(self, instance):
        # Backups uploaded to a destination are a multi-table child of the export.
        return getattr(instance, "exportapplicationstodestinationjob", instance)

    def get_destination(self, instance) -> str:
        return getattr(self._destination_job(instance), "destination", "") or ""

    def get_remote_key(self, instance) -> str:
        return getattr(self._destination_job(instance), "remote_key", "") or ""


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
    destination = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "The name of a data destination to also upload the backup to. Leave it "
            "out to keep the backup on the instance storage only."
        ),
    )


class RemoteBackupSerializer(serializers.Serializer):
    key = serializers.CharField(
        help_text="The key of the archive, pass it to the restore endpoint."
    )
    created_on = serializers.CharField()
    size = serializers.IntegerField()
    sha256 = serializers.CharField()
    only_structure = serializers.BooleanField()
    instance_id = serializers.CharField(
        allow_null=True,
        help_text="The instance that made the backup.",
    )
    baserow_version = serializers.CharField(allow_null=True)
    schedule_id = serializers.IntegerField(allow_null=True)
    workspace = serializers.DictField()
    applications = serializers.ListField(child=serializers.DictField())


class ListRemoteBackupsSerializer(serializers.Serializer):
    results = RemoteBackupSerializer(many=True)


class RestoreRemoteBackupSerializer(serializers.Serializer):
    key = serializers.CharField(
        max_length=512,
        help_text="The key of the archive to restore, as returned by the listing.",
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
    trust_public_key = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Trust the key the archive was signed with. Needed to restore a backup "
            "made by another instance; staff only, and the destination must allow it."
        ),
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
            "destination",
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
    destination = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "The name of a data destination every backup is also uploaded to. Empty "
            "keeps the backups on the instance storage only."
        ),
    )
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
    destination = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    keep_last = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    keep_days = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
