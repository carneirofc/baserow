from collections import defaultdict

from baserow.core.handler import CoreHandler
from baserow.core.models import WORKSPACE_USER_PERMISSION_ADMIN, WorkspaceUser
from baserow.core.registries import PermissionManagerType
from baserow.core.subjects import UserSubjectType

from .controllable_operations import CONTROLLABLE_OPERATION_TYPES
from .exceptions import OperationNotAllowedByRoleError


class GranularRolePermissionManagerType(PermissionManagerType):
    """
    Gates the curated set of `CONTROLLABLE_OPERATION_TYPES` behind a `WorkspaceUser`'s
    assigned `Role`, if any. ADMINs and members without a role assigned are left
    untouched so `WorkspaceMemberOnlyPermissionManagerType`/`BasicPermissionManagerType`
    keep deciding those checks, preserving today's behavior for everyone who isn't
    using this feature.
    """

    type = "granular_role"
    supported_actor_types = [UserSubjectType.type]

    def check_multiple_permissions(self, checks, workspace=None, include_trash=False):
        if workspace is None:
            return {}

        controllable_checks = [
            check
            for check in checks
            if check.operation_name in CONTROLLABLE_OPERATION_TYPES
        ]
        if not controllable_checks:
            return {}

        actors = {check.actor for check in controllable_checks}
        workspace_user_by_user_id = {
            workspace_user.user_id: workspace_user
            for workspace_user in CoreHandler().get_workspace_users(
                workspace, actors, include_trash=include_trash
            )
        }

        role_ids = {
            workspace_user.role_id
            for workspace_user in workspace_user_by_user_id.values()
            if workspace_user.role_id is not None
        }
        operations_by_role_id = defaultdict(set)
        if role_ids:
            for (
                role_id,
                operation_name,
            ) in WorkspaceUser.role.field.related_model.objects.filter(
                id__in=role_ids
            ).values_list("id", "operations__name"):
                operations_by_role_id[role_id].add(operation_name)

        result = {}
        for check in controllable_checks:
            workspace_user = workspace_user_by_user_id.get(check.actor.id)
            if workspace_user is None:
                # Not a member of this workspace: let `member` deny it.
                continue

            if workspace_user.permissions == WORKSPACE_USER_PERMISSION_ADMIN:
                continue

            if workspace_user.role_id is None:
                # No custom role: today's full-member access.
                continue

            if check.operation_name in operations_by_role_id[workspace_user.role_id]:
                result[check] = True
            else:
                result[check] = OperationNotAllowedByRoleError(
                    check.actor,
                    workspace,
                    workspace_user.role_id,
                    check.operation_name,
                )

        return result

    def get_permissions_object(self, actor, workspace=None):
        if workspace is None:
            return None

        try:
            workspace_user = WorkspaceUser.objects.select_related("role").get(
                user_id=actor.id, workspace_id=workspace.id
            )
        except WorkspaceUser.DoesNotExist:
            return None

        allowed_operations = None
        if (
            workspace_user.permissions != WORKSPACE_USER_PERMISSION_ADMIN
            and workspace_user.role_id is not None
        ):
            allowed_operations = list(
                workspace_user.role.operations.values_list("name", flat=True)
            )

        return {
            "controllable_operations": list(CONTROLLABLE_OPERATION_TYPES),
            "allowed_operations": allowed_operations,
        }
