from __future__ import annotations

from typing import Any

from .models import AuditEvent

FORBIDDEN_KEYS = {"password", "token", "access", "refresh", "secret", "authorization"}


def record(
    *, actor, action: str, target, summary: str = "", data: dict[str, Any] | None = None
) -> AuditEvent:
    """Append an audit event. `target` is any model instance (type + pk recorded)."""
    clean = {k: v for k, v in (data or {}).items() if k.lower() not in FORBIDDEN_KEYS}
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        summary=summary[:255],
        data=clean,
    )
