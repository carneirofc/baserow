"""
Parsing and validation of the env-configured OIDC providers.

Providers are declared entirely through the ``BASEROW_OIDC_PROVIDERS`` environment
variable as a JSON list. The configuration is the source of truth; a lightweight
database row (see ``OIDCAuthProviderModel``) is upserted per provider only to anchor
the user linkage that the shared auth-provider machinery relies on.

Access is expressed in terms of the IdP's client roles: which of them grant global
staff/superuser, and which grant a membership (and optionally a granular role) in a
workspace. A provider that maps any client role refuses users carrying none of them.

The env var is parsed and structurally validated once, at startup, so that an invalid
configuration fails fast with a clear error instead of surfacing at login time. Network
reachable checks (OIDC discovery) are intentionally deferred to login time.

IMPORTANT: this module is imported from ``config/settings/base.py`` while Django
settings are still being evaluated (before the app registry is ready). Keep it
import-light — stdlib and ``django.core.exceptions`` only — and never import Django
models or ``requests_oauthlib`` here, or settings evaluation will break.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

DEFAULT_SCOPES = ["openid", "email", "profile"]

# Keycloak/RHBK nests a client's roles under this claim, substituting the client id.
# Matching their built-in mapper's default lets an operator paste the claim name in.
DEFAULT_ROLES_CLAIM = "resource_access.${client_id}.roles"
CLIENT_ID_PLACEHOLDER = "${client_id}"

# The workspace permissions an operator may map an IdP client role to.
WORKSPACE_PERMISSIONS_ADMIN = "ADMIN"
WORKSPACE_PERMISSIONS_MEMBER = "MEMBER"
ALLOWED_WORKSPACE_PERMISSIONS = (
    WORKSPACE_PERMISSIONS_ADMIN,
    WORKSPACE_PERMISSIONS_MEMBER,
)

# Config keys retired by the move to client roles, mapped to their replacement. They are
# refused rather than ignored: silently dropping `staff_groups` would revoke every admin.
RETIRED_PROVIDER_KEYS = {
    "groups_claim": "roles_claim",
    "staff_groups": "staff_roles",
    "superuser_groups": "superuser_roles",
}
RETIRED_MAPPING_KEYS = {"group": "client_role"}

# A provider name is used in URLs and as the database anchor key, so keep it to a
# conservative, url-safe slug.
_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class WorkspaceMapping:
    """Maps one IdP client role to a membership in one Baserow workspace."""

    client_role: str
    workspace_id: int
    permissions: str
    # The name of a `core.Role` in the same workspace, restricting the member to that
    # role's operations. None means today's unrestricted full-member access. Resolved at
    # login time, since the database is not reachable while settings are evaluated.
    role: Optional[str] = None


@dataclass(frozen=True)
class OIDCProviderConfig:
    """A single env-declared OIDC provider."""

    name: str
    display_name: str
    issuer: str
    client_id: str
    client_secret: str
    scopes: List[str] = field(default_factory=lambda: list(DEFAULT_SCOPES))
    # The claim (in the ID token / userinfo) that holds the user's email.
    email_claim: str = "email"
    # The claim that holds the user's display name.
    name_claim: str = "name"
    # The (possibly dotted) claim path that holds the user's IdP roles.
    roles_claim: str = DEFAULT_ROLES_CLAIM
    # IdP client roles whose holders are granted Baserow global staff.
    staff_roles: List[str] = field(default_factory=list)
    # IdP client roles whose holders are granted Baserow global superuser.
    superuser_roles: List[str] = field(default_factory=list)
    # Maps IdP client roles to workspace memberships.
    workspace_mappings: List[WorkspaceMapping] = field(default_factory=list)
    # When True, SSO-granted workspace memberships are revoked once the user loses the
    # mapped client role. Manually-added memberships are never touched.
    strict_membership: bool = False

    @property
    def syncs_global_roles(self) -> bool:
        """True when this provider maps any IdP client role to a global role."""

        return bool(self.staff_roles) or bool(self.superuser_roles)

    @property
    def syncs_workspace_memberships(self) -> bool:
        """True when this provider maps any IdP client role to a membership."""

        return bool(self.workspace_mappings)

    @property
    def mapped_roles(self) -> Set[str]:
        """Every IdP client role this provider grants some access to."""

        return (
            set(self.staff_roles)
            | set(self.superuser_roles)
            | {mapping.client_role for mapping in self.workspace_mappings}
        )

    @property
    def declares_any_mapping(self) -> bool:
        """
        True when this provider derives any access from client roles, and a user
        carrying none of them must therefore be refused.
        """

        return bool(self.mapped_roles)


def _require_str(provider: Dict[str, Any], key: str, index: int) -> str:
    value = provider.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: '{key}' is required and must be a "
            f"non-empty string."
        )
    return value.strip()


def _string_list(provider: Dict[str, Any], key: str, index: int) -> List[str]:
    """Validates an optional list-of-strings provider field, defaulting to []."""

    value = provider.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: '{key}' must be a list of strings."
        )
    return value


def _reject_retired_keys(
    mapping: Dict[str, Any], retired: Dict[str, str], prefix: str
) -> None:
    """
    Fails fast on a key from the pre-client-role configuration format.

    Ignoring one would silently drop the access it used to grant, so an operator
    upgrading is told exactly which key to rename.
    """

    for old_key, new_key in retired.items():
        if old_key in mapping:
            raise ImproperlyConfigured(
                f"{prefix}: '{old_key}' is no longer supported; access is now derived "
                f"from IdP client roles. Rename it to '{new_key}'."
            )


def _workspace_mappings(provider: Dict[str, Any], index: int) -> List[WorkspaceMapping]:
    """Validates the optional ``workspace_mappings`` provider field."""

    raw_mappings = provider.get("workspace_mappings", [])
    if not isinstance(raw_mappings, list):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'workspace_mappings' must be a list."
        )

    mappings = []
    for position, mapping in enumerate(raw_mappings):
        prefix = f"BASEROW_OIDC_PROVIDERS[{index}].workspace_mappings[{position}]"
        if not isinstance(mapping, dict):
            raise ImproperlyConfigured(f"{prefix}: must be a JSON object.")

        _reject_retired_keys(mapping, RETIRED_MAPPING_KEYS, prefix)
        if (
            "permissions" not in mapping
            and mapping.get("role") in ALLOWED_WORKSPACE_PERMISSIONS
        ):
            # 'role' used to hold ADMIN/MEMBER; it now names a granular `core.Role`.
            raise ImproperlyConfigured(
                f"{prefix}: 'role' no longer holds "
                f"{list(ALLOWED_WORKSPACE_PERMISSIONS)} — rename it to 'permissions'. "
                f"'role' now names a role declared in BASEROW_ROLES."
            )

        client_role = mapping.get("client_role")
        if not isinstance(client_role, str) or not client_role.strip():
            raise ImproperlyConfigured(
                f"{prefix}: 'client_role' must be a non-empty string."
            )

        workspace = mapping.get("workspace")
        # bool is a subclass of int; reject it explicitly.
        if not isinstance(workspace, int) or isinstance(workspace, bool):
            raise ImproperlyConfigured(
                f"{prefix}: 'workspace' must be an integer workspace id."
            )

        permissions = mapping.get("permissions")
        if permissions not in ALLOWED_WORKSPACE_PERMISSIONS:
            raise ImproperlyConfigured(
                f"{prefix}: 'permissions' must be one of "
                f"{list(ALLOWED_WORKSPACE_PERMISSIONS)}."
            )

        role = mapping.get("role")
        if role is not None:
            if not isinstance(role, str) or not role.strip():
                raise ImproperlyConfigured(
                    f"{prefix}: 'role' must be a non-empty string when provided."
                )
            role = role.strip()
            if permissions == WORKSPACE_PERMISSIONS_ADMIN:
                # Workspace admins bypass the granular role permission manager, so the
                # combination would silently grant unrestricted access.
                raise ImproperlyConfigured(
                    f"{prefix}: 'role' cannot be combined with permissions "
                    f"'{WORKSPACE_PERMISSIONS_ADMIN}', because workspace admins are "
                    f"not restricted by a role. Use "
                    f"'{WORKSPACE_PERMISSIONS_MEMBER}'."
                )

        mappings.append(
            WorkspaceMapping(
                client_role=client_role.strip(),
                workspace_id=workspace,
                permissions=permissions,
                role=role,
            )
        )
    return mappings


def _validate_provider(provider: Any, index: int) -> OIDCProviderConfig:
    if not isinstance(provider, dict):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: each provider must be a JSON object."
        )

    _reject_retired_keys(
        provider, RETIRED_PROVIDER_KEYS, f"BASEROW_OIDC_PROVIDERS[{index}]"
    )

    name = _require_str(provider, "name", index)
    if not _NAME_RE.match(name):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'name' ('{name}') may only contain "
            f"letters, digits, hyphens and underscores."
        )

    issuer = _require_str(provider, "issuer", index)
    parsed_issuer = urlparse(issuer)
    if parsed_issuer.scheme not in ("http", "https") or not parsed_issuer.netloc:
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'issuer' must be a valid http(s) URL."
        )

    client_id = _require_str(provider, "client_id", index)
    client_secret = _require_str(provider, "client_secret", index)

    display_name = provider.get("display_name") or name
    if not isinstance(display_name, str) or not display_name.strip():
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'display_name' must be a non-empty "
            f"string when provided."
        )

    scopes = provider.get("scopes", list(DEFAULT_SCOPES))
    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'scopes' must be a list of strings."
        )
    if "openid" not in scopes:
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'scopes' must include 'openid'."
        )

    email_claim = provider.get("email_claim", "email")
    name_claim = provider.get("name_claim", "name")
    roles_claim = provider.get("roles_claim", DEFAULT_ROLES_CLAIM)
    for claim_key, claim_value in (
        ("email_claim", email_claim),
        ("name_claim", name_claim),
        ("roles_claim", roles_claim),
    ):
        if not isinstance(claim_value, str) or not claim_value.strip():
            raise ImproperlyConfigured(
                f"BASEROW_OIDC_PROVIDERS[{index}]: '{claim_key}' must be a non-empty "
                f"string."
            )

    # Keycloak writes its mapper claim names with a `${client_id}` placeholder, so the
    # operator can paste one in verbatim.
    roles_claim = roles_claim.strip().replace(CLIENT_ID_PLACEHOLDER, client_id)

    staff_roles = _string_list(provider, "staff_roles", index)
    superuser_roles = _string_list(provider, "superuser_roles", index)
    workspace_mappings = _workspace_mappings(provider, index)

    strict_membership = provider.get("strict_membership", False)
    if not isinstance(strict_membership, bool):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: 'strict_membership' must be a boolean."
        )

    return OIDCProviderConfig(
        name=name,
        display_name=display_name.strip(),
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        email_claim=email_claim.strip(),
        name_claim=name_claim.strip(),
        roles_claim=roles_claim,
        staff_roles=staff_roles,
        superuser_roles=superuser_roles,
        workspace_mappings=workspace_mappings,
        strict_membership=strict_membership,
    )


def parse_oidc_providers_env(raw: Optional[str]) -> List[OIDCProviderConfig]:
    """
    Parses and validates the ``BASEROW_OIDC_PROVIDERS`` environment value.

    :param raw: The raw JSON string (or None / empty when unset).
    :raises ImproperlyConfigured: When the JSON is invalid or a provider is malformed.
    :return: The list of validated provider configs (possibly empty).
    """

    if raw is None or not raw.strip():
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS is not valid JSON: {exc}."
        ) from exc

    if not isinstance(data, list):
        raise ImproperlyConfigured(
            "BASEROW_OIDC_PROVIDERS must be a JSON list of provider objects."
        )

    providers: List[OIDCProviderConfig] = []
    seen_names = set()
    for index, provider in enumerate(data):
        config = _validate_provider(provider, index)
        if config.name in seen_names:
            raise ImproperlyConfigured(
                f"BASEROW_OIDC_PROVIDERS: duplicate provider name '{config.name}'."
            )
        seen_names.add(config.name)
        providers.append(config)

    return providers


def get_oidc_providers() -> List[OIDCProviderConfig]:
    """Returns the configured OIDC providers from settings."""

    from django.conf import settings

    return list(getattr(settings, "BASEROW_OIDC_PROVIDERS", []))


def get_oidc_provider(name: str) -> Optional[OIDCProviderConfig]:
    """Returns the configured OIDC provider with the given name, or None."""

    for provider in get_oidc_providers():
        if provider.name == name:
            return provider
    return None
