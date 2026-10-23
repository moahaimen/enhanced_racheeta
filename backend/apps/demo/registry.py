"""Records what `seed_demo_data` creates, and keeps the seeder idempotent.

`Registry` is a context manager: while it is active a `post_save` receiver notes every row that is
INSERTED (side effects included: notifications, audit events, transitions, billing accounts...). The
seeder runs as a separate management-command process, so no web request can be captured by
mistake. `ensure(key, factory)` makes a row addressable by a stable key so a second run finds and
reuses it instead of creating it again.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.apps import apps
from django.db.models.signals import post_save

from .models import DemoRecord

# Rows created lazily by the framework itself (never seed output, never ours to delete).
EXCLUDED_APP_LABELS = frozenset({"contenttypes", "auth", "sessions", "admin", "demo"})


class Registry:
    def __init__(self) -> None:
        self._pending: list[tuple[str, str]] = []
        self._seen: set[tuple[str, str]] = set()
        self._keys: dict[tuple[str, str], str] = {}
        self._dispatch_uid = f"demo-registry-{id(self)}"

    # -- recording ----------------------------------------------------------------------------
    def _on_save(self, sender, instance, created=False, raw=False, **kwargs) -> None:
        if not created or raw:
            return
        meta = sender._meta
        if meta.app_label in EXCLUDED_APP_LABELS or meta.auto_created:
            return
        ident = (meta.label, str(instance.pk))
        if ident not in self._seen:
            self._seen.add(ident)
            self._pending.append(ident)

    def __enter__(self) -> Registry:
        post_save.connect(self._on_save, dispatch_uid=self._dispatch_uid, weak=False)
        return self

    def __exit__(self, *exc_info) -> None:
        post_save.disconnect(dispatch_uid=self._dispatch_uid)

    # -- idempotency --------------------------------------------------------------------------
    @staticmethod
    def get(key: str) -> Any | None:
        record = DemoRecord.objects.filter(key=key).first()
        if record is None:
            return None
        return apps.get_model(record.model_label)._base_manager.filter(pk=record.object_pk).first()

    def ensure(self, key: str, factory: Callable[[], Any]) -> tuple[Any, bool]:
        """Return (object, created). The object is reused when `key` was seeded before."""
        record = DemoRecord.objects.filter(key=key).first()
        if record is not None:
            model = apps.get_model(record.model_label)
            existing = model._base_manager.filter(pk=record.object_pk).first()
            if existing is not None:
                return existing, False
            record.delete()  # the row was removed by hand: seed it again
        instance = factory()
        self._keys[(instance._meta.label, str(instance.pk))] = key
        return instance, True

    # -- persistence --------------------------------------------------------------------------
    def flush(self) -> int:
        """Write the registry rows for everything recorded so far (call inside the transaction)."""
        rows = [
            DemoRecord(model_label=label, object_pk=pk, key=self._keys.get((label, pk)))
            for label, pk in self._pending
        ]
        DemoRecord.objects.bulk_create(rows)
        count = len(rows)
        self._pending.clear()
        return count

    def discard_pending(self) -> None:
        """Forget recorded rows of a phase that was rolled back (they no longer exist)."""
        self._pending.clear()
        self._seen = {(m, p) for m, p in DemoRecord.objects.values_list("model_label", "object_pk")}
        self._keys.clear()

    @property
    def pending_count(self) -> int:
        return len(self._pending)
