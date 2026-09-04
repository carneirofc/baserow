import dataclasses

import pytest

from baserow.core.auth_provider.models import (
    OIDCAuthProviderModel,
    OIDCSsoWorkspaceMembership,
)
from baserow.core.models import Operation, WorkspaceUser
from baserow.core.roles.models import Role
from baserow.core.sso.oidc.config import OIDCProviderConfig, WorkspaceMapping
from baserow.core.sso.oidc.workspaces import sync_workspace_memberships

BASE_CONFIG = OIDCProviderConfig(
    name="rhbk",
    display_name="Keycloak",
    issuer="https://idp.example.com/realms/test",
    client_id="baserow",
    client_secret="secret",
)


def _config(mappings, strict=False):
    return dataclasses.replace(
        BASE_CONFIG, workspace_mappings=mappings, strict_membership=strict
    )


@pytest.fixture
def provider(db):
    return OIDCAuthProviderModel.objects.create(name="rhbk")


# --- additive behaviour (#4) ----------------------------------------------


@pytest.mark.django_db
def test_grants_new_membership(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="ADMIN"
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"


@pytest.mark.django_db
def test_updates_role_on_existing_membership(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="MEMBER", order=0
    )
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="ADMIN"
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"


@pytest.mark.django_db
def test_no_membership_when_group_does_not_match(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="ADMIN"
            )
        ]
    )

    sync_workspace_memberships(user, ["other-team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_unknown_workspace_is_skipped(data_fixture, provider):
    user = data_fixture.create_user()
    config = _config(
        [WorkspaceMapping(client_role="team", workspace_id=999999, permissions="ADMIN")]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_additive_mode_does_not_revoke_on_role_loss(data_fixture, provider):
    # With strict_membership off (default), a lost client role never revokes access.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="MEMBER"
            )
        ]
    )
    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()

    sync_workspace_memberships(user, [], config, provider)

    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


# --- strict revocation (#6) -----------------------------------------------


@pytest.mark.django_db
def test_strict_revokes_membership_on_role_loss(data_fixture, provider):
    user = data_fixture.create_user()
    # A second admin so the user is not the last admin of the workspace.
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=other)
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="MEMBER"
            )
        ],
        strict=True,
    )

    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()
    assert OIDCSsoWorkspaceMembership.objects.filter(
        provider=provider, user=user, workspace=workspace
    ).exists()

    # The user no longer holds the client role.
    sync_workspace_memberships(user, [], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()
    assert not OIDCSsoWorkspaceMembership.objects.filter(
        provider=provider, user=user, workspace=workspace
    ).exists()


@pytest.mark.django_db
def test_strict_never_revokes_manual_membership(data_fixture, provider):
    user = data_fixture.create_user()
    other = data_fixture.create_user()
    # A manually-added membership: no SSO tracking row exists for it.
    workspace = data_fixture.create_workspace(user=other)
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="MEMBER", order=0
    )
    # A mapping to the same workspace, but the user lacks the client role.
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="ADMIN"
            )
        ],
        strict=True,
    )

    sync_workspace_memberships(user, [], config, provider)

    # The manual membership is preserved (never tracked, so never revoked).
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_strict_keeps_membership_while_role_retained(data_fixture, provider):
    user = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=other)
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="MEMBER"
            )
        ],
        strict=True,
    )

    sync_workspace_memberships(user, ["team"], config, provider)
    # Second login, still holding the role.
    sync_workspace_memberships(user, ["team"], config, provider)

    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_strict_does_not_revoke_last_admin(data_fixture, provider):
    # If revoking would remove the workspace's last admin, the membership is kept.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="ADMIN"
            )
        ],
        strict=True,
    )
    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()

    # The user loses the role, but is the only admin.
    sync_workspace_memberships(user, [], config, provider)

    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


# --- granular roles -------------------------------------------------------


def _role(workspace, name="analyst", operations=("database.table.read",)):
    role = Role.objects.create(workspace=workspace, name=name)
    role.operations.set(
        [Operation.objects.get_or_create(name=op)[0] for op in operations]
    )
    return role


@pytest.mark.django_db
def test_grants_membership_with_a_granular_role(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    role = _role(workspace)
    config = _config(
        [
            WorkspaceMapping(
                client_role="team",
                workspace_id=workspace.id,
                permissions="MEMBER",
                role="analyst",
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "MEMBER"
    assert wu.role_id == role.id


@pytest.mark.django_db
def test_unknown_granular_role_refuses_the_membership(data_fixture, provider):
    # Fail closed: granting without the restricting role would hand out full member
    # access, the opposite of what the mapping asks for.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="team",
                workspace_id=workspace.id,
                permissions="MEMBER",
                role="does-not-exist",
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_a_role_from_another_workspace_is_not_used(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    other_workspace = data_fixture.create_workspace()
    _role(other_workspace)
    config = _config(
        [
            WorkspaceMapping(
                client_role="team",
                workspace_id=workspace.id,
                permissions="MEMBER",
                role="analyst",
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_dropping_the_granular_role_restores_full_member_access(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    role = _role(workspace)
    restricted = _config(
        [
            WorkspaceMapping(
                client_role="team",
                workspace_id=workspace.id,
                permissions="MEMBER",
                role="analyst",
            )
        ]
    )
    sync_workspace_memberships(user, ["team"], restricted, provider)
    assert WorkspaceUser.objects.get(user=user, workspace=workspace).role_id == role.id

    unrestricted = _config(
        [
            WorkspaceMapping(
                client_role="team", workspace_id=workspace.id, permissions="MEMBER"
            )
        ]
    )
    sync_workspace_memberships(user, ["team"], unrestricted, provider)

    assert WorkspaceUser.objects.get(user=user, workspace=workspace).role_id is None


# --- conflicting mappings -------------------------------------------------


@pytest.mark.django_db
def test_admin_wins_when_two_mappings_target_one_workspace(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="member-role",
                workspace_id=workspace.id,
                permissions="MEMBER",
            ),
            WorkspaceMapping(
                client_role="admin-role",
                workspace_id=workspace.id,
                permissions="ADMIN",
            ),
        ]
    )

    sync_workspace_memberships(user, ["member-role", "admin-role"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"
    assert wu.role_id is None


@pytest.mark.django_db
def test_admin_wins_regardless_of_mapping_order(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceMapping(
                client_role="admin-role",
                workspace_id=workspace.id,
                permissions="ADMIN",
            ),
            WorkspaceMapping(
                client_role="member-role",
                workspace_id=workspace.id,
                permissions="MEMBER",
            ),
        ]
    )

    sync_workspace_memberships(user, ["member-role", "admin-role"], config, provider)

    assert (
        WorkspaceUser.objects.get(user=user, workspace=workspace).permissions == "ADMIN"
    )
