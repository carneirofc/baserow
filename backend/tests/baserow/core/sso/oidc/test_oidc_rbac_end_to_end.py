"""
End-to-end cover for the OIDC client role -> declared role -> permission manager chain.

Proves that an operator declaring a role in ``BASEROW_ROLES`` and mapping an IdP client role
to it in ``BASEROW_OIDC_PROVIDERS`` actually restricts what the member can do, without
any of the intermediate layers being stubbed.
"""

import dataclasses

import pytest

from baserow.core.auth_provider.models import OIDCAuthProviderModel
from baserow.core.exceptions import UserInvalidWorkspacePermissionsError
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceUser
from baserow.core.operations import (
    ReadWorkspaceOperationType,
    UpdateWorkspaceOperationType,
)
from baserow.core.roles.config import RoleConfig
from baserow.core.roles.exceptions import OperationNotAllowedByRoleError
from baserow.core.roles.handler import sync_declared_roles
from baserow.core.sso.oidc.config import OIDCProviderConfig, WorkspaceMapping
from baserow.core.sso.oidc.workspaces import sync_workspace_memberships

BASE_CONFIG = OIDCProviderConfig(
    name="rhbk",
    display_name="Keycloak",
    issuer="https://idp.example.com/realms/test",
    client_id="baserow",
    client_secret="secret",
)


@pytest.mark.django_db
def test_oidc_client_role_grants_only_the_declared_roles_operations(data_fixture):
    user = data_fixture.create_user()
    # A separate admin so the workspace is not left without one.
    workspace = data_fixture.create_workspace(user=data_fixture.create_user())

    # 1. The operator declares a read-only role.
    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Reader",
                operations=[ReadWorkspaceOperationType.type],
            )
        ]
    )

    # 2. ... and maps the IdP client role "analysts" to it.
    config = dataclasses.replace(
        BASE_CONFIG,
        workspace_mappings=[
            WorkspaceMapping(
                client_role="analysts",
                workspace_id=workspace.id,
                permissions="MEMBER",
                role="Reader",
            )
        ],
    )
    provider = OIDCAuthProviderModel.objects.create(name="rhbk")

    # 3. The user logs in carrying that client role.
    sync_workspace_memberships(user, ["analysts"], config, provider)

    assert WorkspaceUser.objects.get(user=user, workspace=workspace).role is not None

    # 4. The granular role permission manager enforces it.
    handler = CoreHandler()
    assert handler.check_permissions(
        user, ReadWorkspaceOperationType.type, workspace=workspace, context=workspace
    )
    with pytest.raises(OperationNotAllowedByRoleError):
        handler.check_permissions(
            user,
            UpdateWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )


@pytest.mark.django_db
def test_oidc_client_role_can_grant_an_operation_a_plain_member_lacks(data_fixture):
    # `workspace.update` is admin-only for a plain member; a declared role granting it
    # lifts that restriction, proving the mapping grants as well as denies.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=data_fixture.create_user())
    provider = OIDCAuthProviderModel.objects.create(name="rhbk")
    handler = CoreHandler()

    plain_member_config = dataclasses.replace(
        BASE_CONFIG,
        workspace_mappings=[
            WorkspaceMapping(
                client_role="analysts", workspace_id=workspace.id, permissions="MEMBER"
            )
        ],
    )
    sync_workspace_memberships(user, ["analysts"], plain_member_config, provider)

    assert WorkspaceUser.objects.get(user=user, workspace=workspace).role is None
    with pytest.raises(UserInvalidWorkspacePermissionsError):
        handler.check_permissions(
            user,
            UpdateWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Maintainer",
                operations=[
                    ReadWorkspaceOperationType.type,
                    UpdateWorkspaceOperationType.type,
                ],
            )
        ]
    )
    maintainer_config = dataclasses.replace(
        BASE_CONFIG,
        workspace_mappings=[
            WorkspaceMapping(
                client_role="analysts",
                workspace_id=workspace.id,
                permissions="MEMBER",
                role="Maintainer",
            )
        ],
    )
    sync_workspace_memberships(user, ["analysts"], maintainer_config, provider)

    assert handler.check_permissions(
        user,
        UpdateWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
    )
