"""Populate STAGING with a presentation-ready, clearly fictional demo ecosystem.

    DEMO_DATA_ENABLED=true DEMO_PASSWORD='<choose one>' python manage.py seed_demo_data

Safety:
  * refuses to run unless the environment variable DEMO_DATA_ENABLED=true (set it only on the
    staging service; never on production);
  * the shared password of the demo accounts comes from DEMO_PASSWORD (a platform variable, never
    in git) — or, for the INITIAL seed only, `--generate-password` prints a random one ONCE;
  * credentials are never rotated by a re-run: when demo accounts already exist,
    `--generate-password` is refused and DEMO_PASSWORD must match their current password;
  * idempotent: a second run reuses what exists (keys in the demo registry);
  * everything it creates is recorded so `clear_demo_data` removes exactly that.
"""

import os
import secrets
from collections import defaultdict

from django.contrib.auth.hashers import check_password
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Account
from apps.demo import seeder
from apps.demo.content import estate, jobs, market, people, providers
from apps.demo.models import DemoRecord

CATEGORY_LABELS = [
    ("Accounts", ["accounts.Account"]),
    ("Healthcare providers (practitioners + facilities)", ["providers.ProviderProfile"]),
    ("Provider services", ["providers.ServiceOffering"]),
    ("Facility memberships", ["providers.ProviderMembership"]),
    ("Availability slots", ["reservations.AvailabilitySlot"]),
    ("Reservations", ["reservations.Reservation"]),
    ("Reviews", ["reviews.Review"]),
    ("Offers", ["offers.Offer"]),
    ("Notifications", ["notifications.Notification"]),
    ("Conversations", ["chat.Conversation"]),
    ("Chat messages", ["chat.Message"]),
    ("Medical companies", ["marketplace.MedicalCompany"]),
    ("Product categories", ["marketplace.ProductCategory"]),
    ("Marketplace products", ["marketplace.Product"]),
    ("Employers", ["jobs.Employer"]),
    ("Job postings", ["jobs.JobPost"]),
    ("Job seeker profiles", ["jobs.JobSeekerProfile"]),
    ("Job applications", ["jobs.JobApplication"]),
    ("Recruitment messages", ["jobs.RecruitmentMessage"]),
    ("Real-estate sellers", ["real_estate.RealEstateSeller"]),
    ("Real-estate listings", ["real_estate.PropertyListing"]),
]


def planned_counts() -> list[tuple[str, int]]:
    return [
        ("Practitioners", len(providers.PRACTITIONERS)),
        ("Facilities", len(providers.FACILITIES)),
        ("Pharmaceutical companies", sum(1 for c in market.COMPANIES if c[3] == "pharma")),
        ("Medical-equipment companies", sum(1 for c in market.COMPANIES if c[3] == "equipment")),
        ("Marketplace products", len(market.PRODUCTS)),
        ("Job postings", len(jobs.JOBS)),
        ("Job seekers / applications", f"{len(jobs.SEEKERS)} / {len(jobs.APPLICATIONS)}"),
        ("Real-estate listings", len(estate.LISTINGS)),
        ("Reviews", sum(len(v) for v in people.REVIEW_PLAN.values())),
        ("Patients", len(people.PATIENTS)),
    ]


def registered_account_hashes() -> set[str]:
    """Distinct password hashes of the demo accounts that are registered AND still exist."""
    records = DemoRecord.objects.filter(model_label="accounts.Account")
    pks = list(records.values_list("object_pk", flat=True))
    return set(Account.objects.filter(pk__in=pks).values_list("password", flat=True))


class Command(BaseCommand):
    help = "Seed the staging database with fictional demo data (reversible with clear_demo_data)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show the plan; write nothing.")
        parser.add_argument(
            "--generate-password",
            action="store_true",
            help="Use a random shared password and print it once (instead of DEMO_PASSWORD).",
        )

    def handle(self, *args, **options):
        if os.environ.get("DEMO_DATA_ENABLED", "").lower() != "true":
            raise CommandError(
                "Refusing: DEMO_DATA_ENABLED is not 'true'. Demo data is for STAGING only; set "
                "that variable on the staging service (never on production)."
            )
        if options["dry_run"]:
            existing = DemoRecord.objects.count()
            self.stdout.write("seed_demo_data --dry-run (nothing is written). Would create:")
            for label, count in planned_counts():
                self.stdout.write(f"  {label}: {count}")
            self.stdout.write(
                f"Demo registry currently holds {existing} rows"
                + (" (a re-run reuses them)." if existing else " (empty: first seed).")
            )
            return
        existing_hashes = registered_account_hashes()
        password = os.environ.get("DEMO_PASSWORD", "")
        generated = False
        if options["generate_password"]:
            if existing_hashes:
                raise CommandError(
                    "Demo accounts already exist. --generate-password is only valid for the "
                    "initial seed. Use the existing demo credential (DEMO_PASSWORD) or clear the "
                    "demo dataset first (clear_demo_data --yes)."
                )
            password, generated = secrets.token_urlsafe(18), True
        if len(password) < 12:
            raise CommandError(
                "Set DEMO_PASSWORD (at least 12 characters, a platform variable — not in git) or "
                "pass --generate-password."
            )
        if existing_hashes and not all(check_password(password, h) for h in existing_hashes):
            raise CommandError(
                "DEMO_PASSWORD does not match the password of the existing demo accounts. A re-run "
                "never changes demo credentials: use the current demo password, or clear the demo "
                "dataset first (clear_demo_data --yes) to seed with a new one."
            )
        self.stdout.write("Seeding demo data ...")
        runner = seeder.DemoSeeder(password=password, stdout=self.stdout)
        try:
            counts = runner.run()
        except Exception:
            # Phases before the failure are committed and registered; if they created accounts
            # with a generated password, that password must not be lost (a retry with
            # --generate-password is refused once accounts exist).
            if generated and registered_account_hashes():
                self._print_generated(password, partial=True)
            raise
        for warning in sorted(set(runner.warnings)):
            self.stdout.write(self.style.WARNING(f"  warning: {warning}"))
        self.stdout.write("Demo registry now holds:")
        grouped = defaultdict(int)
        for title, labels in CATEGORY_LABELS:
            grouped[title] = sum(counts.get(label, 0) for label in labels)
            self.stdout.write(f"  {title}: {grouped[title]}")
        self.stdout.write(
            f"  (all registered rows, including side effects: {sum(counts.values())})"
        )
        if generated:
            self._print_generated(password)
        self.stdout.write(self.style.SUCCESS("seed_demo_data: done. Reverse with clear_demo_data."))

    def _print_generated(self, password: str, *, partial: bool = False) -> None:
        if partial:
            self.stdout.write(
                self.style.WARNING(
                    "The seed failed after demo accounts were created. They use the generated "
                    "password below; retry with DEMO_PASSWORD set to it (or clear and start over)."
                )
            )
        self.stdout.write(
            self.style.WARNING(f"Shared demo password (shown once, store it safely): {password}")
        )
