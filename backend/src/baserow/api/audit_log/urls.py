from django.urls import re_path

from .views import AuditLogEntryAdminView, AuditLogEntryExportView

app_name = "baserow.api.audit_log"

urlpatterns = [
    re_path(r"^export/$", AuditLogEntryExportView.as_view(), name="export"),
    re_path(r"^$", AuditLogEntryAdminView.as_view(), name="list"),
]
