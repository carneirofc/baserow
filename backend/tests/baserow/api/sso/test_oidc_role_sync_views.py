import dataclasses

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses

from baserow.core.sso.oidc.config import WorkspaceMapping
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
def test_staff_client_role_grants_staff_on_login(api_client):
    idp = FakeOIDCProvider(email="admin@example.com", client_roles=["baserow-staff"])
    config = dataclasses.replace(idp.config, staff_roles=["baserow-staff"])

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    user = User.objects.get(email="admin@example.com")
    assert user.is_staff is True


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_losing_the_staff_client_role_revokes_staff_on_next_login(
    api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    idp = FakeOIDCProvider(email="admin@example.com", client_roles=["baserow-staff"])
    # A second mapped role keeps the user past the access gate after they lose staff.
    # It has to be a workspace mapping: a superuser role would keep them staff too.
    config = dataclasses.replace(
        idp.config,
        staff_roles=["baserow-staff"],
        workspace_mappings=[
            WorkspaceMapping(
                client_role="baserow-member",
                workspace_id=workspace.id,
                permissions="MEMBER",
            )
        ],
    )

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        _drive_callback(api_client, idp, responses)
        user = User.objects.get(email="admin@example.com")
        assert user.is_staff is True

        # Next login, the user no longer holds the staff role.
        idp.client_roles = ["baserow-member"]
        responses.reset()
        _drive_callback(api_client, idp, responses)

    user.refresh_from_db()
    assert user.is_staff is False


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_superuser_role_keeps_staff_when_the_staff_role_is_lost(api_client):
    # Superuser implies staff, so an admin who loses the staff role keeps the flag.
    idp = FakeOIDCProvider(
        email="admin@example.com", client_roles=["baserow-staff", "baserow-admin"]
    )
    config = dataclasses.replace(
        idp.config, staff_roles=["baserow-staff"], superuser_roles=["baserow-admin"]
    )

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        _drive_callback(api_client, idp, responses)
        user = User.objects.get(email="admin@example.com")
        assert user.is_staff is True

        idp.client_roles = ["baserow-admin"]
        responses.reset()
        _drive_callback(api_client, idp, responses)

    user.refresh_from_db()
    assert user.is_superuser is True
    assert user.is_staff is True


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_roles_are_read_from_the_userinfo_endpoint(api_client):
    # The operator enabled the client-roles mapper on userinfo but not the ID token.
    idp = FakeOIDCProvider(email="admin@example.com", client_roles=["baserow-staff"])
    config = dataclasses.replace(idp.config, staff_roles=["baserow-staff"])

    responses.add(responses.GET, idp.discovery_url, json=idp.discovery_document())
    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        api_client.get(reverse("api:sso:oidc:login", args=(idp.name,)))
        nonce = api_client.session[SESSION_NONCE_KEY]
        # Mint an ID token carrying no roles at all; userinfo still has them.
        id_token = dataclasses.replace(idp, client_roles=None).mint_id_token(
            nonce=nonce
        )
        idp.register_all(responses, id_token=id_token)
        response = api_client.get(
            reverse("api:sso:oidc:callback", args=(idp.name,)) + "?code=the-code"
        )

    assert response.status_code == 302
    assert User.objects.get(email="admin@example.com").is_staff is True


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_login_refused_without_a_mapped_client_role(api_client):
    idp = FakeOIDCProvider(email="nobody@example.com", client_roles=["unrelated"])
    config = dataclasses.replace(idp.config, staff_roles=["baserow-staff"])

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    assert "error=errorNoMappedRole" in response.url
    # The refusal happens before anything is written: no account is provisioned.
    assert not User.objects.filter(email="nobody@example.com").exists()


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_login_refused_when_the_user_holds_no_client_role(api_client):
    idp = FakeOIDCProvider(email="nobody@example.com", client_roles=[])
    config = dataclasses.replace(idp.config, staff_roles=["baserow-staff"])

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        response = _drive_callback(api_client, idp, responses)

    assert "error=errorNoMappedRole" in response.url
    assert not User.objects.filter(email="nobody@example.com").exists()


@responses.activate(assert_all_requests_are_fired=False)
@pytest.mark.django_db
def test_provider_without_mappings_still_signs_the_user_in(api_client):
    # A plain sign-in provider derives no access from roles, so it is not gated.
    idp = FakeOIDCProvider(email="anyone@example.com", client_roles=[])

    with override_settings(BASEROW_OIDC_PROVIDERS=[idp.config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    assert "error=" not in response.url
    assert User.objects.filter(email="anyone@example.com").exists()
