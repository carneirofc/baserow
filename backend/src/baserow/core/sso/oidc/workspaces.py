"""
Mapping OIDC group membership to Baserow workspace memberships.

On every login, for each configured ``{group, workspace, role}`` mapping whose group
the user currently belongs to, the user is added to the workspace with that role (or an
existing membership is updated to it). This is additive only: memberships are never
removed here — strict revocation is a separate, opt-in feature.
"""

from typing import List

from django.contrib.auth.models import AbstractUser

from loguru import logger

from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.signals import workspace_user_added
from baserow.core.sso.oidc.config import OIDCProviderConfig


def sync_workspace_memberships(
    user: AbstractUser, groups: List[str], config: OIDCProviderConfig
) -> None:
    """
    Adds/updates the user's workspace memberships from their current IdP groups.

    :param user: The user that just signed in.
    :param groups: The user's current IdP group memberships.
    :param config: The provider configuration holding the workspace mappings.
    """

    if not config.syncs_workspace_memberships:
        return

    group_set = set(groups)
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
        elif workspace_user.permissions != mapping.role:
            workspace_user.permissions = mapping.role
            workspace_user.save(update_fields=["permissions"])
