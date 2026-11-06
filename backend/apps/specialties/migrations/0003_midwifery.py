"""Midwifery (a nursing specialty): preselected for the MIDWIFE onboarding type. Idempotent."""

from django.db import migrations


def seed(apps, schema_editor):
    Specialty = apps.get_model("specialties", "Specialty")
    parent = Specialty.objects.filter(slug="nursing").first()
    last = Specialty.objects.order_by("-sort_order").values_list("sort_order", flat=True).first()
    Specialty.objects.get_or_create(
        slug="midwifery",
        defaults={
            "name_en": "Midwifery",
            "name_ar": "القبالة",
            "parent": parent,
            "sort_order": (last or 0) + 1,
        },
    )


def unseed(apps, schema_editor):
    Specialty = apps.get_model("specialties", "Specialty")
    Specialty.objects.filter(slug="midwifery", providers__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("specialties", "0002_seed_specialties")]
    operations = [migrations.RunPython(seed, unseed)]
