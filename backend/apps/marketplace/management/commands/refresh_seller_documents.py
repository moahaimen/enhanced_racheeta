"""Recompute every store's `documents_complete` (run daily in production, e.g. from cron).

Licences expire with time, not with an event: a store whose last required licence expired
yesterday must stop selling today. Uploads, withdrawals and reviews already recompute the flag.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.marketplace.models import MedicalCompany
from apps.marketplace.sellers import refresh_documents_complete


class Command(BaseCommand):
    help = "Recompute documents_complete for every store (expired licences stop sales)."

    def handle(self, *args, **options):
        changed = 0
        for pk, before in MedicalCompany.objects.values_list("pk", "documents_complete"):
            with transaction.atomic():
                if refresh_documents_complete(pk) != before:
                    changed += 1
        self.stdout.write(f"refresh_seller_documents: {changed} store(s) changed")
