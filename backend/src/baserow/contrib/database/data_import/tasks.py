from datetime import timedelta

from django.conf import settings

from baserow.config.celery import app


@app.task(bind=True, queue="export")
def reconcile_table_import_records(self):
    """
    Closes the import records whose job never reached a conclusion, and drops records
    that are past their retention.

    An import job runs inside a transaction, so when it fails everything it wrote is
    rolled back and it cannot mark its own record as failed. The record is created up
    front in the request that started the job, which is why it survives, and this task
    is what eventually gives it a final status.
    """

    from .handler import TableImportRecordHandler

    handler = TableImportRecordHandler()
    handler.reconcile_stale_records()
    handler.delete_expired_records()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=settings.BASEROW_TABLE_IMPORT_RECONCILE_INTERVAL_MINUTES),
        reconcile_table_import_records.s(),
    )
