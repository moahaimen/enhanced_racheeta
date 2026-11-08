"""Audit 2026-11-06: legacy categories must not become MORE purchasable than before.

0004 mapped every legacy `consumer_allowed` category to B2C_ALLOWED and everything else to
QUOTE_ONLY. That preserves what the old public store sold, but two cases were auto-approved
without review and are demoted here to RESTRICTED_PENDING_REVIEW (fail closed):

* an INACTIVE legacy consumer category: it sold nothing, so reactivating it must be a review;
* a legacy consumer category that contains a RESTRICTED (regulated) product: a category mixing
  regulated items is not "consumer merchandise" until someone reviews it.

It runs once, right after 0004, and only demotes (never promotes); applying the same rule twice
changes nothing. The checkout no longer
treats B2C_ALLOWED as permission for direct B2B purchase (that needs B2B_VERIFIED_ONLY), so no
legacy category gains a new professional purchase path either.
"""

from django.db import migrations


def tighten(apps, schema_editor):
    Category = apps.get_model("marketplace", "ProductCategory")
    Product = apps.get_model("marketplace", "Product")
    legacy_b2c = Category.objects.filter(consumer_allowed=True, compliance_class="B2C_ALLOWED")
    regulated = Product.objects.filter(is_restricted=True).values("category_id")
    legacy_b2c.filter(is_active=False).update(compliance_class="RESTRICTED_PENDING_REVIEW")
    legacy_b2c.filter(pk__in=regulated).update(compliance_class="RESTRICTED_PENDING_REVIEW")


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0004_compliance_and_reservations")]

    operations = [migrations.RunPython(tighten, migrations.RunPython.noop)]
