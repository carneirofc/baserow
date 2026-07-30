class BackupScheduleDoesNotExist(Exception):
    """Raised when the requested backup schedule does not exist."""


class InvalidBackupScheduleCron(Exception):
    """Raised when the provided cron expression cannot be parsed."""
