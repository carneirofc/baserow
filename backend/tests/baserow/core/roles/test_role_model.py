import pytest

from baserow.core.models import Operation
from baserow.core.operations import (
    ReadWorkspaceOperationType,
    UpdateWorkspaceOperationType,
)
from baserow.core.roles.models import Role


@pytest.mark.django_db
def test_role_is_scoped_to_a_workspace(data_fixture):
    workspace = data_fixture.create_workspace()
    other_workspace = data_fixture.create_workspace()

    role = Role.objects.create(workspace=workspace, name="Viewer")

    assert role.workspace_id == workspace.id
    assert list(workspace.roles.all()) == [role]
    assert list(other_workspace.roles.all()) == []


@pytest.mark.django_db
def test_role_operations_can_be_assigned_and_are_optional(data_fixture):
    workspace = data_fixture.create_workspace()
    read_operation = Operation.objects.get(name=ReadWorkspaceOperationType.type)
    update_operation = Operation.objects.get(name=UpdateWorkspaceOperationType.type)

    role = Role.objects.create(workspace=workspace, name="Viewer")
    assert list(role.operations.all()) == []

    role.operations.add(read_operation, update_operation)

    assert set(role.operations.values_list("name", flat=True)) == {
        ReadWorkspaceOperationType.type,
        UpdateWorkspaceOperationType.type,
    }
    assert list(read_operation.roles.all()) == [role]
