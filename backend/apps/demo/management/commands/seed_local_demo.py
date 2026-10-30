"""Seed the DISPOSABLE LOCAL demo database: the staging demo dataset plus the local-only extras.

    scripts/local_demo.sh seed            # (reads local-demo/.env.demo; never committed)
    python manage.py seed_local_demo --dry-run

Refuses unless `local_guard` accepts the database. The shared demo password comes from
LOCAL_DEMO_PASSWORD (local-demo/.env.demo) and is never printed. `--with-admin` additionally
creates one local-only administrator (registered, so `clear_local_demo` removes it); the staging
command `seed_demo_data` never creates an administrator.
"""

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.demo.local_guard import LocalDemoRefused, assert_local_disposable_database


class Command(BaseCommand):
    help = "Seed the disposable local demo database (refuses any other database)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--with-admin", action="store_true")

    def handle(self, *args, **options):
        try:
            name = assert_local_disposable_database()
        except LocalDemoRefused as exc:
            raise CommandError(str(exc)) from exc
        password = os.environ.get("LOCAL_DEMO_PASSWORD", "")
        if len(password) < 16:
            raise CommandError("Set LOCAL_DEMO_PASSWORD (16+ characters) in local-demo/.env.demo.")
        self.stdout.write(f"Local demo database: {name}")
        # The staging gate is satisfied explicitly here, AFTER the stricter local guard passed.
        os.environ["DEMO_DATA_ENABLED"] = "true"
        os.environ["DEMO_PASSWORD"] = password
        os.environ["DEMO_LOCAL_EXTRAS"] = "1"
        if options["with_admin"]:
            os.environ["DEMO_LOCAL_ADMIN"] = "1"
        call_command("seed_demo_data", dry_run=options["dry_run"], stdout=self.stdout)
