from rest_framework import serializers

from baserow.contrib.database.data_import.models import TableImportRecord


class TableImportRecordUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="user_id")
    email = serializers.CharField(source="user_email")


class TableImportRecordSerializer(serializers.ModelSerializer):
    user = TableImportRecordUserSerializer(
        source="*",
        help_text="The user that started the import, as they were at the time.",
    )

    class Meta:
        model = TableImportRecord
        fields = (
            "id",
            "job_id",
            "workspace_id",
            "workspace_name",
            "database_id",
            "database_name",
            "table_id",
            "table_name",
            "user",
            "user_ip_address",
            "mode",
            "importer_type",
            "original_file_name",
            "payload_sha256",
            "payload_bytes",
            "field_mapping",
            "upsert_field_ids",
            "rows_in_file",
            "rows_created",
            "rows_updated",
            "rows_deleted",
            "rows_failed",
            "trashed_rows_entry_id",
            "row_history_truncated",
            "status",
            "error",
            "report",
            "started_on",
            "finished_on",
        )
        read_only_fields = fields
