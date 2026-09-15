from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_403_FORBIDDEN

from baserow.core.audit_log.models import AuditLogEntry


@pytest.mark.django_db
def test_non_staff_cannot_list_audit_log(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:admin:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_staff_can_list_audit_log(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    AuditLogEntry.objects.create(
        user=user,
        user_email=user.email,
        action_type="sign_in",
        command_type="DO",
        description="Signed in",
    )

    response = api_client.get(
        reverse("api:admin:audit_log:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0]["action_type"] == "sign_in"


@pytest.mark.django_db
def test_staff_can_filter_audit_log_by_action_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    AuditLogEntry.objects.create(
        user=user, action_type="sign_in", command_type="DO", description="a"
    )
    AuditLogEntry.objects.create(
        user=user, action_type="sign_out", command_type="AUTH", description="b"
    )

    response = api_client.get(
        reverse("api:admin:audit_log:list"),
        {"action_type": "sign_out"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert response_json["results"][0]["action_type"] == "sign_out"


@pytest.mark.django_db
def test_non_staff_cannot_export_audit_log(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:admin:audit_log:export"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_staff_can_export_audit_log(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    AuditLogEntry.objects.create(
        user=user, action_type="sign_in", command_type="DO", description="a"
    )

    response = api_client.get(
        reverse("api:admin:audit_log:export"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    content = b"".join(response.streaming_content).decode("utf-8")
    assert "sign_in" in content
