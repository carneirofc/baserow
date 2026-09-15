from rest_framework import serializers

from baserow.core.audit_log.models import AuditLogEntry


class AuditLogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLogEntry
        fields = (
            "id",
            "user_id",
            "user_email",
            "workspace_id",
            "action_type",
            "command_type",
            "description",
            "created_on",
            "ip_address",
        )
        read_only_fields = fields
