"""Seed Iraq (country, governorates, principal cities). Idempotent."""

from django.db import migrations


def seed(apps, schema_editor):
    from apps.geography.seed_iraq import IRAQ_GOVERNORATES

    Country = apps.get_model("geography", "Country")
    Governorate = apps.get_model("geography", "Governorate")
    City = apps.get_model("geography", "City")

    iraq, _ = Country.objects.get_or_create(code="IQ", defaults={"name_en": "Iraq", "name_ar": "العراق"})
    for order, (slug, name_en, name_ar, cities) in enumerate(IRAQ_GOVERNORATES, start=1):
        gov, _ = Governorate.objects.get_or_create(
            country=iraq, slug=slug, defaults={"name_en": name_en, "name_ar": name_ar, "sort_order": order}
        )
        for c_order, (c_slug, c_en, c_ar) in enumerate(cities, start=1):
            City.objects.get_or_create(
                governorate=gov, slug=c_slug, defaults={"name_en": c_en, "name_ar": c_ar, "sort_order": c_order}
            )


def unseed(apps, schema_editor):
    Country = apps.get_model("geography", "Country")
    Country.objects.filter(code="IQ").delete()


class Migration(migrations.Migration):
    dependencies = [("geography", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
