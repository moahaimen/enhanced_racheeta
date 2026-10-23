"""Ownership registry for synthetic demo data (docs/DEMO_DATA.md, ADR-063).

No existing model carries a "this row is synthetic" marker, and guessing from names or e-mail
domains cannot satisfy "delete ONLY demo data". So every row that `seed_demo_data` inserts
(including side effects such as notifications, audit events and transitions) is recorded here, and
`clear_demo_data` deletes exactly the registered rows (plus rows that exist only because of them and
reference nothing outside the registry). A row that is not registered is never deleted.
"""

from django.db import models


class DemoRecord(models.Model):
    # "app_label.ModelName" and the primary key as text (UUID for almost every model).
    model_label = models.CharField(max_length=100)
    object_pk = models.CharField(max_length=64)
    # Stable idempotency key of rows the seeder addresses by name ("provider:dijla-hospital");
    # null for side effects that are recorded only so they can be removed.
    key = models.CharField(max_length=200, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "demo_record"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["model_label", "object_pk"], name="demo_record_unique")
        ]
        indexes = [models.Index(fields=["model_label"], name="demo_record_model_idx")]

    def __str__(self) -> str:
        return f"{self.model_label}:{self.object_pk}"
