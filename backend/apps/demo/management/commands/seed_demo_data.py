"""Populate STAGING with a presentation-ready, clearly fictional demo ecosystem.

    DEMO_DATA_ENABLED=true DEMO_PASSWORD='<choose one>' python manage.py seed_demo_data

Safety:
  * refuses to run unless the environment variable DEMO_DATA_ENABLED=true (set it only on the
    staging service; never on production);
  * the shared password of the demo accounts comes from DEMO_PASSWORD (a platform variable, never
    in git) — or `--generate-password` prints a random one ONCE to your terminal;
  * idempotent: a second run reuses what exists (keys in the demo registry);
  * everything it creates is recorded so `clear_demo_data` removes exactly that.
"""

import os
import secrets
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

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
        password = os.environ.get("DEMO_PASSWORD", "")
        generated = False
        if options["generate_password"]:
            password, generated = secrets.token_urlsafe(18), True
        if len(password) < 12:
            raise CommandError(
                "Set DEMO_PASSWORD (at least 12 characters, a platform variable — not in git) or "
                "pass --generate-password."
            )
        self.stdout.write("Seeding demo data ...")
        runner = seeder.DemoSeeder(password=password, stdout=self.stdout)
        counts = runner.run()
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
            self.stdout.write(
                self.style.WARNING(
                    f"Shared demo password (shown once, store it safely): {password}"
                )
            )
        self.stdout.write(self.style.SUCCESS("seed_demo_data: done. Reverse with clear_demo_data."))
