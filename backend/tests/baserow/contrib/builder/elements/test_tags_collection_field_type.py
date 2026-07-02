import pytest

from baserow.contrib.builder.api.elements.serializers import CollectionFieldSerializer
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.pages.service import PageService
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_RAW,
    BASEROW_FORMULA_MODE_SIMPLE,
)


@pytest.mark.django_db
def test_import_export_tags_collection_field_type(data_fixture):
    """
    Ensure that the TagsCollectionField's formulas are exported correctly
    with the updated Data Sources.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["BMW", "#ffffff"],
        ],
    )
    name_field, color_field = fields
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Colors as formula",
                "type": "tags",
                "config": {
                    "values": f"get('data_source.{data_source.id}.0.{name_field.db_column}')",
                    "colors": f"get('data_source.{data_source.id}.0.{color_field.db_column}')",
                    "colors_is_formula": True,
                },
            },
            {
                "name": "Colors as hex",
                "type": "tags",
                "config": {
                    "values": "'a,b,c'",
                    "colors": "#d06060ff",
                    "colors_is_formula": False,
                },
            },
        ],
    )

    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()

    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}

    exported = table_element.get_type().export_serialized(table_element)
    exported_fields = exported["fields"]
    assert "colors_is_formula" not in exported_fields[0]["config"]
    assert "colors_is_formula" not in exported_fields[1]["config"]

    imported_table_element = ElementHandler().import_element(page, exported, id_mapping)

    tags_with_formula = imported_table_element.fields.get(name="Colors as formula")
    assert tags_with_formula.config == {
        "values": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{name_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "colors": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{color_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "colors_is_formula": True,
    }

    tags_without_formula = imported_table_element.fields.get(name="Colors as hex")
    assert tags_without_formula.config == {
        "values": BaserowFormulaObject(
            formula="'a,b,c'",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "colors": BaserowFormulaObject(
            formula="#d06060ff",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_RAW,
        ),
        "colors_is_formula": False,
    }


@pytest.mark.django_db
def test_import_legacy_tags_collection_field_type_colors_is_formula(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table_element = data_fixture.create_builder_table_element(page=page)

    serialized = table_element.get_type().export_serialized(table_element)
    serialized["data_source_id"] = None
    serialized["fields"] = [
        {
            "name": "Colors as formula",
            "type": "tags",
            "config": {
                "values": "'a,b,c'",
                "colors": "get('current_record.Color')",
                "colors_is_formula": True,
            },
        },
        {
            "name": "Colors as hex",
            "type": "tags",
            "config": {
                "values": "'a,b,c'",
                "colors": "#d06060ff",
                "colors_is_formula": False,
            },
        },
    ]

    imported_table_element = ElementHandler().import_element(page, serialized, {})

    tags_with_formula = imported_table_element.fields.get(name="Colors as formula")
    assert tags_with_formula.config["colors"] == BaserowFormulaObject(
        formula="get('current_record.Color')",
        version=BASEROW_FORMULA_VERSION_INITIAL,
        mode=BASEROW_FORMULA_MODE_SIMPLE,
    )
    assert tags_with_formula.config["colors_is_formula"] is True

    tags_without_formula = imported_table_element.fields.get(name="Colors as hex")
    assert tags_without_formula.config["colors"] == BaserowFormulaObject(
        formula="#d06060ff",
        version=BASEROW_FORMULA_VERSION_INITIAL,
        mode=BASEROW_FORMULA_MODE_RAW,
    )
    assert tags_without_formula.config["colors_is_formula"] is False


@pytest.mark.django_db
def test_serialize_legacy_tags_collection_field_type_colors_is_formula(data_fixture):
    table_element = data_fixture.create_builder_table_element(
        fields=[
            {
                "name": "Colors as hex",
                "type": "tags",
                "config": {
                    "values": "'a,b,c'",
                    "colors": "#d06060ff",
                    "colors_is_formula": False,
                },
            },
        ],
    )

    tags_without_formula = table_element.fields.get(name="Colors as hex")
    serialized = CollectionFieldSerializer(tags_without_formula).data

    assert "colors_is_formula" not in serialized
    assert serialized["colors"] == BaserowFormulaObject(
        formula="#d06060ff",
        version=BASEROW_FORMULA_VERSION_INITIAL,
        mode=BASEROW_FORMULA_MODE_RAW,
    )


def test_deserialize_tags_collection_field_type_derives_colors_is_formula():
    serializer = CollectionFieldSerializer(
        data={
            "name": "Colors as hex",
            "type": "tags",
            "values": {
                "formula": "",
                "version": BASEROW_FORMULA_VERSION_INITIAL,
                "mode": BASEROW_FORMULA_MODE_RAW,
            },
            "colors": {
                "formula": "#d06060ff",
                "version": BASEROW_FORMULA_VERSION_INITIAL,
                "mode": BASEROW_FORMULA_MODE_RAW,
            },
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["config"]["colors_is_formula"] is False
