"""
Reconciliation of the env-declared workspace roles (``BASEROW_ROLES``) into `Role` rows.

The reconcile is idempotent and runs after every migrate, and on demand through the
``sync_roles`` management command - workspaces are usually created after a deploy, so a
migrate-time-only reconcile would silently skip them.

Roles that exist in the database but are no longer declared are left untouched: they may
still be assigned to members, and silently dropping them would widen those members'
access back to full-member.
"""

from typing import List, Optional

from loguru import logger

from baserow.core.models import Operation, Workspace

from .config import RoleConfig, get_declared_roles
from .controllable_operations import CONTROLLABLE_OPERATION_TYPES
from .models import Role


def sync_declared_roles(configs: Optional[List[RoleConfig]] = None) -> None:
    """
    Creates or updates a `Role` per declared role config, and sets its operations.

    :param configs: The declared roles. Defaults to the ones in settings.
    """

    if configs is None:
        configs = get_declared_roles()

    if not configs:
        return

    for config in configs:
        if not Workspace.objects.filter(id=config.workspace_id).exists():
            logger.warning(
                "BASEROW_ROLES declares role '{0}' for unknown workspace {1}; skipping.",
                config.name,
                config.workspace_id,
            )
            continue

        wanted = []
        for operation in config.operations:
            if operation not in CONTROLLABLE_OPERATION_TYPES:
                logger.warning(
                    "BASEROW_ROLES role '{0}' (workspace {1}) lists operation '{2}' "
                    "which is not controllable by a role; skipping it.",
                    config.name,
                    config.workspace_id,
                    operation,
                )
                continue
            wanted.append(operation)

        operations = list(Operation.objects.filter(name__in=wanted))
        found = {operation.name for operation in operations}
        for missing in set(wanted) - found:
            logger.warning(
                "BASEROW_ROLES role '{0}' (workspace {1}) lists unregistered operation "
                "'{2}'; skipping it.",
                config.name,
                config.workspace_id,
                missing,
            )

        role, _ = Role.objects.get_or_create(
            workspace_id=config.workspace_id, name=config.name
        )
        role.operations.set(operations)
