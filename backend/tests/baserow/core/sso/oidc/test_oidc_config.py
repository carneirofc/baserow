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
