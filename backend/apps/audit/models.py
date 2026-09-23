"""Structured, append-only audit trail for commercially and security
sensitive actions. Never stores secrets, tokens or passwords."""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class AuditEvent(BaseModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(
        max_length=80, db_index=True, help_text="dotted code, e.g. billing.subscription.activated"
    )
    target_type = models.CharField(max_length=60)
    target_id = models.CharField(max_length=64)
    summary = models.CharField(max_length=255, blank=True, default="")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "audit_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["target_type", "target_id", "-created_at"], name="audit_event_target_idx"
            )
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"
