"""
Parsing and validation of the env-configured OIDC providers.

Providers are declared entirely through the ``BASEROW_OIDC_PROVIDERS`` environment
variable as a JSON list. The configuration is the source of truth; a lightweight
database row (see ``OIDCAuthProviderModel``) is upserted per provider only to anchor
the user linkage that the shared auth-provider machinery relies on.

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
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

DEFAULT_SCOPES = ["openid", "email", "profile"]

# A provider name is used in URLs and as the database anchor key, so keep it to a
# conservative, url-safe slug.
_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


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
    # The claim (in the ID token / userinfo) that holds the user's group memberships.
    groups_claim: str = "groups"
    # IdP groups whose members are granted Baserow global staff.
    staff_groups: List[str] = field(default_factory=list)
    # IdP groups whose members are granted Baserow global superuser.
    superuser_groups: List[str] = field(default_factory=list)

    @property
    def syncs_global_roles(self) -> bool:
        """True when this provider maps any IdP group to a global role."""

        return bool(self.staff_groups) or bool(self.superuser_groups)


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


def _validate_provider(provider: Any, index: int) -> OIDCProviderConfig:
    if not isinstance(provider, dict):
        raise ImproperlyConfigured(
            f"BASEROW_OIDC_PROVIDERS[{index}]: each provider must be a JSON object."
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
    groups_claim = provider.get("groups_claim", "groups")
    for claim_key, claim_value in (
        ("email_claim", email_claim),
        ("name_claim", name_claim),
        ("groups_claim", groups_claim),
    ):
        if not isinstance(claim_value, str) or not claim_value.strip():
            raise ImproperlyConfigured(
                f"BASEROW_OIDC_PROVIDERS[{index}]: '{claim_key}' must be a non-empty "
                f"string."
            )

    staff_groups = _string_list(provider, "staff_groups", index)
    superuser_groups = _string_list(provider, "superuser_groups", index)

    return OIDCProviderConfig(
        name=name,
        display_name=display_name.strip(),
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        email_claim=email_claim.strip(),
        name_claim=name_claim.strip(),
        groups_claim=groups_claim.strip(),
        staff_groups=staff_groups,
        superuser_groups=superuser_groups,
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
