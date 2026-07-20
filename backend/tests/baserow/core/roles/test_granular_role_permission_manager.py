import pytest

from baserow.core.models import Operation
from baserow.core.operations import (
    ListApplicationsWorkspaceOperationType,
    ReadWorkspaceOperationType,
    UpdateWorkspaceOperationType,
)
from baserow.core.roles.exceptions import OperationNotAllowedByRoleError
from baserow.core.roles.models import Role
from baserow.core.roles.permission_manager import GranularRolePermissionManagerType
from baserow.core.types import PermissionCheck


@pytest.fixture
def read_operation():
    return Operation.objects.get(name=ReadWorkspaceOperationType.type)


@pytest.fixture
def role_granting_read(data_fixture, read_operation):
    def make(workspace):
        role = Role.objects.create(workspace=workspace, name="Reader")
        role.operations.add(read_operation)
        return role

    return make


@pytest.mark.django_db
def test_check_multiple_permissions_returns_nothing_without_a_workspace(data_fixture):
    user = data_fixture.create_user()
    perm_manager = GranularRolePermissionManagerType()

    result = perm_manager.check_multiple_permissions(
        [PermissionCheck(user, ReadWorkspaceOperationType.type, None)], workspace=None
    )

    assert result == {}


@pytest.mark.django_db
def test_check_multiple_permissions_ignores_non_controllable_operations(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    perm_manager = GranularRolePermissionManagerType()

    check = PermissionCheck(
        user, ListApplicationsWorkspaceOperationType.type, workspace
    )
    result = perm_manager.check_multiple_permissions([check], workspace=workspace)

    assert result == {}


@pytest.mark.django_db
def test_check_multiple_permissions_leaves_non_members_undetermined(data_fixture):
    workspace = data_fixture.create_workspace()
    outsider = data_fixture.create_user()
    perm_manager = GranularRolePermissionManagerType()

    check = PermissionCheck(outsider, ReadWorkspaceOperationType.type, workspace)
    result = perm_manager.check_multiple_permissions([check], workspace=workspace)

    assert result == {}


@pytest.mark.django_db
def test_check_multiple_permissions_leaves_admins_undetermined(data_fixture):
    workspace = data_fixture.create_workspace()
    admin = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=admin, permissions="ADMIN"
    )
    perm_manager = GranularRolePermissionManagerType()

    check = PermissionCheck(admin, ReadWorkspaceOperationType.type, workspace)
    result = perm_manager.check_multiple_permissions([check], workspace=workspace)

    assert result == {}


@pytest.mark.django_db
def test_check_multiple_permissions_leaves_roleless_members_undetermined(
    data_fixture,
):
    workspace = data_fixture.create_workspace()
    member = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER"
    )
    perm_manager = GranularRolePermissionManagerType()

    check = PermissionCheck(member, ReadWorkspaceOperationType.type, workspace)
    result = perm_manager.check_multiple_permissions([check], workspace=workspace)

    assert result == {}


@pytest.mark.django_db
def test_check_multiple_permissions_grants_operation_allowed_by_role(
    data_fixture, role_granting_read
):
    workspace = data_fixture.create_workspace()
    member = data_fixture.create_user()
    role = role_granting_read(workspace)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER", role=role
    )
    perm_manager = GranularRolePermissionManagerType()

    check = PermissionCheck(member, ReadWorkspaceOperationType.type, workspace)
    result = perm_manager.check_multiple_permissions([check], workspace=workspace)

    assert result == {check: True}


@pytest.mark.django_db
def test_check_multiple_permissions_denies_operation_not_allowed_by_role(
    data_fixture, role_granting_read
):
    workspace = data_fixture.create_workspace()
    member = data_fixture.create_user()
    role = role_granting_read(workspace)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER", role=role
    )
    perm_manager = GranularRolePermissionManagerType()

    check = PermissionCheck(member, UpdateWorkspaceOperationType.type, workspace)
    result = perm_manager.check_multiple_permissions([check], workspace=workspace)

    assert isinstance(result[check], OperationNotAllowedByRoleError)


@pytest.mark.django_db
def test_get_permissions_object_returns_none_without_a_workspace(data_fixture):
    user = data_fixture.create_user()

    result = GranularRolePermissionManagerType().get_permissions_object(
        user, workspace=None
    )

    assert result is None


@pytest.mark.django_db
def test_get_permissions_object_returns_none_for_non_members(data_fixture):
    workspace = data_fixture.create_workspace()
    outsider = data_fixture.create_user()

    result = GranularRolePermissionManagerType().get_permissions_object(
        outsider, workspace=workspace
    )

    assert result is None


@pytest.mark.django_db
def test_get_permissions_object_has_no_allowed_operations_for_roleless_member(
    data_fixture,
):
    workspace = data_fixture.create_workspace()
    member = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER"
    )

    result = GranularRolePermissionManagerType().get_permissions_object(
        member, workspace=workspace
    )

    assert result["allowed_operations"] is None


@pytest.mark.django_db
def test_get_permissions_object_has_no_allowed_operations_for_admin_with_role(
    data_fixture, role_granting_read
):
    workspace = data_fixture.create_workspace()
    admin = data_fixture.create_user()
    role = role_granting_read(workspace)
    data_fixture.create_user_workspace(
        workspace=workspace, user=admin, permissions="ADMIN", role=role
    )

    result = GranularRolePermissionManagerType().get_permissions_object(
        admin, workspace=workspace
    )

    assert result["allowed_operations"] is None


@pytest.mark.django_db
def test_get_permissions_object_lists_the_roles_operations_for_a_member(
    data_fixture, role_granting_read
):
    workspace = data_fixture.create_workspace()
    member = data_fixture.create_user()
    role = role_granting_read(workspace)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER", role=role
    )

    result = GranularRolePermissionManagerType().get_permissions_object(
        member, workspace=workspace
    )

    assert result["allowed_operations"] == [ReadWorkspaceOperationType.type]
