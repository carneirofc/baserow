"""
Mapping OIDC group membership to Baserow global roles.

Group membership is reconciled on every login: a user in a mapped staff/superuser
group is granted the role, and a user no longer in the group has it revoked. Because
this only runs during an OIDC login, a local break-glass admin (who never logs in via
OIDC) is never touched.
"""

from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser

from baserow.core.sso.oidc.config import OIDCProviderConfig


def extract_groups(
    config: OIDCProviderConfig,
    id_token_claims: Dict[str, Any],
    userinfo: Dict[str, Any],
) -> List[str]:
    """
    Returns the union of the group names found under the configured groups claim in
    both the ID token and the userinfo response.
    """

    groups = set()
    for source in (id_token_claims, userinfo):
        value = source.get(config.groups_claim)
        if isinstance(value, list):
            groups.update(str(item) for item in value)
        elif isinstance(value, str) and value:
            groups.add(value)
    return sorted(groups)


def sync_global_roles(
    user: AbstractUser, groups: List[str], config: OIDCProviderConfig
) -> None:
    """
    Reconciles ``is_staff`` / ``is_superuser`` from the user's current groups.

    Only the dimensions the provider actually maps are reconciled: an instance that
    configures no staff/superuser groups leaves both flags untouched. A superuser is
    also kept as staff so they retain admin access.
    """

    if not config.syncs_global_roles:
        return

    group_set = set(groups)
    changed_fields = []

    is_superuser = user.is_superuser
    if config.superuser_groups:
        is_superuser = bool(group_set.intersection(config.superuser_groups))
        if is_superuser != user.is_superuser:
            user.is_superuser = is_superuser
            changed_fields.append("is_superuser")

    if config.staff_groups:
        is_staff = bool(group_set.intersection(config.staff_groups))
        # Superuser implies staff so admin access is retained.
        is_staff = is_staff or is_superuser
        if is_staff != user.is_staff:
            user.is_staff = is_staff
            changed_fields.append("is_staff")
    elif is_superuser and not user.is_staff:
        user.is_staff = True
        changed_fields.append("is_staff")

    if changed_fields:
        user.save(update_fields=changed_fields)
