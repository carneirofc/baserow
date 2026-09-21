import hashlib
import json
import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from tempfile import SpooledTemporaryFile
from typing import IO, Any, Dict, List, Optional
from zipfile import BadZipFile, ZipFile

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from loguru import logger

from baserow.core.data_destinations.config import PURPOSE_BACKUP
from baserow.core.data_destinations.exceptions import InvalidDataDestinationKey
from baserow.core.data_destinations.handler import DataDestinationHandler
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import (
    MANIFEST_NAME,
    SIGNATURE_NAME,
    ImportExportHandler,
)
from baserow.core.models import ImportApplicationsJob
from baserow.core.operations import (
    CreateApplicationsWorkspaceOperationType,
    ExportWorkspaceOperationType,
)
from baserow.core.storage import get_default_storage
from baserow.version import VERSION

from .exceptions import (
    RemoteBackupCorrupted,
    RemoteBackupDoesNotExist,
    RemoteBackupTrustNotAllowed,
)
from .models import BackupSchedule, ExportApplicationsToDestinationJob

BACKUPS_PREFIX = "backups"
ARCHIVE_SUFFIX = ".zip"
SIDECAR_SUFFIX = ".zip.json"
SIDECAR_FORMAT_VERSION = 1
COPY_CHUNK_SIZE = 1024 * 1024
# Archives up to this size are restored in memory, larger ones spill to disk.
RESTORE_MEMORY_LIMIT = 64 * 1024 * 1024


def _sha256_of(handle: IO[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(COPY_CHUNK_SIZE), b""):
        digest.update(chunk)
    return digest.hexdigest()


class BackupDestinationHandler:
    """
    Ships backup archives to an env-declared data destination and brings them back.

    Every archive is written as `backups/workspace=<id>/<timestamp>_<uuid>.zip` with a
    JSON sidecar next to it. The sidecar is written last, so an archive without one is
    an incomplete upload and is ignored. The sidecar carries everything needed to list
    and restore the backup on a fresh instance, where the originating database is
    gone.
    """

    def __init__(self):
        self.destinations = DataDestinationHandler()

    def get_archive_key(
        self, workspace_id: int, created_on: datetime, resource_uuid: Any
    ) -> str:
        timestamp = created_on.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return (
            f"{BACKUPS_PREFIX}/workspace={workspace_id}/"
            f"{timestamp}_{resource_uuid}{ARCHIVE_SUFFIX}"
        )

    def get_sidecar_key(self, archive_key: str) -> str:
        return archive_key + ".json"

    def read_archive_metadata(self, handle: IO[bytes]) -> Dict[str, Any]:
        """
        Extracts the applications, configuration and signing key from an archive.

        :param handle: A seekable binary handle of the zip archive.
        :raises RemoteBackupCorrupted: When the archive is not a valid export.
        :return: The metadata stored in the sidecar.
        """

        try:
            with ZipFile(handle, "r") as zip_file:
                manifest = json.loads(zip_file.read(MANIFEST_NAME))
                signature = (
                    json.loads(zip_file.read(SIGNATURE_NAME))
                    if SIGNATURE_NAME in zip_file.namelist()
                    else {}
                )
        except (BadZipFile, KeyError, ValueError) as exc:
            raise RemoteBackupCorrupted(f"The archive is not a valid export: {exc}")

        applications = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "type": application_type,
            }
            for application_type, group in manifest.get("applications", {}).items()
            for item in group.get("items", [])
        ]

        return {
            "applications": applications,
            "only_structure": bool(
                manifest.get("configuration", {}).get("only_structure", False)
            ),
            "public_key_pem": signature.get("public_key_pem") or "",
            "export_baserow_version": manifest.get("baserow_version"),
        }

    def upload_archive(self, job: ExportApplicationsToDestinationJob) -> str:
        """
        Uploads the archive of a finished export to its destination, followed by the
        sidecar that marks the upload as complete.

        :param job: The export job, its resource must already be set.
        :return: The key of the uploaded archive.
        """

        destination = self.destinations.get_destination(
            job.destination, purpose=PURPOSE_BACKUP
        )
        storage = self.destinations.get_storage(destination)
        source_storage = get_default_storage()
        resource = job.resource
        export_path = ImportExportHandler().get_export_storage_path(
            resource.get_archive_name()
        )

        archive_key = self.get_archive_key(
            job.workspace_id, timezone.now(), resource.uuid
        )

        with source_storage.open(export_path, "rb") as source:
            sha256 = _sha256_of(source)
            source.seek(0)
            metadata = self.read_archive_metadata(source)
            source.seek(0)
            self.destinations.save_file(storage, archive_key, source)

        workspace = job.workspace
        sidecar = {
            "format_version": SIDECAR_FORMAT_VERSION,
            "archive_key": archive_key,
            "instance_id": CoreHandler().get_settings().instance_id,
            "baserow_version": VERSION,
            "workspace": {
                "id": job.workspace_id,
                "name": workspace.name if workspace else None,
            },
            "schedule_id": job.backup_schedule_id,
            "created_on": timezone.now().isoformat(),
            "created_by": job.user.email if job.user_id else None,
            "size": resource.size,
            "sha256": sha256,
            **metadata,
        }
        self.destinations.write_json(
            storage, self.get_sidecar_key(archive_key), sidecar
        )

        job.remote_key = archive_key
        job.save(update_fields=["remote_key"])

        return archive_key

    def list_backups(
        self, destination_name: str, workspace_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists the complete uploads on a destination, without any permission check.
        Meant for the periodic retention task and management commands.

        :param destination_name: The name of the data destination.
        :param workspace_id: Only the backups of this workspace, None for all.
        :return: The sidecars, each with its archive `key`, most recent first.
        """

        destination = self.destinations.get_destination(
            destination_name, purpose=PURPOSE_BACKUP
        )
        storage = self.destinations.get_storage(destination)
        prefix = (
            f"{BACKUPS_PREFIX}/workspace={workspace_id}"
            if workspace_id is not None
            else BACKUPS_PREFIX
        )

        backups = []
        for key in self.destinations.list_keys(storage, prefix):
            if not key.endswith(SIDECAR_SUFFIX):
                continue
            try:
                sidecar = self.destinations.read_json(storage, key)
            except (OSError, ValueError) as exc:
                logger.warning(
                    "Skipping unreadable backup sidecar {key}: {error}",
                    key=key,
                    error=exc,
                )
                continue
            # Trust the key the sidecar was found at, not the one it claims.
            sidecar["key"] = key[: -len(".json")]
            backups.append(sidecar)

        backups.sort(key=lambda backup: backup.get("created_on") or "", reverse=True)
        return backups

    def list_remote_backups(
        self, user: AbstractUser, workspace_id: int, destination_name: str
    ) -> List[Dict[str, Any]]:
        """
        Lists the backups of a workspace that are available on a destination.

        :param user: The user on whose behalf the backups are listed.
        :param workspace_id: The workspace the backups were made of.
        :param destination_name: The name of the data destination.
        :return: The sidecars of the complete uploads, most recent first.
        """

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            user,
            ExportWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        return self.list_backups(destination_name, workspace_id)

    def apply_remote_retention(self, schedule: BackupSchedule) -> int:
        """
        Deletes the uploaded backups of a schedule that fall outside its retention
        window. Only backups this schedule made are considered.

        :param schedule: The schedule whose retention rules are applied.
        :return: The number of remote backups deleted.
        """

        if not schedule.destination or (
            schedule.keep_last is None and schedule.keep_days is None
        ):
            return 0

        backups = [
            backup
            for backup in self.list_backups(schedule.destination, schedule.workspace_id)
            if backup.get("schedule_id") == schedule.id
        ]

        to_delete = {}
        if schedule.keep_last is not None:
            for backup in backups[schedule.keep_last :]:
                to_delete[backup["key"]] = backup
        if schedule.keep_days is not None:
            cutoff = timezone.now() - timedelta(days=schedule.keep_days)
            for backup in backups:
                created_on = parse_datetime(backup.get("created_on") or "")
                if created_on is not None and created_on < cutoff:
                    to_delete[backup["key"]] = backup

        if not to_delete:
            return 0

        destination = self.destinations.get_destination(
            schedule.destination, purpose=PURPOSE_BACKUP
        )
        storage = self.destinations.get_storage(destination)
        for key in to_delete:
            # The archive goes first: a sidecar without an archive is still listed and
            # would be retried, an archive without a sidecar is invisible garbage.
            self.destinations.delete_keys(storage, [key, self.get_sidecar_key(key)])

        return len(to_delete)

    def restore_remote_backup(
        self,
        user: AbstractUser,
        workspace_id: int,
        destination_name: str,
        key: str,
        application_ids: Optional[List[int]] = None,
        trust_public_key: bool = False,
        sync: bool = False,
    ) -> ImportApplicationsJob:
        """
        Downloads a backup from a destination and starts restoring it into a
        workspace. The applications are installed as new applications.

        :param user: The user on whose behalf the restore is made.
        :param workspace_id: The workspace to restore into.
        :param destination_name: The name of the data destination.
        :param key: The key of the archive, as returned by the listing.
        :param application_ids: The applications from the archive to restore. None
            means all of them.
        :param trust_public_key: Trust the key the archive was signed with, which is
            needed when it was made by another instance. Requires a staff user and a
            destination that allows it.
        :raises InvalidDataDestinationKey: When the key is not a backup archive key.
        :raises RemoteBackupDoesNotExist: When the archive or its sidecar is missing.
        :raises RemoteBackupCorrupted: When the archive does not match its sidecar.
        :raises RemoteBackupTrustNotAllowed: When trusting the key is not permitted.
        :param sync: Run the import in the current process instead of a worker.
        :return: The started import job.
        """

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        destination = self.destinations.get_destination(
            destination_name, purpose=PURPOSE_BACKUP
        )
        key = self.destinations.normalize_key(key)
        if not key.startswith(f"{BACKUPS_PREFIX}/") or not key.endswith(ARCHIVE_SUFFIX):
            raise InvalidDataDestinationKey(f"The key '{key}' is not a backup archive.")

        if trust_public_key and (
            not user.is_staff or not destination.allow_trust_public_key
        ):
            raise RemoteBackupTrustNotAllowed(
                "Trusting the signing key of a remote backup requires a staff user and "
                "a destination with `allow_trust_public_key` enabled."
            )

        storage = self.destinations.get_storage(destination)
        sidecar_key = self.get_sidecar_key(key)
        if not storage.exists(key) or not storage.exists(sidecar_key):
            raise RemoteBackupDoesNotExist(f"The backup '{key}' is not available.")
        sidecar = self.destinations.read_json(storage, sidecar_key)

        with SpooledTemporaryFile(max_size=RESTORE_MEMORY_LIMIT) as archive:
            with storage.open(key, "rb") as source:
                for chunk in iter(lambda: source.read(COPY_CHUNK_SIZE), b""):
                    archive.write(chunk)

            archive.seek(0)
            if _sha256_of(archive) != sidecar.get("sha256"):
                raise RemoteBackupCorrupted(
                    f"The archive '{key}' does not match its recorded checksum."
                )

            if trust_public_key:
                archive.seek(0)
                self._trust_archive_key(user, destination.name, archive, sidecar)

            archive.seek(0)
            resource = ImportExportHandler().create_resource_from_file(
                user, os.path.basename(key), archive
            )

        from .handler import BackupHandler

        return BackupHandler().start_restore(
            user,
            workspace_id,
            resource.id,
            application_ids=application_ids,
            sync=sync,
        )

    def _trust_archive_key(
        self,
        user: AbstractUser,
        destination_name: str,
        archive: IO[bytes],
        sidecar: Dict[str, Any],
    ):
        """
        Registers the key an archive was signed with as a trusted import source.

        The key inside the archive must equal the one recorded in the sidecar, so a
        swapped archive cannot smuggle in a key of its own.
        """

        public_key_pem = self.read_archive_metadata(archive)["public_key_pem"]
        if not public_key_pem or public_key_pem != sidecar.get("public_key_pem"):
            raise RemoteBackupCorrupted(
                "The signing key of the archive does not match its recorded key."
            )

        name = f"destination:{destination_name}:{sidecar.get('instance_id') or ''}"
        ImportExportHandler().add_trusted_public_key(name[:255], public_key_pem)
        logger.warning(
            "User {user_id} trusted the backup signing key of {name}.",
            user_id=user.id,
            name=name,
        )
