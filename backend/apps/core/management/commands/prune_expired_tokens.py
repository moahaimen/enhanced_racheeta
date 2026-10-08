"""Maintenance: delete expired JWT refresh tokens and their blacklist rows.

`rest_framework_simplejwt.token_blacklist` stores one OutstandingToken per issued refresh token
and a BlacklistedToken per revoked one; both only grow. This removes outstanding tokens whose expiry
has passed (their blacklist rows cascade). An expired token can no longer be used, so deleting it
never re-enables a revoked one.

Safe to rerun (idempotent), works in small batches so it never holds a long lock, and prints one
summary line. Intended for a scheduled job (docs/OPERATIONS.md); there is no permanent worker.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken


class Command(BaseCommand):
    help = "Delete expired refresh tokens (and, by cascade, their blacklist entries)."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=5000)
        parser.add_argument(
            "--dry-run", action="store_true", help="Count what would be deleted, delete nothing."
        )

    def handle(self, *args, **options):
        now = timezone.now()
        batch = max(1, options["batch_size"])
        expired = OutstandingToken.objects.filter(expires_at__lt=now)
        if options["dry_run"]:
            self.stdout.write(
                f"prune_expired_tokens: would delete {expired.count()} expired token(s)"
            )
            return
        deleted = 0
        while True:
            ids = list(expired.values_list("pk", flat=True)[:batch])
            if not ids:
                break
            with transaction.atomic():
                # Blacklist rows reference the token row; delete them first so the batch is bounded.
                OutstandingToken.objects.filter(pk__in=ids).delete()
            deleted += len(ids)
        remaining = OutstandingToken.objects.count()
        self.stdout.write(
            f"prune_expired_tokens: deleted {deleted} expired token(s); {remaining} remain"
        )
