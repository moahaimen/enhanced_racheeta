"""Seed the initial specialty list. Idempotent."""

from django.db import migrations


def seed(apps, schema_editor):
    from apps.specialties.seed import SPECIALTIES

    Specialty = apps.get_model("specialties", "Specialty")
    by_slug = {}
    for order, (slug, name_en, name_ar, parent_slug) in enumerate(SPECIALTIES, start=1):
        parent = by_slug.get(parent_slug) if parent_slug else None
        obj, _ = Specialty.objects.get_or_create(
            slug=slug,
            defaults={"name_en": name_en, "name_ar": name_ar, "parent": parent, "sort_order": order},
        )
        by_slug[slug] = obj


def unseed(apps, schema_editor):
    from apps.specialties.seed import SPECIALTIES

    Specialty = apps.get_model("specialties", "Specialty")
    Specialty.objects.filter(slug__in=[s[0] for s in reversed(SPECIALTIES)]).delete()


class Migration(migrations.Migration):
    dependencies = [("specialties", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
