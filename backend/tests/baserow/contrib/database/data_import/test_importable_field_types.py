import pytest

from baserow.contrib.database.fields.registries import field_type_registry

# The field types a file import can write values into. A strict import requires the
# file to cover exactly these, so this set is part of the contract: adding a field
# type here (or setting `can_import`) must be matched by `getCanImport()` on the
# frontend field type, or the two sides disagree about which columns a file needs.
EXPECTED_IMPORTABLE_FIELD_TYPES = {
    "boolean",
    "date",
    "duration",
    "email",
    "file",
    "link_row",
    "long_text",
    "multiple_collaborators",
    "multiple_select",
    "number",
    "phone_number",
    "rating",
    "single_select",
    "text",
    "url",
}


@pytest.mark.django_db
def test_importable_field_types_are_the_expected_set():
    importable = {
        field_type.type
        for field_type in field_type_registry.get_all()
        if field_type.can_import and not field_type.read_only
    }

    assert importable == EXPECTED_IMPORTABLE_FIELD_TYPES


@pytest.mark.django_db
def test_read_only_field_types_are_never_importable():
    for field_type in field_type_registry.get_all():
        if field_type.read_only:
            assert not field_type.can_import, field_type.type
