import pytest

from baserow.core.operations import (
    ListApplicationsWorkspaceOperationType,
    ReadWorkspaceOperationType,
    UpdateWorkspaceOperationType,
)
from baserow.core.roles.config import RoleConfig
from baserow.core.roles.handler import sync_declared_roles
from baserow.core.roles.models import Role


@pytest.mark.django_db
def test_creates_a_declared_role(data_fixture):
    workspace = data_fixture.create_workspace()

    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Editor",
                operations=[
                    ReadWorkspaceOperationType.type,
                    UpdateWorkspaceOperationType.type,
                ],
            )
        ]
    )

    role = Role.objects.get(workspace=workspace, name="Editor")
    assert set(role.operations.values_list("name", flat=True)) == {
        ReadWorkspaceOperationType.type,
        UpdateWorkspaceOperationType.type,
    }


@pytest.mark.django_db
def test_is_idempotent(data_fixture):
    workspace = data_fixture.create_workspace()
    configs = [
        RoleConfig(
            workspace_id=workspace.id,
            name="Reader",
            operations=[ReadWorkspaceOperationType.type],
        )
    ]

    sync_declared_roles(configs)
    sync_declared_roles(configs)

    assert Role.objects.filter(workspace=workspace, name="Reader").count() == 1


@pytest.mark.django_db
def test_updates_the_operation_set_of_an_existing_role(data_fixture):
    workspace = data_fixture.create_workspace()
    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Reader",
                operations=[
                    ReadWorkspaceOperationType.type,
                    UpdateWorkspaceOperationType.type,
                ],
            )
        ]
    )

    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Reader",
                operations=[ReadWorkspaceOperationType.type],
            )
        ]
    )

    role = Role.objects.get(workspace=workspace, name="Reader")
    assert list(role.operations.values_list("name", flat=True)) == [
        ReadWorkspaceOperationType.type
    ]


@pytest.mark.django_db
def test_unknown_workspace_is_skipped(data_fixture):
    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=999999,
                name="Editor",
                operations=[ReadWorkspaceOperationType.type],
            )
        ]
    )

    assert not Role.objects.filter(name="Editor").exists()


@pytest.mark.django_db
def test_uncontrollable_operation_is_skipped(data_fixture):
    # The operation exists, but is not part of CONTROLLABLE_OPERATION_TYPES, so a role
    # must not be able to gate it.
    workspace = data_fixture.create_workspace()

    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Editor",
                operations=[
                    ReadWorkspaceOperationType.type,
                    ListApplicationsWorkspaceOperationType.type,
                ],
            )
        ]
    )

    role = Role.objects.get(workspace=workspace, name="Editor")
    assert list(role.operations.values_list("name", flat=True)) == [
        ReadWorkspaceOperationType.type
    ]


@pytest.mark.django_db
def test_unregistered_operation_is_skipped(data_fixture):
    workspace = data_fixture.create_workspace()

    sync_declared_roles(
        [
            RoleConfig(
                workspace_id=workspace.id,
                name="Editor",
                operations=["does.not.exist"],
            )
        ]
    )

    role = Role.objects.get(workspace=workspace, name="Editor")
    assert role.operations.count() == 0


@pytest.mark.django_db
def test_undeclared_roles_are_left_alone(data_fixture):
    workspace = data_fixture.create_workspace()
    existing = Role.objects.create(workspace=workspace, name="Legacy")

    sync_declared_roles(
        [RoleConfig(workspace_id=workspace.id, name="Editor", operations=[])]
    )

    assert Role.objects.filter(id=existing.id).exists()


@pytest.mark.django_db
def test_no_declared_roles_is_a_no_op(data_fixture):
    sync_declared_roles([])

    assert not Role.objects.exists()
