from baserow.core.scheduling.cron import InvalidCron


class BackupScheduleDoesNotExist(Exception):
    """Raised when the requested backup schedule does not exist."""


class InvalidBackupScheduleCron(InvalidCron):
    """Raised when the provided cron expression cannot be parsed."""


class RemoteBackupDoesNotExist(Exception):
    """Raised when a backup is not available on the data destination."""


class RemoteBackupCorrupted(Exception):
    """Raised when a remote archive does not match the metadata written next to it."""


class RemoteBackupTrustNotAllowed(Exception):
    """
    Raised when trusting the signing key of a remote backup is requested by a
    non-staff user, or for a destination that does not allow it.
    """
