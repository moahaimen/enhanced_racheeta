import django.core.validators
import django.db.models.deletion
import uuid
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("providers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Offer",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True, editable=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("service_title_snapshot", models.CharField(max_length=150)),
                ("title", models.CharField(max_length=150)),
                ("description", models.CharField(blank=True, default="", max_length=1000)),
                ("original_price_snapshot", models.DecimalField(decimal_places=2, max_digits=12)),
                ("offer_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("currency_snapshot", models.CharField(max_length=3)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="offers", to="providers.providerprofile")),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="offers", to="providers.serviceoffering")),
            ],
            options={"db_table": "offers_offer", "ordering": ["-starts_at", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="offer",
            constraint=models.CheckConstraint(
                condition=models.Q(("ends_at__gt", models.F("starts_at"))),
                name="offers_end_after_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="offer",
            constraint=models.CheckConstraint(
                condition=models.Q(("offer_price__gte", 0)),
                name="offers_price_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="offer",
            constraint=models.CheckConstraint(
                condition=models.Q(("offer_price__lt", models.F("original_price_snapshot"))),
                name="offers_price_below_original",
            ),
        ),
        migrations.AddIndex(
            model_name="offer",
            index=models.Index(
                fields=["provider", "is_active", "starts_at", "ends_at"],
                name="offers_public_idx",
            ),
        ),
    ]
