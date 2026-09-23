"""Seed the initial plan configuration (reference data, no prices). Idempotent."""

from django.db import migrations


def seed(apps, schema_editor):
    from apps.billing.seed import PLANS

    Plan = apps.get_model("billing", "Plan")
    PlanEntitlement = apps.get_model("billing", "PlanEntitlement")
    for code, audience, name_en, name_ar, period, term_days, is_public, is_default, sort, entitlements in PLANS:
        plan, _ = Plan.objects.get_or_create(
            code=code,
            defaults={
                "audience": audience,
                "name_en": name_en,
                "name_ar": name_ar,
                "billing_period": period,
                "term_days": term_days,
                "is_public": is_public,
                "is_default": is_default,
                "sort_order": sort,
            },
        )
        for key, kind, enabled, limit, usage_period in entitlements:
            PlanEntitlement.objects.get_or_create(
                plan=plan, key=key, defaults={"kind": kind, "enabled": enabled, "limit": limit, "period": usage_period}
            )


def unseed(apps, schema_editor):
    from apps.billing.seed import PLANS

    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code__in=[p[0] for p in PLANS], subscriptions__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
