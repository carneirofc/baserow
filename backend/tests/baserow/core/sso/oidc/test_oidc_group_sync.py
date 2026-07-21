import dataclasses

import pytest

from baserow.core.sso.oidc.config import OIDCProviderConfig
from baserow.core.sso.oidc.groups import extract_groups, sync_global_roles

BASE_CONFIG = OIDCProviderConfig(
    name="keycloak",
    display_name="Keycloak",
    issuer="https://idp.example.com/realms/test",
    client_id="baserow",
    client_secret="secret",
)


def _config(**overrides):
    return dataclasses.replace(BASE_CONFIG, **overrides)


# --- extract_groups -------------------------------------------------------


def test_extract_groups_from_id_token():
    groups = extract_groups(BASE_CONFIG, {"groups": ["a", "b"]}, {})
    assert groups == ["a", "b"]


def test_extract_groups_from_userinfo():
    groups = extract_groups(BASE_CONFIG, {}, {"groups": ["c"]})
    assert groups == ["c"]


def test_extract_groups_unions_both_sources():
    groups = extract_groups(BASE_CONFIG, {"groups": ["a"]}, {"groups": ["a", "b"]})
    assert groups == ["a", "b"]


def test_extract_groups_supports_string_claim():
    groups = extract_groups(BASE_CONFIG, {"groups": "solo"}, {})
    assert groups == ["solo"]


def test_extract_groups_custom_claim_name():
    config = _config(groups_claim="roles")
    groups = extract_groups(config, {"roles": ["x"]}, {})
    assert groups == ["x"]


def test_extract_groups_empty_when_absent():
    assert extract_groups(BASE_CONFIG, {}, {}) == []


# --- sync_global_roles ----------------------------------------------------


@pytest.mark.django_db
def test_staff_group_grants_staff(data_fixture):
    user = data_fixture.create_user()
    assert user.is_staff is False

    sync_global_roles(user, ["staff"], _config(staff_groups=["staff"]))

    user.refresh_from_db()
    assert user.is_staff is True


@pytest.mark.django_db
def test_leaving_staff_group_revokes_staff(data_fixture):
    user = data_fixture.create_user()
    user.is_staff = True
    user.save()

    sync_global_roles(user, ["other"], _config(staff_groups=["staff"]))

    user.refresh_from_db()
    assert user.is_staff is False


@pytest.mark.django_db
def test_superuser_group_grants_superuser_and_staff(data_fixture):
    user = data_fixture.create_user()

    sync_global_roles(user, ["admins"], _config(superuser_groups=["admins"]))

    user.refresh_from_db()
    assert user.is_superuser is True
    assert user.is_staff is True


@pytest.mark.django_db
def test_leaving_superuser_group_revokes_superuser(data_fixture):
    user = data_fixture.create_user()
    user.is_superuser = True
    user.is_staff = True
    user.save()

    sync_global_roles(
        user, [], _config(superuser_groups=["admins"], staff_groups=["staff"])
    )

    user.refresh_from_db()
    assert user.is_superuser is False
    assert user.is_staff is False


@pytest.mark.django_db
def test_local_admin_untouched_when_provider_maps_no_groups(data_fixture):
    # Represents the break-glass admin: the provider configures no role mappings,
    # so a local admin's flags are never reconciled.
    user = data_fixture.create_user()
    user.is_staff = True
    user.is_superuser = True
    user.save()

    sync_global_roles(user, [], BASE_CONFIG)

    user.refresh_from_db()
    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_only_configured_dimension_is_reconciled(data_fixture):
    # staff_groups configured but superuser_groups not: is_superuser must be left
    # alone even though the user is not in any staff group.
    user = data_fixture.create_user()
    user.is_superuser = True
    user.is_staff = True
    user.save()

    sync_global_roles(user, [], _config(staff_groups=["staff"]))

    user.refresh_from_db()
    # is_superuser untouched (not mapped); is_staff kept True because superuser
    # implies staff.
    assert user.is_superuser is True
    assert user.is_staff is True
