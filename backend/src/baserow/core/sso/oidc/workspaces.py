"""
Mapping OIDC group membership to Baserow workspace memberships and granular roles.

On every login, for each configured ``{group, workspace, role, granular_role}`` mapping
whose group the user currently belongs to, the user is added to the workspace with that
role (or an existing membership is updated to it). The sync is authoritative for the
workspaces it maps: both ``WorkspaceUser.permissions`` and ``WorkspaceUser.role`` are
written to what the mapping asks for, so dropping ``granular_role`` from a mapping
restores unrestricted member access on the next login.

By default this is additive: memberships are never removed. When a provider enables
``strict_membership``, memberships that the sync itself created are recorded and revoked
once the user loses the mapped group - manually-added memberships are never tracked and
therefore never revoked.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from django.contrib.auth.models import AbstractUser

from loguru import logger

from baserow.core.auth_provider.models import (
    OIDCAuthProviderModel,
    OIDCSsoWorkspaceMembership,
)
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceUserIsLastAdmin
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.roles.models import Role
from baserow.core.signals import workspace_user_added
from baserow.core.sso.oidc.config import WORKSPACE_ROLE_ADMIN, OIDCProviderConfig


@dataclass(frozen=True)
class _DesiredMembership:
    """The membership a user's current groups ask for in one workspace."""

    permissions: str
    granular_role: Optional[str]


def sync_workspace_memberships(
    user: AbstractUser,
    groups: List[str],
    config: OIDCProviderConfig,
    provider: OIDCAuthProviderModel,
) -> None:
    """
    Adds/updates (and, in strict mode, revokes) the user's workspace memberships from
    their current IdP groups.

    :param user: The user that just signed in.
    :param groups: The user's current IdP group memberships.
    :param config: The provider configuration holding the workspace mappings.
    :param provider: The database anchor row for the provider, used to record
        SSO-granted memberships.
    """

    if not config.syncs_workspace_memberships:
        return

    desired = _resolve_desired_memberships(groups, config)
    granted_workspace_ids = _apply_desired_memberships(user, desired, config, provider)

    if config.strict_membership:
        _revoke_stale_memberships(user, provider, granted_workspace_ids)


def _resolve_desired_memberships(
    groups: List[str], config: OIDCProviderConfig
) -> Dict[int, _DesiredMembership]:
    """
    Collapses the mappings the user's groups match into one desired membership per
    workspace.

    When several matching mappings target the same workspace, an ``ADMIN`` mapping wins;
    otherwise the first matching mapping wins. Conflicts are logged, since two mappings
    disagreeing about a workspace is a configuration mistake.
    """

    group_set = set(groups)
    desired: Dict[int, _DesiredMembership] = {}

    for mapping in config.workspace_mappings:
        if mapping.group not in group_set:
            continue

        wanted = _DesiredMembership(
            permissions=mapping.role, granular_role=mapping.granular_role
        )
        current = desired.get(mapping.workspace_id)

        if current is None:
            desired[mapping.workspace_id] = wanted
            continue

        if current == wanted:
            continue

        if current.permissions == WORKSPACE_ROLE_ADMIN:
            winner = current
        elif wanted.permissions == WORKSPACE_ROLE_ADMIN:
            winner = wanted
        else:
            winner = current

        logger.warning(
            "OIDC provider '{0}' has conflicting mappings for workspace {1} "
            "(the user matches both {2} and {3}); applying {4}.",
            config.name,
            mapping.workspace_id,
            current,
            wanted,
            winner,
        )
        desired[mapping.workspace_id] = winner

    return desired


def _apply_desired_memberships(
    user: AbstractUser,
    desired: Dict[int, _DesiredMembership],
    config: OIDCProviderConfig,
    provider: OIDCAuthProviderModel,
) -> Set[int]:
    """
    Creates or updates the memberships in ``desired`` and returns the workspace ids that
    were actually granted.
    """

    granted_workspace_ids: Set[int] = set()

    for workspace_id, wanted in desired.items():
        workspace = Workspace.objects.filter(id=workspace_id).first()
        if workspace is None:
            logger.warning(
                "OIDC provider '{0}' maps to unknown workspace {1}; skipping.",
                config.name,
                workspace_id,
            )
            continue

        role = None
        if wanted.granular_role is not None:
            role = Role.objects.filter(
                workspace_id=workspace.id, name=wanted.granular_role
            ).first()
            if role is None:
                # Fail closed: granting the membership without the restricting role
                # would hand out full member access, the opposite of what the mapping
                # asks for.
                logger.error(
                    "OIDC provider '{0}' maps workspace {1} to unknown role '{2}'; "
                    "refusing the membership. Declare the role in BASEROW_ROLES and "
                    "run `sync_roles`.",
                    config.name,
                    workspace_id,
                    wanted.granular_role,
                )
                continue

        granted_workspace_ids.add(workspace.id)

        workspace_user, created = WorkspaceUser.objects.get_or_create(
            user=user,
            workspace=workspace,
            defaults={
                "order": WorkspaceUser.get_last_order(user),
                "permissions": wanted.permissions,
                "role": role,
            },
        )

        if created:
            workspace_user_added.send(
                None,
                workspace_user_id=workspace_user.id,
                workspace_user=workspace_user,
                user=user,
            )
            if config.strict_membership:
                # Only memberships the sync created are tracked, so a manually-added
                # membership to the same workspace is never revoked later.
                OIDCSsoWorkspaceMembership.objects.get_or_create(
                    provider=provider, user=user, workspace=workspace
                )
            continue

        update_fields = []
        if workspace_user.permissions != wanted.permissions:
            workspace_user.permissions = wanted.permissions
            update_fields.append("permissions")
        role_id = role.id if role is not None else None
        if workspace_user.role_id != role_id:
            workspace_user.role_id = role_id
            update_fields.append("role")
        if update_fields:
            workspace_user.save(update_fields=update_fields)

    return granted_workspace_ids


def _revoke_stale_memberships(
    user: AbstractUser,
    provider: OIDCAuthProviderModel,
    desired_workspace_ids: Set[int],
) -> None:
    """Revokes SSO-granted memberships the user no longer has a mapped group for."""

    stale = OIDCSsoWorkspaceMembership.objects.filter(provider=provider, user=user)
    if desired_workspace_ids:
        stale = stale.exclude(workspace_id__in=desired_workspace_ids)

    for record in stale.select_related("workspace"):
        try:
            CoreHandler().leave_workspace(user, record.workspace)
        except UserNotInWorkspace:
            # The membership was already removed elsewhere; drop the tracking row.
            pass
        except WorkspaceUserIsLastAdmin:
            # Never orphan a workspace by revoking its last admin; keep the membership
            # (and its tracking row) so a future login can reconcile it.
            logger.warning(
                "Skipping OIDC revocation of user {0} from workspace {1}: last admin.",
                user.id,
                record.workspace_id,
            )
            continue
        record.delete()
