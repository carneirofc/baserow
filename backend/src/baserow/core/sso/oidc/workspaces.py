"""
Mapping OIDC group membership to Baserow workspace memberships.

On every login, for each configured ``{group, workspace, role}`` mapping whose group
the user currently belongs to, the user is added to the workspace with that role (or an
existing membership is updated to it).

By default this is additive: memberships are never removed. When a provider enables
``strict_membership``, memberships that the sync itself created are recorded and revoked
once the user loses the mapped group — manually-added memberships are never tracked and
therefore never revoked.
"""

from typing import List, Set

from django.contrib.auth.models import AbstractUser

from loguru import logger

from baserow.core.auth_provider.models import (
    OIDCAuthProviderModel,
    OIDCSsoWorkspaceMembership,
)
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceUserIsLastAdmin
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.signals import workspace_user_added
from baserow.core.sso.oidc.config import OIDCProviderConfig


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

    group_set = set(groups)
    desired_workspace_ids: Set[int] = set()

    for mapping in config.workspace_mappings:
        if mapping.group not in group_set:
            continue

        workspace = Workspace.objects.filter(id=mapping.workspace_id).first()
        if workspace is None:
            logger.warning(
                "OIDC provider '{0}' maps group '{1}' to unknown workspace {2}; "
                "skipping.",
                config.name,
                mapping.group,
                mapping.workspace_id,
            )
            continue

        desired_workspace_ids.add(workspace.id)

        workspace_user, created = WorkspaceUser.objects.get_or_create(
            user=user,
            workspace=workspace,
            defaults={
                "order": WorkspaceUser.get_last_order(user),
                "permissions": mapping.role,
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
        elif workspace_user.permissions != mapping.role:
            workspace_user.permissions = mapping.role
            workspace_user.save(update_fields=["permissions"])

    if config.strict_membership:
        _revoke_stale_memberships(user, provider, desired_workspace_ids)


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
