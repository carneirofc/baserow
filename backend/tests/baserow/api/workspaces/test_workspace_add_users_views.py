from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.core.models import WorkspaceUser


@pytest.fixture
def setup(data_fixture):
    admin, admin_token = data_fixture.create_user_and_token(first_name="Admin")
    member, member_token = data_fixture.create_user_and_token(first_name="Member")
    workspace = data_fixture.create_workspace()
    data_fixture.create_user_workspace(workspace=workspace, user=admin, order=1)
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER", order=2
    )
    return workspace, admin_token, member, member_token


def add_url(workspace):
    return reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id})


def candidates_url(workspace, search):
    return (
        reverse(
            "api:workspaces:users:candidates", kwargs={"workspace_id": workspace.id}
        )
        + f"?search={search}"
    )


@pytest.mark.django_db
def test_admin_adds_existing_users_directly(api_client, data_fixture, setup):
    workspace, admin_token, member, _ = setup
    alice = data_fixture.create_user(email="alice@example.com")
    bob = data_fixture.create_user(email="bob@example.com")

    response = api_client.post(
        add_url(workspace),
        {"user_ids": [alice.id, bob.id], "permissions": "ADMIN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert sorted(item["user_id"] for item in response.json()) == sorted(
        [alice.id, bob.id]
    )
    assert set(
        WorkspaceUser.objects.filter(
            workspace=workspace, user__in=[alice, bob]
        ).values_list("permissions", flat=True)
    ) == {"ADMIN"}


@pytest.mark.django_db
def test_adding_an_existing_member_keeps_their_permissions(
    api_client, data_fixture, setup
):
    workspace, admin_token, member, _ = setup

    response = api_client.post(
        add_url(workspace),
        {"user_ids": [member.id], "permissions": "ADMIN"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert WorkspaceUser.objects.get(workspace=workspace, user=member).permissions == (
        "MEMBER"
    )


@pytest.mark.django_db
def test_add_users_defaults_to_member_and_refuses_unaddable_accounts(
    api_client, data_fixture, setup
):
    workspace, admin_token, _, _ = setup
    alice = data_fixture.create_user()
    inactive = data_fixture.create_user(is_active=False)

    response = api_client.post(
        add_url(workspace),
        {"user_ids": [alice.id, inactive.id, 0]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USERS_CANNOT_BE_ADDED"
    # All or nothing.
    assert not WorkspaceUser.objects.filter(workspace=workspace, user=alice).exists()

    response = api_client.post(
        add_url(workspace),
        {"user_ids": [alice.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.json()[0]["permissions"] == "MEMBER"


@pytest.mark.django_db
def test_member_cannot_add_users_or_search(api_client, data_fixture, setup):
    workspace, _, _, member_token = setup
    alice = data_fixture.create_user(email="alice@example.com")

    response = api_client.post(
        add_url(workspace),
        {"user_ids": [alice.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {member_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"

    response = api_client.get(
        candidates_url(workspace, "alice"), HTTP_AUTHORIZATION=f"JWT {member_token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_INVALID_GROUP_PERMISSIONS"


@pytest.mark.django_db
def test_candidates_search(api_client, data_fixture, setup):
    workspace, admin_token, member, _ = setup
    alice = data_fixture.create_user(email="alice@example.com", first_name="Alice")
    data_fixture.create_user(email="alice.gone@example.com", is_active=False)
    auth = {"HTTP_AUTHORIZATION": f"JWT {admin_token}"}

    response = api_client.get(candidates_url(workspace, "ALICE"), **auth)
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json() == [
        {"user_id": alice.id, "name": "Alice", "email": "alice@example.com"}
    ]

    # Existing members are not candidates.
    response = api_client.get(candidates_url(workspace, member.email[:5]), **auth)
    assert member.id not in [item["user_id"] for item in response.json()]

    # A minimum length keeps admins from listing every account.
    response = api_client.get(candidates_url(workspace, "al"), **auth)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
