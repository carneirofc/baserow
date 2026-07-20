from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin


class Role(CreatedAndUpdatedOnMixin, models.Model):
    """
    A workspace-scoped, custom set of operations a `WorkspaceUser` is allowed to
    perform. Assigning a role to a `WorkspaceUser` restricts that member to only
    the operations granted by the role, gated by `GranularRolePermissionManagerType`.
    """

    workspace = models.ForeignKey(
        "core.Workspace",
        on_delete=models.CASCADE,
        related_name="roles",
        help_text="The workspace this role belongs to.",
    )
    name = models.CharField(max_length=255)
    operations = models.ManyToManyField(
        "core.Operation",
        related_name="roles",
        blank=True,
        help_text="The operations a WorkspaceUser assigned this role is allowed "
        "to perform.",
    )

    class Meta:
        ordering = ("id",)
