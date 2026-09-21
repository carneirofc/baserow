import hashlib
import json
from datetime import timedelta
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models import Q
from django.utils import timezone

from loguru import logger

from baserow.contrib.database.table.models import Table

from .constants import (
    IMPORT_RECORD_STATUS_FAILED,
    IMPORT_RECORD_STATUS_FINISHED,
    IMPORT_RECORD_STATUS_RUNNING,
    STRICT_IMPORT_MODES,
)
from .exceptions import ImportSchemaMismatch
from .models import TableImportRecord


def get_importable_fields(table: Table, model=None) -> list:
    """
    Returns the fields of the table a file import is able to write values into, in
    the same order `RowHandler.import_rows` expects the row values in.

    :param table: The table to inspect.
    :param model: An already generated table model, to avoid regenerating it.
    :return: The importable fields, primary first, then by order, then by id.
    """

    model = model or table.get_model()
    fields = [
        field_object["field"]
        for field_object in model._field_objects.values()
        if not field_object["type"].read_only
        and not field_object["field"].read_only
        and field_object["type"].can_import
    ]
    fields.sort(key=lambda f: (not f.primary, f.order, f.id))
    return fields


def validate_strict_mapping(
    table: Table,
    mode: str,
    file_header: Optional[list[str]],
    field_mapping: Optional[list[int]],
    model=None,
) -> None:
    """
    Enforces that the file's columns line up exactly with the importable fields of
    the table, so an upsert or a replace can never write a partial row or silently
    drop a column. The table's schema is never touched by an import; this is what
    makes "the data format doesn't change" a checked contract rather than a promise.

    Only applies to the modes in `STRICT_IMPORT_MODES`. `append` keeps the lenient
    mapping it has always had.

    :param table: The table being imported into.
    :param mode: The import mode.
    :param file_header: The column headers as read from the file.
    :param field_mapping: One target field id per file column, `0` meaning skipped,
        aligned with `file_header`.
    :param model: An already generated table model, to avoid regenerating it.
    :raises ImportSchemaMismatch: When the columns don't line up.
    """

    if mode not in STRICT_IMPORT_MODES:
        return

    file_header = list(file_header or [])
    field_mapping = list(field_mapping or [])

    if len(file_header) != len(field_mapping):
        raise ImportSchemaMismatch(
            unmapped_file_columns=file_header[len(field_mapping) :] or file_header
        )

    importable_fields = get_importable_fields(table, model=model)
    importable_by_id = {field.id: field for field in importable_fields}

    unmapped_file_columns = [
        header
        for header, field_id in zip(file_header, field_mapping)
        if not field_id or field_id not in importable_by_id
    ]

    seen: set[int] = set()
    duplicated: set[int] = set()
    for field_id in field_mapping:
        if field_id in importable_by_id:
            if field_id in seen:
                duplicated.add(field_id)
            seen.add(field_id)

    uncovered_fields = [
        field.name for field in importable_fields if field.id not in seen
    ]
    # Ordered by the table's field order rather than by set iteration, so the error
    # message is stable.
    duplicate_fields = [
        field.name for field in importable_fields if field.id in duplicated
    ]

    if unmapped_file_columns or uncovered_fields or duplicate_fields:
        raise ImportSchemaMismatch(
            unmapped_file_columns=unmapped_file_columns,
            uncovered_fields=uncovered_fields,
            duplicate_fields=duplicate_fields,
        )


def payload_digest(data: list[list[Any]]) -> tuple[str, int]:
    """
    Returns the SHA-256 hex digest and the byte size of the normalized row payload,
    so a record can later be tied back to the exact data that was imported.
    """

    # Row order is part of what was imported, so the payload is hashed as given.
    encoded = json.dumps(data, ensure_ascii=False).encode("utf8")
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


class TableImportRecordHandler:
    """
    Creates and finalises the durable `TableImportRecord` that every row-affecting
    file import leaves behind, and emits the matching structured log line.
    """

    def create_record(
        self,
        user: AbstractUser,
        table: Table,
        mode: str,
        data: list[list[Any]],
        job=None,
        configuration: Optional[dict] = None,
    ) -> TableImportRecord:
        """
        Opens a `running` record before any row is touched, so a crashed worker still
        leaves a trace of what was attempted.
        """

        configuration = configuration or {}
        database = table.database
        workspace = database.workspace
        digest, size = payload_digest(data)

        file_header = configuration.get("file_header") or []
        field_mapping = configuration.get("field_mapping") or []

        return TableImportRecord.objects.create(
            job=job,
            workspace=workspace,
            workspace_name=workspace.name,
            database=database,
            database_name=database.name,
            table=table,
            table_name=table.name,
            user=user if getattr(user, "id", None) else None,
            user_email=getattr(user, "email", "") or "",
            user_ip_address=getattr(job, "user_ip_address", None),
            mode=mode,
            importer_type=getattr(job, "importer_type", "") or "",
            original_file_name=getattr(job, "original_file_name", "") or "",
            payload_sha256=digest,
            payload_bytes=size,
            # A list of pairs rather than a dict: two file columns may share a
            # header, and the record has to say what each of them was mapped to.
            field_mapping=[
                {"column": column, "field_id": field_id}
                for column, field_id in zip(file_header, field_mapping)
            ],
            upsert_field_ids=configuration.get("upsert_fields") or [],
            rows_in_file=len(data),
        )

    def finish_record(
        self,
        record: TableImportRecord,
        rows_created: int = 0,
        rows_updated: int = 0,
        rows_deleted: int = 0,
        report: Optional[dict] = None,
        trashed_rows_entry_id: Optional[int] = None,
        row_history_truncated: bool = False,
    ) -> TableImportRecord:
        # `report` is the job's error report, shaped as {"failing_rows": {index: ...}}.
        report = report or {}
        record.status = IMPORT_RECORD_STATUS_FINISHED
        record.rows_created = rows_created
        record.rows_updated = rows_updated
        record.rows_deleted = rows_deleted
        record.rows_failed = len(report.get("failing_rows") or {})
        record.report = report
        record.trashed_rows_entry_id = trashed_rows_entry_id
        record.row_history_truncated = row_history_truncated
        record.finished_on = timezone.now()
        record.save()
        self._log(record)
        return record

    def fail_record(self, record: TableImportRecord, error: str) -> TableImportRecord:
        record.status = IMPORT_RECORD_STATUS_FAILED
        record.error = str(error)[:2000]
        record.finished_on = timezone.now()
        record.save()
        self._log(record)
        return record

    def _log(self, record: TableImportRecord) -> None:
        logger.bind(
            compliance="table_import",
            record_id=record.id,
            job_id=record.job_id,
            status=record.status,
            mode=record.mode,
            workspace_id=record.workspace_id,
            database_id=record.database_id,
            table_id=record.table_id,
            table_name=record.table_name,
            user_id=record.user_id,
            user_email=record.user_email,
            user_ip_address=record.user_ip_address,
            original_file_name=record.original_file_name,
            payload_sha256=record.payload_sha256,
            rows_in_file=record.rows_in_file,
            rows_created=record.rows_created,
            rows_updated=record.rows_updated,
            rows_deleted=record.rows_deleted,
            rows_failed=record.rows_failed,
            trashed_rows_entry_id=record.trashed_rows_entry_id,
            row_history_truncated=record.row_history_truncated,
        ).info(
            "table import {status}: mode={mode} table={table_id} user={user_id} "
            "created={rows_created} updated={rows_updated} deleted={rows_deleted} "
            "failed={rows_failed}",
            status=record.status,
            mode=record.mode,
            table_id=record.table_id,
            user_id=record.user_id,
            rows_created=record.rows_created,
            rows_updated=record.rows_updated,
            rows_deleted=record.rows_deleted,
            rows_failed=record.rows_failed,
        )

    def reconcile_stale_records(self) -> int:
        """
        Gives a final status to the records whose job ended without one.

        An import job runs inside a transaction, so a failing job rolls back anything
        it wrote, including its own attempt to close the record. Here we look at the
        job's committed state instead: a record still `running` whose job has ended,
        or whose job has been cleaned up entirely, is marked failed.

        :return: The number of records that were closed.
        """

        from baserow.core.jobs.constants import (
            JOB_CANCELLED,
            JOB_FAILED,
            JOB_FINISHED,
        )

        stale = (
            TableImportRecord.objects.filter(status=IMPORT_RECORD_STATUS_RUNNING)
            .filter(
                Q(job__isnull=True)
                | Q(job__state__in=[JOB_FAILED, JOB_CANCELLED, JOB_FINISHED])
            )
            .select_related("job")
        )

        closed = 0
        for record in stale:
            job = record.job
            if job is None:
                error = "The import job no longer exists; its outcome is unknown."
            elif job.state == JOB_CANCELLED:
                error = "The import job was cancelled."
            elif job.state == JOB_FINISHED:
                # The job committed but the record was never closed, which should not
                # happen. Flag it rather than silently claiming success.
                error = "The import job finished without recording its result."
            else:
                error = job.human_readable_error or job.error or "The import failed."
            self.fail_record(record, error)
            closed += 1

        return closed

    def delete_expired_records(self) -> int:
        """
        Deletes records older than `BASEROW_TABLE_IMPORT_RECORD_RETENTION_DAYS`. A
        retention of `0` keeps them forever, which is the default: a compliance trail
        that silently disappears is worse than none.
        """

        retention_days = settings.BASEROW_TABLE_IMPORT_RECORD_RETENTION_DAYS
        if retention_days <= 0:
            return 0

        cutoff = timezone.now() - timedelta(days=retention_days)
        deleted, _ = TableImportRecord.objects.filter(started_on__lt=cutoff).delete()
        return deleted
