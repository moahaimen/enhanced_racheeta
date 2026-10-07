"""Fill a LOCAL database with obviously fake data, for EXPLAIN analysis and the load harness.

    python manage.py seed_synthetic --confirm-synthetic --providers 5000 --jobs 5000 \
        --listings 3000 --notifications 5000

Safety (this command can write thousands of rows):
  * refuses unless the database host is local (localhost / 127.0.0.1 / ::1 / a unix socket),
    unless --allow-nonlocal-host is given (e.g. a disposable CI or staging database);
  * requires --confirm-synthetic;
  * every account is `...@synthetic.invalid`, every name starts with "Synthetic";
  * no real person's data, no external service, no credentials: the shared password for the load
    test user is read from SYNTHETIC_PASSWORD (or generated and NOT printed).
Idempotent per run: rows are namespaced by a run tag so a second run adds more rows.
"""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.geography.models import Governorate
from apps.jobs.models import Employer, JobPost
from apps.notifications.models import Notification
from apps.notifications.types import NotificationCategory, NotificationEventType
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus
from apps.real_estate.models import ListingSuitableUse, PropertyListing, RealEstateSeller
from apps.real_estate.types import (
    ContactMethod,
    PropertyType,
    PublicationStatus,
    SellerType,
    SuitableUse,
    TransactionType,
)

LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}
CHUNK = 1000


def _chunks(items, size=CHUNK):
    for start in range(0, len(items), size):
        yield items[start : start + size]


class Command(BaseCommand):
    help = "Seed a local database with synthetic providers, jobs, listings and notifications."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-synthetic", action="store_true")
        parser.add_argument("--allow-nonlocal-host", action="store_true")
        parser.add_argument("--providers", type=int, default=0)
        parser.add_argument("--jobs", type=int, default=0)
        parser.add_argument("--listings", type=int, default=0)
        parser.add_argument("--notifications", type=int, default=0)

    def handle(self, *args, **options):
        if not options["confirm_synthetic"]:
            raise CommandError("Pass --confirm-synthetic to acknowledge this writes fake data.")
        host = connection.settings_dict.get("HOST") or ""
        if (
            host not in LOCAL_HOSTS
            and not host.startswith("/")
            and not options["allow_nonlocal_host"]
        ):
            raise CommandError(
                f"Refusing: database host {host!r} is not local. Synthetic data must never reach "
                "a shared or production database (use --allow-nonlocal-host only for a "
                "disposable database)."
            )
        self.tag = uuid.uuid4().hex[:8]
        self.password_hash = make_password(
            os.environ.get("SYNTHETIC_PASSWORD") or secrets.token_urlsafe(24)
        )
        self.governorates = list(Governorate.objects.all())
        if not self.governorates:
            raise CommandError("No governorates: run `manage.py migrate` first (they are seeded).")
        with transaction.atomic():
            if options["providers"]:
                self._providers(options["providers"])
            if options["jobs"]:
                self._jobs(options["jobs"])
            if options["listings"]:
                self._listings(options["listings"])
            if options["notifications"]:
                self._notifications(options["notifications"])
        self.stdout.write(self.style.SUCCESS(f"seed_synthetic: done (run tag {self.tag})"))

    # -- helpers ----------------------------------------------------------------------------
    def _accounts(self, n: int, role: str, label: str) -> list[Account]:
        rows = [
            Account(
                email=f"{label}-{self.tag}-{i}@synthetic.invalid",
                full_name=f"Synthetic {label} {i}",
                role=role,
                password=self.password_hash,
            )
            for i in range(n)
        ]
        made: list[Account] = []
        for chunk in _chunks(rows):
            made.extend(Account.objects.bulk_create(chunk))
        return made

    def _gov(self, i: int) -> Governorate:
        return self.governorates[i % len(self.governorates)]

    # -- data sets --------------------------------------------------------------------------
    def _providers(self, n: int) -> None:
        accounts = self._accounts(n, AccountRole.PROVIDER, "provider")
        rows = [
            ProviderProfile(
                account=acct,
                provider_type=ProviderType.DOCTOR if i % 3 else ProviderType.MEDICAL_CENTER,
                display_name=f"Synthetic Provider {self.tag}-{i}",
                governorate=self._gov(i),
                verification_status=VerificationStatus.VERIFIED,
                is_visible=True,
            )
            for i, acct in enumerate(accounts)
        ]
        for chunk in _chunks(rows):
            ProviderProfile.objects.bulk_create(chunk)
        self.stdout.write(f"  providers: {n}")

    def _jobs(self, n: int) -> None:
        employer_count = max(1, n // 50)
        owners = self._accounts(employer_count, AccountRole.PROVIDER, "employer")
        employers = Employer.objects.bulk_create(
            [
                Employer(
                    name=f"Synthetic Hospital {self.tag}-{i}",
                    organization_type="HOSPITAL",
                    governorate=self._gov(i),
                    verification_status=VerificationStatus.VERIFIED,
                    verified_at=timezone.now(),
                    created_by=owner,
                )
                for i, owner in enumerate(owners)
            ]
        )
        now = timezone.now()
        rows = [
            JobPost(
                employer=employers[i % employer_count],
                created_by=owners[i % employer_count],
                title=f"Synthetic nurse {self.tag}-{i}",
                profession="NURSE",
                description="Synthetic posting for performance testing.",
                governorate=self._gov(i),
                employment_type="FULL_TIME",
                status="PUBLISHED",
                published_at=now - timedelta(minutes=i),
            )
            for i in range(n)
        ]
        for chunk in _chunks(rows):
            JobPost.objects.bulk_create(chunk)
        self.stdout.write(f"  jobs: {n} (employers: {employer_count})")

    def _listings(self, n: int) -> None:
        seller_count = max(1, n // 20)
        accounts = self._accounts(seller_count, AccountRole.REAL_ESTATE_SELLER, "seller")
        sellers = RealEstateSeller.objects.bulk_create(
            [
                RealEstateSeller(
                    account=acct,
                    seller_type=SellerType.OWNER,
                    display_name=f"Synthetic Seller {self.tag}-{i}",
                )
                for i, acct in enumerate(accounts)
            ]
        )
        now = timezone.now()
        rows = [
            PropertyListing(
                seller=sellers[i % seller_count],
                publication_status=PublicationStatus.PUBLISHED,
                published_at=now - timedelta(minutes=i),
                title=f"Synthetic listing {self.tag}-{i}",
                description="Synthetic listing for performance testing.",
                property_type=PropertyType.CLINIC,
                transaction_type=TransactionType.RENT,
                governorate=self._gov(i),
                district="Synthetic district",
                area_sqm=Decimal("120.00"),
                price=Decimal("1500000.00") + i,
                currency="IQD",
                facilities="Parking",
                contact_method=ContactMethod.PHONE,
                contact_phone="07700000000",
                expires_at=now + timedelta(days=30),
            )
            for i in range(n)
        ]
        made: list[PropertyListing] = []
        for chunk in _chunks(rows):
            made.extend(PropertyListing.objects.bulk_create(chunk))
        for chunk in _chunks(
            [ListingSuitableUse(listing=lst, use=SuitableUse.CLINIC) for lst in made]
        ):
            ListingSuitableUse.objects.bulk_create(chunk)
        self.stdout.write(f"  listings: {n} (sellers: {seller_count})")

    def _notifications(self, n: int) -> None:
        # One account owns them all: the realistic worst case for a very active user.
        (owner,) = Account.objects.bulk_create(
            [
                Account(
                    email=f"loadtest-user-{self.tag}@synthetic.invalid",
                    full_name="Synthetic load test user",
                    role=AccountRole.PATIENT,
                    password=self.password_hash,
                    email_verified_at=timezone.now(),
                )
            ]
        )
        rows = [
            Notification(
                recipient=owner,
                category=NotificationCategory.RESERVATION,
                event_type=NotificationEventType.RESERVATION_STATUS_CHANGED,
                resource_type="RESERVATION",
                resource_id=uuid.uuid4(),
                dedupe_key=f"synthetic:{self.tag}:{i}",
                payload={"status": "CONFIRMED"},
                read_at=timezone.now() if i % 2 else None,
            )
            for i in range(n)
        ]
        for chunk in _chunks(rows):
            Notification.objects.bulk_create(chunk)
        self.stdout.write(f"  notifications: {n} for loadtest-user-{self.tag}@synthetic.invalid")
