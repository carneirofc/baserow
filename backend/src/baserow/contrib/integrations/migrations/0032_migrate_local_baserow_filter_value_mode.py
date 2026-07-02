from django.db import migrations


def migrate_filter_values_to_raw_mode(apps, schema_editor):
    LocalBaserowTableServiceFilter = apps.get_model(
        "integrations", "LocalBaserowTableServiceFilter"
    )

    filters_to_update = []
    for service_filter in LocalBaserowTableServiceFilter.objects.filter(
        value_is_formula=False
    ).iterator():
        value = service_filter.value
        if isinstance(value, dict):
            value["mode"] = "raw"
        else:
            value = {
                "formula": "" if value is None else str(value),
                "mode": "raw",
                "version": "0.1",
            }

        service_filter.value = value
        filters_to_update.append(service_filter)
        if len(filters_to_update) >= 1000:
            LocalBaserowTableServiceFilter.objects.bulk_update(
                filters_to_update, ["value"]
            )
            filters_to_update = []

    if filters_to_update:
        LocalBaserowTableServiceFilter.objects.bulk_update(filters_to_update, ["value"])


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0031_corestartworkflowservice"),
    ]

    operations = [
        migrations.RunPython(
            migrate_filter_values_to_raw_mode, migrations.RunPython.noop
        ),
    ]
