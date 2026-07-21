import dataclasses

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses

from baserow.core.models import WorkspaceUser
from baserow.core.sso.oidc.config import WorkspaceRoleMapping
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
def test_login_adds_user_to_mapped_workspace(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    idp = FakeOIDCProvider(email="member@example.com", groups=["team-a"])
    config = dataclasses.replace(
        idp.config,
        workspace_mappings=[
            WorkspaceRoleMapping(
                group="team-a", workspace_id=workspace.id, role="ADMIN"
            )
        ],
    )

    with override_settings(BASEROW_OIDC_PROVIDERS=[config]):
        response = _drive_callback(api_client, idp, responses)

    assert response.status_code == 302
    user = User.objects.get(email="member@example.com")
    wu = WorkspaceUser.objects.get(user=user, workspace=workspace)
    assert wu.permissions == "ADMIN"
