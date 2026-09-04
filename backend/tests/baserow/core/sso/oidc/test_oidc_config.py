import json

from django.core.exceptions import ImproperlyConfigured

import pytest

from baserow.core.sso.oidc.config import (
    DEFAULT_SCOPES,
    OIDCProviderConfig,
    parse_oidc_providers_env,
)

VALID_PROVIDER = {
    "name": "keycloak",
    "display_name": "Keycloak",
    "issuer": "http://localhost:8080/realms/master",
    "client_id": "baserow",
    "client_secret": "secret",
}


def _env(*providers):
    return json.dumps(list(providers))


def test_empty_env_returns_no_providers():
    assert parse_oidc_providers_env(None) == []
    assert parse_oidc_providers_env("") == []
    assert parse_oidc_providers_env("   ") == []


def test_valid_provider_is_parsed_with_defaults():
    providers = parse_oidc_providers_env(_env(VALID_PROVIDER))

    assert len(providers) == 1
    provider = providers[0]
    assert isinstance(provider, OIDCProviderConfig)
    assert provider.name == "keycloak"
    assert provider.display_name == "Keycloak"
    assert provider.issuer == "http://localhost:8080/realms/master"
    assert provider.client_id == "baserow"
    assert provider.client_secret == "secret"
    assert provider.scopes == DEFAULT_SCOPES
    assert provider.email_claim == "email"
    assert provider.name_claim == "name"


def test_display_name_defaults_to_name():
    provider = dict(VALID_PROVIDER)
    del provider["display_name"]

    providers = parse_oidc_providers_env(_env(provider))

    assert providers[0].display_name == "keycloak"


def test_invalid_json_fails_fast():
    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env("{not json")


def test_non_list_fails_fast():
    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(json.dumps(VALID_PROVIDER))


@pytest.mark.parametrize("missing", ["name", "issuer", "client_id", "client_secret"])
def test_missing_required_field_fails_fast(missing):
    provider = dict(VALID_PROVIDER)
    del provider[missing]

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_invalid_name_fails_fast():
    provider = dict(VALID_PROVIDER, name="not a slug!")

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_invalid_issuer_fails_fast():
    provider = dict(VALID_PROVIDER, issuer="not-a-url")

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_scopes_must_include_openid():
    provider = dict(VALID_PROVIDER, scopes=["email", "profile"])

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_duplicate_names_fail_fast():
    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(VALID_PROVIDER, VALID_PROVIDER))


def test_multiple_providers_parsed():
    second = dict(VALID_PROVIDER, name="google", display_name="Google")

    providers = parse_oidc_providers_env(_env(VALID_PROVIDER, second))

    assert [p.name for p in providers] == ["keycloak", "google"]


def test_role_mapping_defaults():
    provider = parse_oidc_providers_env(_env(VALID_PROVIDER))[0]

    # The default claim is Keycloak's own, with the client id substituted in.
    assert provider.roles_claim == "resource_access.baserow.roles"
    assert provider.staff_roles == []
    assert provider.superuser_roles == []
    assert provider.syncs_global_roles is False
    assert provider.mapped_roles == set()
    assert provider.declares_any_mapping is False


def test_roles_claim_substitutes_the_client_id():
    provider = dict(
        VALID_PROVIDER,
        client_id="my-client",
        roles_claim="resource_access.${client_id}.roles",
    )

    config = parse_oidc_providers_env(_env(provider))[0]

    assert config.roles_claim == "resource_access.my-client.roles"


def test_role_mapping_parsed():
    provider = dict(
        VALID_PROVIDER,
        roles_claim="realm_access.roles",
        staff_roles=["staff", "admins"],
        superuser_roles=["superadmins"],
    )

    config = parse_oidc_providers_env(_env(provider))[0]

    assert config.roles_claim == "realm_access.roles"
    assert config.staff_roles == ["staff", "admins"]
    assert config.superuser_roles == ["superadmins"]
    assert config.syncs_global_roles is True
    assert config.declares_any_mapping is True


@pytest.mark.parametrize("key", ["staff_roles", "superuser_roles"])
def test_role_lists_must_be_lists_of_strings(key):
    provider = dict(VALID_PROVIDER, **{key: "not-a-list"})

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_roles_claim_must_be_non_empty_string():
    provider = dict(VALID_PROVIDER, roles_claim="")

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_workspace_mappings_defaults_to_empty():
    provider = parse_oidc_providers_env(_env(VALID_PROVIDER))[0]

    assert provider.workspace_mappings == []
    assert provider.syncs_workspace_memberships is False


def test_workspace_mappings_parsed():
    provider = dict(
        VALID_PROVIDER,
        workspace_mappings=[
            {"client_role": "team-a", "workspace": 7, "permissions": "ADMIN"},
            {"client_role": "team-b", "workspace": 9, "permissions": "MEMBER"},
        ],
    )

    config = parse_oidc_providers_env(_env(provider))[0]

    assert config.syncs_workspace_memberships is True
    assert config.workspace_mappings[0].client_role == "team-a"
    assert config.workspace_mappings[0].workspace_id == 7
    assert config.workspace_mappings[0].permissions == "ADMIN"
    assert config.workspace_mappings[0].role is None
    assert config.workspace_mappings[1].workspace_id == 9
    assert config.workspace_mappings[1].permissions == "MEMBER"
    assert config.mapped_roles == {"team-a", "team-b"}


def test_workspace_mapping_can_name_a_granular_role():
    provider = dict(
        VALID_PROVIDER,
        workspace_mappings=[
            {
                "client_role": "analyst",
                "workspace": 7,
                "permissions": "MEMBER",
                "role": "analyst",
            }
        ],
    )

    config = parse_oidc_providers_env(_env(provider))[0]

    assert config.workspace_mappings[0].role == "analyst"


def test_granular_role_is_refused_alongside_admin():
    # Workspace admins bypass the granular role permission manager, so the pair would
    # silently grant unrestricted access.
    provider = dict(
        VALID_PROVIDER,
        workspace_mappings=[
            {
                "client_role": "analyst",
                "workspace": 7,
                "permissions": "ADMIN",
                "role": "analyst",
            }
        ],
    )

    with pytest.raises(ImproperlyConfigured, match="not restricted by a role"):
        parse_oidc_providers_env(_env(provider))


@pytest.mark.parametrize(
    "key,replacement",
    [
        ("groups_claim", "roles_claim"),
        ("staff_groups", "staff_roles"),
        ("superuser_groups", "superuser_roles"),
    ],
)
def test_retired_provider_keys_fail_fast(key, replacement):
    # Ignoring one would silently drop the access it used to grant.
    provider = dict(VALID_PROVIDER, **{key: ["a"] if key != "groups_claim" else "a"})

    with pytest.raises(ImproperlyConfigured, match=replacement):
        parse_oidc_providers_env(_env(provider))


def test_retired_mapping_group_key_fails_fast():
    provider = dict(
        VALID_PROVIDER,
        workspace_mappings=[
            {"group": "team-a", "workspace": 7, "permissions": "MEMBER"}
        ],
    )

    with pytest.raises(ImproperlyConfigured, match="client_role"):
        parse_oidc_providers_env(_env(provider))


def test_retired_mapping_role_semantics_fail_fast():
    # 'role' used to hold ADMIN/MEMBER; it now names a granular role.
    provider = dict(
        VALID_PROVIDER,
        workspace_mappings=[{"client_role": "team-a", "workspace": 7, "role": "ADMIN"}],
    )

    with pytest.raises(ImproperlyConfigured, match="rename it to 'permissions'"):
        parse_oidc_providers_env(_env(provider))


def test_strict_membership_defaults_false_and_parses():
    assert parse_oidc_providers_env(_env(VALID_PROVIDER))[0].strict_membership is False

    provider = dict(VALID_PROVIDER, strict_membership=True)
    assert parse_oidc_providers_env(_env(provider))[0].strict_membership is True


def test_strict_membership_must_be_boolean():
    provider = dict(VALID_PROVIDER, strict_membership="yes")

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


@pytest.mark.parametrize(
    "mapping",
    [
        {"client_role": "team", "workspace": 1},  # missing permissions
        # permissions not allowed
        {"client_role": "team", "workspace": 1, "permissions": "VIEWER"},
        # workspace not an int
        {"client_role": "team", "workspace": "1", "permissions": "ADMIN"},
        # bool rejected
        {"client_role": "team", "workspace": True, "permissions": "ADMIN"},
        {"workspace": 1, "permissions": "ADMIN"},  # missing client_role
        # granular role must be a non-empty string
        {"client_role": "team", "workspace": 1, "permissions": "MEMBER", "role": ""},
        "not-an-object",
    ],
)
def test_invalid_workspace_mapping_fails_fast(mapping):
    provider = dict(VALID_PROVIDER, workspace_mappings=[mapping])

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))
