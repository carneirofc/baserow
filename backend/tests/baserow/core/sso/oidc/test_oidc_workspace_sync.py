import dataclasses

import pytest

from baserow.core.models import WorkspaceUser
from baserow.core.sso.oidc.config import OIDCProviderConfig, WorkspaceRoleMapping
from baserow.core.sso.oidc.workspaces import sync_workspace_memberships

BASE_CONFIG = OIDCProviderConfig(
    name="keycloak",
    display_name="Keycloak",
    issuer="https://idp.example.com/realms/test",
    client_id="baserow",
    client_secret="secret",
)


def _config(mappings):
    return dataclasses.replace(BASE_CONFIG, workspace_mappings=mappings)


@pytest.mark.django_db
def test_grants_new_membership(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")]
    )

    sync_workspace_memberships(user, ["team"], config)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"


@pytest.mark.django_db
def test_updates_role_on_existing_membership(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace, user=user, permissions="MEMBER", order=0
    )
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")]
    )

    sync_workspace_memberships(user, ["team"], config)

    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"


@pytest.mark.django_db
def test_no_membership_when_group_does_not_match(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=workspace.id, role="ADMIN")]
    )

    sync_workspace_memberships(user, ["other-team"], config)

    assert not WorkspaceUser.objects.filter(user=user, workspace=workspace).exists()


@pytest.mark.django_db
def test_unknown_workspace_is_skipped(data_fixture):
    user = data_fixture.create_user()
    config = _config(
        [WorkspaceRoleMapping(group="team", workspace_id=999999, role="ADMIN")]
    )

    # Should not raise.
    sync_workspace_memberships(user, ["team"], config)

    assert not WorkspaceUser.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_does_not_remove_other_memberships(data_fixture):
    user = data_fixture.create_user()
    mapped_workspace = data_fixture.create_workspace()
    other_workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=other_workspace, user=user, permissions="MEMBER", order=0
    )
    config = _config(
        [
            WorkspaceRoleMapping(
                group="team", workspace_id=mapped_workspace.id, role="MEMBER"
            )
        ]
    )

    sync_workspace_memberships(user, ["team"], config)

    # The unrelated membership is untouched (additive only).
    assert WorkspaceUser.objects.filter(user=user, workspace=other_workspace).exists()
    assert WorkspaceUser.objects.filter(user=user, workspace=mapped_workspace).exists()
