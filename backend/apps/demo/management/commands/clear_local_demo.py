"""Clear the demo rows of the DISPOSABLE LOCAL demo database (refuses any other database)."""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.demo.local_guard import LocalDemoRefused, assert_local_disposable_database


class Command(BaseCommand):
    help = "clear_demo_data, but only on the disposable local demo database."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true")

    def handle(self, *args, **options):
        try:
            assert_local_disposable_database()
        except LocalDemoRefused as exc:
            raise CommandError(str(exc)) from exc
        call_command(
            "clear_demo_data", dry_run=options["dry_run"], yes=options["yes"], stdout=self.stdout
        )
