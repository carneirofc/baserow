"""
Parsing and validation of the env-declared workspace roles.

Roles are declared through the ``BASEROW_ROLES`` environment variable as a JSON list.
The configuration is the source of truth; the matching ``Role`` rows are reconciled from
it (see ``baserow.core.roles.handler.sync_declared_roles``) so an operator can grant an
OIDC group a granular role without any UI.

The env var is parsed and structurally validated once, at startup, so that an invalid
configuration fails fast with a clear error instead of surfacing at login time. Checks
that need the database - the workspace existing, the operation names being registered -
are deferred to reconcile time.

IMPORTANT: this module is imported from ``config/settings/base.py`` while Django settings
are still being evaluated (before the app registry is ready). Keep it import-light -
stdlib and ``django.core.exceptions`` only - and never import Django models or
``controllable_operations`` here, or settings evaluation will break.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class RoleConfig:
    """A single env-declared workspace role."""

    workspace_id: int
    name: str
    operations: List[str]


def _validate_role(role: Any, index: int) -> RoleConfig:
    prefix = f"BASEROW_ROLES[{index}]"

    if not isinstance(role, dict):
        raise ImproperlyConfigured(f"{prefix}: each role must be a JSON object.")

    workspace = role.get("workspace")
    # bool is a subclass of int; reject it explicitly.
    if not isinstance(workspace, int) or isinstance(workspace, bool):
        raise ImproperlyConfigured(
            f"{prefix}: 'workspace' must be an integer workspace id."
        )

    name = role.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ImproperlyConfigured(f"{prefix}: 'name' must be a non-empty string.")

    operations = role.get("operations", [])
    if not isinstance(operations, list) or not all(
        isinstance(operation, str) and operation.strip() for operation in operations
    ):
        raise ImproperlyConfigured(
            f"{prefix}: 'operations' must be a list of non-empty strings."
        )

    return RoleConfig(
        workspace_id=workspace,
        name=name.strip(),
        operations=[operation.strip() for operation in operations],
    )


def parse_roles_env(raw: Optional[str]) -> List[RoleConfig]:
    """
    Parses and validates the ``BASEROW_ROLES`` environment value.

    :param raw: The raw JSON string (or None / empty when unset).
    :raises ImproperlyConfigured: When the JSON is invalid or a role is malformed.
    :return: The list of validated role configs (possibly empty).
    """

    if raw is None or not raw.strip():
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImproperlyConfigured(f"BASEROW_ROLES is not valid JSON: {exc}.") from exc

    if not isinstance(data, list):
        raise ImproperlyConfigured("BASEROW_ROLES must be a JSON list of role objects.")

    roles: List[RoleConfig] = []
    seen: Dict[int, set] = {}
    for index, role in enumerate(data):
        config = _validate_role(role, index)
        names = seen.setdefault(config.workspace_id, set())
        if config.name in names:
            raise ImproperlyConfigured(
                f"BASEROW_ROLES: duplicate role '{config.name}' for workspace "
                f"{config.workspace_id}."
            )
        names.add(config.name)
        roles.append(config)

    return roles


def get_declared_roles() -> List[RoleConfig]:
    """Returns the declared roles from settings."""

    from django.conf import settings

    return list(getattr(settings, "BASEROW_ROLES", []))
