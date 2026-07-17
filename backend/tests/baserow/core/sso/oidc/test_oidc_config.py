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


def test_group_mapping_defaults():
    provider = parse_oidc_providers_env(_env(VALID_PROVIDER))[0]

    assert provider.groups_claim == "groups"
    assert provider.staff_groups == []
    assert provider.superuser_groups == []
    assert provider.syncs_global_roles is False


def test_group_mapping_parsed():
    provider = dict(
        VALID_PROVIDER,
        groups_claim="roles",
        staff_groups=["staff", "admins"],
        superuser_groups=["superadmins"],
    )

    config = parse_oidc_providers_env(_env(provider))[0]

    assert config.groups_claim == "roles"
    assert config.staff_groups == ["staff", "admins"]
    assert config.superuser_groups == ["superadmins"]
    assert config.syncs_global_roles is True


@pytest.mark.parametrize("key", ["staff_groups", "superuser_groups"])
def test_group_lists_must_be_lists_of_strings(key):
    provider = dict(VALID_PROVIDER, **{key: "not-a-list"})

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))


def test_groups_claim_must_be_non_empty_string():
    provider = dict(VALID_PROVIDER, groups_claim="")

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
            {"group": "team-a", "workspace": 7, "role": "ADMIN"},
            {"group": "team-b", "workspace": 9, "role": "MEMBER"},
        ],
    )

    config = parse_oidc_providers_env(_env(provider))[0]

    assert config.syncs_workspace_memberships is True
    assert config.workspace_mappings[0].group == "team-a"
    assert config.workspace_mappings[0].workspace_id == 7
    assert config.workspace_mappings[0].role == "ADMIN"
    assert config.workspace_mappings[1].workspace_id == 9
    assert config.workspace_mappings[1].role == "MEMBER"


@pytest.mark.parametrize(
    "mapping",
    [
        {"group": "team", "workspace": 1},  # missing role
        {"group": "team", "workspace": 1, "role": "VIEWER"},  # role not allowed
        {"group": "team", "workspace": "1", "role": "ADMIN"},  # workspace not int
        {"group": "team", "workspace": True, "role": "ADMIN"},  # bool rejected
        {"workspace": 1, "role": "ADMIN"},  # missing group
        "not-an-object",
    ],
)
def test_invalid_workspace_mapping_fails_fast(mapping):
    provider = dict(VALID_PROVIDER, workspace_mappings=[mapping])

    with pytest.raises(ImproperlyConfigured):
        parse_oidc_providers_env(_env(provider))
