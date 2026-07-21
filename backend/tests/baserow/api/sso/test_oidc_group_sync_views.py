from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses

from baserow.core.sso.oidc.handler import SESSION_NONCE_KEY
from baserow.test_utils.oidc import FakeOIDCProvider

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def _drive_callback(api_client, idp, responses_mock):
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
def test_staff_group_membership_grants_staff_on_login(api_client):
    idp = FakeOIDCProvider(email="admin@example.com", groups=["baserow-staff"])
    config = idp.config
    config.staff_groups.append("baserow-staff")

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    user = User.objects.get(email="admin@example.com")
    assert user.is_staff is True


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_leaving_staff_group_revokes_staff_on_next_login(api_client):
    idp = FakeOIDCProvider(email="admin@example.com", groups=["baserow-staff"])
    config = idp.config
    config.staff_groups.append("baserow-staff")

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        _drive_callback(api_client, idp, responses)
        user = User.objects.get(email="admin@example.com")
        assert user.is_staff is True

        # Next login, the user has left the staff group.
        idp.groups = []
        responses.reset()
        _drive_callback(api_client, idp, responses)

    user.refresh_from_db()
    assert user.is_staff is False
