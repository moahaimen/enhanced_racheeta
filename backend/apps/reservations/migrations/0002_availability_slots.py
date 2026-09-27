import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AvailabilitySlot",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="availability_slots",
                        to="providers.providerprofile",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="availability_slots",
                        to="providers.serviceoffering",
                    ),
                ),
            ],
            options={
                "db_table": "reservations_availability_slot",
                "ordering": ["starts_at"],
                "indexes": [
                    models.Index(
                        fields=["provider", "is_active", "starts_at"],
                        name="reservations_slot_lookup_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("ends_at__gt", models.F("starts_at"))),
                        name="reservations_slot_end_after_start",
                    ),
                    models.UniqueConstraint(
                        fields=("provider", "starts_at"),
                        name="reservations_slot_provider_start_unique",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="reservation",
            name="availability_slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reservations",
                to="reservations.availabilityslot",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("availability_slot__isnull", False),
                    ("status__in", ["PENDING", "CONFIRMED"]),
                ),
                fields=("availability_slot",),
                name="reservations_one_live_per_slot",
            ),
        ),
    ]
