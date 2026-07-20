from baserow.core.exceptions import PermissionException


class OperationNotAllowedByRoleError(PermissionException):
    """
    Raised when a `WorkspaceUser` has a custom `Role` assigned that doesn't grant
    the requested operation.
    """

    def __init__(self, user, workspace, role, operation_name, *args, **kwargs):
        self.user = user
        self.workspace = workspace
        self.role = role
        self.operation_name = operation_name
        super().__init__(
            f"The user {user} with role {role} isn't allowed to perform "
            f"{operation_name} in {workspace}.",
            *args,
            **kwargs,
        )
