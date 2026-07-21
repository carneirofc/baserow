from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses

from baserow.core.auth_provider.models import OIDCAuthProviderModel
from baserow.core.sso.oidc.handler import SESSION_NONCE_KEY
from baserow.test_utils.oidc import FakeOIDCProvider


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_login_options_lists_oidc_providers(api_client):
    idp = FakeOIDCProvider()
    with override_settings(BASEROW_OIDC_PROVIDERS=[idp.config]):
        response = api_client.get(reverse("api:auth_provider:login_options"))

    assert response.status_code == 200
    body = response.json()
    assert "openid_connect" in body
    oidc = body["openid_connect"]
    assert oidc["type"] == "openid_connect"
    assert len(oidc["items"]) == 1
    item = oidc["items"][0]
    assert item["type"] == "openid_connect"
    assert item["name"] == "Keycloak"
    assert item["redirect_url"].endswith("/api/sso/oidc/login/keycloak/")
    # A single provider auto-redirects.
    assert oidc["default_redirect_url"] == item["redirect_url"]


@pytest.mark.django_db
def test_login_options_omits_oidc_when_unconfigured(api_client):
    with override_settings(BASEROW_OIDC_PROVIDERS=[]):
        response = api_client.get(reverse("api:auth_provider:login_options"))

    assert response.status_code == 200
    assert "openid_connect" not in response.json()


@pytest.mark.django_db
def test_login_options_lists_multiple_providers(api_client):
    idp = FakeOIDCProvider()
    second = FakeOIDCProvider(name="google", display_name="Google")
    with override_settings(BASEROW_OIDC_PROVIDERS=[idp.config, second.config]):
        response = api_client.get(reverse("api:auth_provider:login_options"))

    oidc = response.json()["openid_connect"]
    assert [i["name"] for i in oidc["items"]] == ["Keycloak", "Google"]
    # More than one provider => no default auto-redirect.
    assert oidc["default_redirect_url"] is None


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_login_redirects_to_provider(api_client):
    idp = FakeOIDCProvider()
    responses.add(responses.GET, idp.discovery_url, json=idp.discovery_document())

    with override_settings(BASEROW_OIDC_PROVIDERS=[idp.config]):
        response = api_client.get(
            reverse("api:sso:oidc:login", args=("keycloak",)) + "?original=/dashboard"
        )

    assert response.status_code == 302
    assert response.headers["Location"].startswith(idp.authorization_endpoint)


@pytest.mark.django_db
def test_login_unknown_provider_redirects_to_error(api_client):
    with override_settings(BASEROW_OIDC_PROVIDERS=[]):
        response = api_client.get(reverse("api:sso:oidc:login", args=("nope",)))

    assert response.status_code == 302
    assert "/login?" in response.headers["Location"]
    assert "errorProviderDoesNotExist" in response.headers["Location"]


def _drive_callback(api_client, idp, responses_mock):
    """Runs login then callback against the same client session; returns the response."""

    responses_mock.add(
        responses_mock.GET, idp.discovery_url, json=idp.discovery_document()
    )
    api_client.get(reverse("api:sso:oidc:login", args=(idp.name,)))
    nonce = api_client.session[SESSION_NONCE_KEY]
    idp.register_all(responses_mock, nonce=nonce)
    return api_client.get(
        reverse("api:sso:oidc:callback", args=(idp.name,)) + "?code=the-code"
    )


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_callback_creates_user_and_signs_in(api_client):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    idp = FakeOIDCProvider(email="newuser@example.com", full_name="New User")

    with override_settings(BASEROW_OIDC_PROVIDERS=[idp.config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    location = response.headers["Location"]
    # The refresh token is embedded in the redirect for the SPA to pick up.
    query = parse_qs(urlparse(location).query)
    assert "token" in query
    assert "user_session" in query

    user = User.objects.get(email="newuser@example.com")
    assert user.first_name == "New User"
    # The provider anchor row now links the created user.
    provider = OIDCAuthProviderModel.objects.get(name="keycloak")
    assert provider.users.filter(id=user.id).exists()


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_callback_signs_in_existing_user(api_client, data_fixture):
    idp = FakeOIDCProvider(email="existing@example.com", full_name="Existing User")
    # Pre-create the user and link them to the provider anchor so the
    # different-provider guard is satisfied.
    user = data_fixture.create_user(email="existing@example.com")
    provider = OIDCAuthProviderModel.objects.create(name=idp.name)
    provider.users.add(user)

    with override_settings(BASEROW_OIDC_PROVIDERS=[idp.config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    assert "error=" not in response.headers["Location"]
    query = parse_qs(urlparse(response.headers["Location"]).query)
    assert "token" in query
