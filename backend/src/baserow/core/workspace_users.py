"""
Adding users that already have an account to a workspace.

With SSO the IdP only decides who may sign in; workspace admins then pick the members of
their workspace from the accounts that exist.
"""

from typing import Iterable, List

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet

from baserow.core.handler import CoreHandler
from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_MEMBER,
    Workspace,
    WorkspaceUser,
)
from baserow.core.operations import AddWorkspaceUsersWorkspaceOperationType

User = get_user_model()

CANDIDATE_SEARCH_MIN_LENGTH = 3
CANDIDATE_SEARCH_LIMIT = 20


class UsersNotFound(Exception):
    """Raised when some users to add don't exist, are deactivated or being deleted."""

    def __init__(self, user_ids: List[int]):
        self.user_ids = user_ids
        super().__init__(f"Users {user_ids} can't be added.")


def _addable_users() -> QuerySet:
    return User.objects.filter(is_active=True, profile__to_be_deleted=False)


class WorkspaceUsersService:
    def _check(self, actor: AbstractUser, workspace: Workspace):
        CoreHandler().check_permissions(
            actor,
            AddWorkspaceUsersWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

    def search_candidates(
        self, actor: AbstractUser, workspace: Workspace, search: str
    ) -> QuerySet:
        """
        Returns the accounts matching `search` by name or email that could be added to
        the workspace. A minimum search length keeps admins from listing every account
        of the instance.
        """

        self._check(actor, workspace)
        search = search.strip()
        if len(search) < CANDIDATE_SEARCH_MIN_LENGTH:
            return User.objects.none()

        return (
            _addable_users()
            .exclude(workspaceuser__workspace=workspace)
            .filter(Q(first_name__icontains=search) | Q(email__icontains=search))
            .order_by("first_name", "id")[:CANDIDATE_SEARCH_LIMIT]
        )

    def add_users(
        self,
        actor: AbstractUser,
        workspace: Workspace,
        user_ids: Iterable[int],
        permissions: str = WORKSPACE_USER_PERMISSION_MEMBER,
    ) -> List[WorkspaceUser]:
        """
        Adds the users to the workspace. Users that are already members keep their
        current permissions.

        :raises UsersNotFound: When any of the users can't be added; nothing is added.
        """

        self._check(actor, workspace)
        user_ids = set(user_ids)
        users = list(_addable_users().filter(id__in=user_ids).order_by("id"))
        missing = user_ids - {user.id for user in users}
        if missing:
            raise UsersNotFound(sorted(missing))

        handler = CoreHandler()
        return [
            handler.add_user_to_workspace(workspace, user, permissions=permissions)
            for user in users
        ]
