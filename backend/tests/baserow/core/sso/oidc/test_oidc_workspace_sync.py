import dataclasses

import pytest

from baserow.core.auth_provider.models import (
    OIDCAuthProviderModel,
    OIDCSsoWorkspaceMembership,
)
from baserow.core.models import WorkspaceUser
from baserow.core.roles.models import Role
from baserow.core.sso.oidc.config import OIDCProviderConfig, WorkspaceRoleMapping
from baserow.core.sso.oidc.workspaces import sync_workspace_memberships

BASE_CONFIG = OIDCProviderConfig(
    name="keycloak",
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
    return OIDCAuthProviderModel.objects.create(name="keycloak")


# --- additive behaviour (#4) ----------------------------------------------


@pytest.mark.django_db
def test_grants_new_membership(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")]
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
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"


@pytest.mark.django_db
def test_no_membership_when_group_does_not_match(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")]
    )

    sync_workspace_memberships(user, ["other-team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_unknown_workspace_is_skipped(data_fixture, provider):
    user = data_fixture.create_user()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=999999, role="ADMIN")]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_additive_mode_does_not_revoke_on_group_loss(data_fixture, provider):
    # With strict_membership off (default), a lost group never revokes access.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="MEMBER")]
    )
    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()

    sync_workspace_memberships(user, [], config, provider)

    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


# --- strict revocation (#6) -----------------------------------------------


@pytest.mark.django_db
def test_strict_revokes_membership_on_group_loss(data_fixture, provider):
    user = data_fixture.create_user()
    # A second admin so the user is not the last admin of the workspace.
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=other)
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="MEMBER")],
        strict=True,
    )

    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()
    assert OIDCSsoWorkspaceMembership.objects.filter(
        provider=provider, user=user, workspace=workspace
    ).exists()

    # The user has left the group.
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
    # A mapping to the same workspace, but the user is not in the group.
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")],
        strict=True,
    )

    sync_workspace_memberships(user, [], config, provider)

    # The manual membership is preserved (never tracked, so never revoked).
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_strict_keeps_membership_while_group_retained(data_fixture, provider):
    user = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=other)
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="MEMBER")],
        strict=True,
    )

    sync_workspace_memberships(user, ["team"], config, provider)
    # Second login, still in the group.
    sync_workspace_memberships(user, ["team"], config, provider)

    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


# --- granular role mapping -------------------------------------------------


def _role(workspace, name="Editor"):
    return Role.objects.create(workspace=workspace, name=name)


@pytest.mark.django_db
def test_grants_the_mapped_granular_role(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    role = _role(workspace)
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "MEMBER"
    assert wu.role_id == role.id


@pytest.mark.django_db
def test_updates_the_granular_role_on_an_existing_membership(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    reader = _role(workspace, "Reader")
    editor = _role(workspace, "Editor")
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="MEMBER", order=0, role=reader
    )
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.role_id == editor.id


@pytest.mark.django_db
def test_dropping_granular_role_from_the_mapping_clears_it(data_fixture, provider):
    # The sync is authoritative for the workspaces it maps, so removing granular_role
    # restores unrestricted member access on the next login.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    _role(workspace)
    with_role = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            )
        ]
    )
    sync_workspace_memberships(user, ["team"], with_role, provider)
    assert WorkspaceUser.objects.get(user=user, workspace=workspace).role_id is not None

    without_role = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="MEMBER")]
    )
    sync_workspace_memberships(user, ["team"], without_role, provider)

    assert WorkspaceUser.objects.get(user=user, workspace=workspace).role_id is None


@pytest.mark.django_db
def test_membership_is_refused_when_the_granular_role_is_missing(
    data_fixture, provider
):
    # Fail closed: granting the membership without the restricting role would hand out
    # full member access, the opposite of what the mapping asks for.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="DoesNotExist",
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
    _role(other_workspace, "Editor")
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_strict_revokes_a_membership_whose_granular_role_disappeared(
    data_fixture, provider
):
    user = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=other)
    role = _role(workspace)
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            )
        ],
        strict=True,
    )
    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()

    role.delete()
    sync_workspace_memberships(user, ["team"], config, provider)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_conflicting_mappings_resolve_admin_first(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    _role(workspace)
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            ),
            WorkspaceRoleMapping(
                group="leads", workspace_id=workspace.id, role="ADMIN"
            ),
        ]
    )

    sync_workspace_memberships(user, ["team", "leads"], config, provider)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"
    assert wu.role_id is None


@pytest.mark.django_db
def test_conflicting_member_mappings_apply_the_first(data_fixture, provider):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    reader = _role(workspace, "Reader")
    _role(workspace, "Editor")
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Reader",
            ),
            WorkspaceRoleMapping(
                group="leads",
                workspace_id=workspace.id,
                role="MEMBER",
                granular_role="Editor",
            ),
        ]
    )

    sync_workspace_memberships(user, ["team", "leads"], config, provider)

    assert (
        WorkspaceUser.objects.get(user=user, workspace=workspace).role_id == reader.id
    )


@pytest.mark.django_db
def test_strict_does_not_revoke_last_admin(data_fixture, provider):
    # If revoking would remove the workspace's last admin, the membership is kept.
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")],
        strict=True,
    )
    sync_workspace_memberships(user, ["team"], config, provider)
    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()

    # User leaves the group, but is the only admin.
    sync_workspace_memberships(user, [], config, provider)

    assert WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()
