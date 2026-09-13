from baserow.core.scheduling.cron import InvalidCron


class BackupScheduleDoesNotExist(Exception):
    """Raised when the requested backup schedule does not exist."""


class InvalidBackupScheduleCron(InvalidCron):
    """Raised when the provided cron expression cannot be parsed."""
