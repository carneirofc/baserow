from django.contrib.auth import get_user_model
from django.db import models

from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.models import Workspace

from .constants import (
    IMPORT_MODE_APPEND,
    IMPORT_MODE_REPLACE,
    IMPORT_MODE_UPSERT,
    IMPORT_RECORD_STATUS_FAILED,
    IMPORT_RECORD_STATUS_FINISHED,
    IMPORT_RECORD_STATUS_RUNNING,
)

User = get_user_model()


class TableImportRecord(models.Model):
    """
    A durable, append-only record of every file import that has touched the rows of a
    table. Unlike `FileImportJob` this is deliberately not a `Job`, so
    `JobHandler.clean_up_jobs` never removes it and the trail outlives the transient
    job it describes.

    Every relation is nullable with a denormalised snapshot alongside it, so deleting
    the workspace, database, table or user does not erase who did what, when.
    """

    MODE_CHOICES = [
        (IMPORT_MODE_APPEND, "Append"),
        (IMPORT_MODE_UPSERT, "Upsert"),
        (IMPORT_MODE_REPLACE, "Replace"),
    ]

    STATUS_CHOICES = [
        (IMPORT_RECORD_STATUS_RUNNING, "Running"),
        (IMPORT_RECORD_STATUS_FINISHED, "Finished"),
        (IMPORT_RECORD_STATUS_FAILED, "Failed"),
    ]

    job = models.ForeignKey(
        "database.FileImportJob",
        on_delete=models.SET_NULL,
        null=True,
        related_name="import_records",
        help_text="The import job this record describes, while it still exists.",
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.SET_NULL,
        null=True,
        related_name="table_import_records",
    )
    workspace_name = models.TextField(blank=True, default="")
    database = models.ForeignKey(
        Database,
        on_delete=models.SET_NULL,
        null=True,
        related_name="table_import_records",
    )
    database_name = models.TextField(blank=True, default="")
    table = models.ForeignKey(
        Table,
        on_delete=models.SET_NULL,
        null=True,
        related_name="import_records",
    )
    table_name = models.TextField(blank=True, default="")

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="table_import_records",
    )
    user_email = models.TextField(
        blank=True,
        default="",
        help_text="The email of the user at the time of the import.",
    )
    user_ip_address = models.GenericIPAddressField(
        null=True, help_text="The IP address the import was requested from."
    )

    mode = models.CharField(
        max_length=16,
        choices=MODE_CHOICES,
        default=IMPORT_MODE_APPEND,
        help_text="Whether the file was appended, upserted or used to replace the "
        "table's contents.",
    )
    importer_type = models.TextField(
        blank=True,
        default="",
        help_text="The frontend importer identifier used to parse the file.",
    )
    original_file_name = models.TextField(
        blank=True, default="", help_text="The original name of the uploaded file."
    )
    payload_sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 of the normalized row payload that was imported.",
    )
    payload_bytes = models.PositiveBigIntegerField(
        default=0, help_text="Size in bytes of the normalized row payload."
    )

    field_mapping = models.JSONField(
        default=list,
        help_text="One {column, field_id} entry per column of the imported file, in "
        "file order.",
    )
    upsert_field_ids = models.JSONField(
        default=list,
        help_text="The field ids used to match imported rows against existing rows.",
    )

    rows_in_file = models.PositiveIntegerField(default=0)
    rows_created = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)
    rows_deleted = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)

    trashed_rows_entry_id = models.PositiveIntegerField(
        null=True,
        help_text="The trash entry holding the rows a replace removed, so the "
        "previous contents can be restored.",
    )
    row_history_truncated = models.BooleanField(
        default=False,
        help_text="Whether per-row history was capped by "
        "BASEROW_MAX_ROW_HISTORY_ENTRIES_PER_IMPORT.",
    )

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=IMPORT_RECORD_STATUS_RUNNING,
    )
    error = models.TextField(
        blank=True, default="", help_text="The error that made the import fail."
    )
    report = models.JSONField(
        default=dict, help_text="A copy of the per-row error report."
    )

    started_on = models.DateTimeField(auto_now_add=True)
    finished_on = models.DateTimeField(null=True)

    class Meta:
        ordering = ("-started_on", "-id")
        indexes = [
            models.Index(fields=["table", "-started_on"]),
            models.Index(fields=["workspace", "-started_on"]),
        ]

    def __str__(self):
        return (
            f"TableImportRecord {self.id} ({self.mode}) "
            f"table={self.table_id} status={self.status}"
        )
