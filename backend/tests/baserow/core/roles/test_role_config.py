from django.core.exceptions import ImproperlyConfigured

import pytest

from baserow.core.roles.config import parse_roles_env


def test_empty_env_yields_no_roles():
    assert parse_roles_env(None) == []
    assert parse_roles_env("") == []
    assert parse_roles_env("   ") == []


def test_parses_a_role():
    [role] = parse_roles_env(
        '[{"workspace": 3, "name": " Editor ", "operations": [" workspace.read "]}]'
    )

    assert role.workspace_id == 3
    assert role.name == "Editor"
    assert role.operations == ["workspace.read"]


def test_operations_default_to_empty():
    [role] = parse_roles_env('[{"workspace": 3, "name": "Nothing"}]')

    assert role.operations == []


def test_invalid_json_is_rejected():
    with pytest.raises(ImproperlyConfigured, match="not valid JSON"):
        parse_roles_env("{[")


def test_non_list_is_rejected():
    with pytest.raises(ImproperlyConfigured, match="must be a JSON list"):
        parse_roles_env('{"workspace": 1, "name": "Editor"}')


def test_non_object_role_is_rejected():
    with pytest.raises(ImproperlyConfigured, match=r"BASEROW_ROLES\[0\]"):
        parse_roles_env('["Editor"]')


@pytest.mark.parametrize("workspace", ['"1"', "true", "null", "1.5"])
def test_workspace_must_be_an_integer(workspace):
    with pytest.raises(ImproperlyConfigured, match="'workspace' must be an integer"):
        parse_roles_env(f'[{{"workspace": {workspace}, "name": "Editor"}}]')


@pytest.mark.parametrize("name", ['""', '"   "', "5", "null"])
def test_name_must_be_a_non_empty_string(name):
    with pytest.raises(ImproperlyConfigured, match="'name' must be a non-empty string"):
        parse_roles_env(f'[{{"workspace": 1, "name": {name}}}]')


@pytest.mark.parametrize("operations", ['"workspace.read"', "[5]", '[""]'])
def test_operations_must_be_a_list_of_non_empty_strings(operations):
    with pytest.raises(ImproperlyConfigured, match="'operations' must be a list"):
        parse_roles_env(
            f'[{{"workspace": 1, "name": "Editor", "operations": {operations}}}]'
        )


def test_duplicate_role_in_the_same_workspace_is_rejected():
    with pytest.raises(ImproperlyConfigured, match="duplicate role 'Editor'"):
        parse_roles_env(
            '[{"workspace": 1, "name": "Editor"}, {"workspace": 1, "name": "Editor"}]'
        )


def test_the_same_role_name_in_different_workspaces_is_allowed():
    roles = parse_roles_env(
        '[{"workspace": 1, "name": "Editor"}, {"workspace": 2, "name": "Editor"}]'
    )

    assert [role.workspace_id for role in roles] == [1, 2]
