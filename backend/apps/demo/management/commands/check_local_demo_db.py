"""Exit non-zero unless the current database is the disposable local demo database (local_guard)."""

from django.core.management.base import BaseCommand, CommandError

from apps.demo.local_guard import LocalDemoRefused, assert_local_disposable_database


class Command(BaseCommand):
    help = "Verify the database is the disposable LOCAL demo database (refuses anything else)."

    def handle(self, *args, **options):
        try:
            name = assert_local_disposable_database()
        except LocalDemoRefused as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(f"OK: '{name}' is the disposable local demo database.")
        )
