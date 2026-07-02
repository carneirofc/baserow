from django.db import migrations


BASEROW_FORMULA_VERSION_INITIAL = "0.1"
BASEROW_FORMULA_MODE_RAW = "raw"
BASEROW_FORMULA_MODE_SIMPLE = "simple"


def to_formula_object(value, mode):
    if isinstance(value, dict):
        value = value.copy()
        value.setdefault("formula", "")
        value.setdefault("version", BASEROW_FORMULA_VERSION_INITIAL)
        value["mode"] = mode
        return value

    return {
        "formula": "" if value is None else str(value),
        "version": BASEROW_FORMULA_VERSION_INITIAL,
        "mode": mode,
    }


def migrate_tags_colors_to_formula_objects(apps, schema_editor):
    CollectionField = apps.get_model("builder", "CollectionField")

    fields_to_update = []
    for collection_field in CollectionField.objects.filter(type="tags").iterator():
        config = collection_field.config or {}
        if "colors" not in config:
            continue

        if config.get("colors_is_formula") is False:
            mode = BASEROW_FORMULA_MODE_RAW
        elif config.get("colors_is_formula") is True:
            mode = BASEROW_FORMULA_MODE_SIMPLE
        elif isinstance(config.get("colors"), dict):
            mode = config["colors"].get("mode", BASEROW_FORMULA_MODE_SIMPLE)
        else:
            mode = BASEROW_FORMULA_MODE_SIMPLE

        colors = to_formula_object(config.get("colors"), mode)

        if config.get("colors") == colors:
            continue

        collection_field.config = {**config, "colors": colors}
        fields_to_update.append(collection_field)

        if len(fields_to_update) >= 1000:
            CollectionField.objects.bulk_update(fields_to_update, ["config"])
            fields_to_update = []

    if fields_to_update:
        CollectionField.objects.bulk_update(fields_to_update, ["config"])


class Migration(migrations.Migration):
    dependencies = [
        ("builder", "0074_corestartworkflowworkflowaction"),
    ]

    operations = [
        migrations.RunPython(
            migrate_tags_colors_to_formula_objects, migrations.RunPython.noop
        ),
    ]
