import django.core.validators
import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("providers", "0001_initial"),
        ("reservations", "0004_protect_reservation_patient"),
    ]

    operations = [
        migrations.CreateModel(
            name="Review",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True, editable=False)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_name_snapshot", models.CharField(max_length=150)),
                ("service_title_snapshot", models.CharField(max_length=150)),
                ("rating", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ("comment", models.CharField(blank=True, default="", max_length=1000)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="provider_reviews", to=settings.AUTH_USER_MODEL)),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviews", to="providers.providerprofile")),
                ("reservation", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="review", to="reservations.reservation")),
            ],
            options={"db_table": "reviews_review", "ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.CheckConstraint(
                condition=models.Q(("rating__gte", 1), ("rating__lte", 5)),
                name="reviews_rating_1_to_5",
            ),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(fields=["provider", "-created_at"], name="reviews_provider_idx"),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(fields=["patient", "-created_at"], name="reviews_patient_idx"),
        ),
    ]
