"""Remove ONLY the demo data created by `seed_demo_data`, or refuse.

    python manage.py clear_demo_data --dry-run     # show exactly what would be deleted
    python manage.py clear_demo_data --yes         # delete it (one transaction)

It deletes the rows recorded in the demo registry, plus rows that exist only because of them. If the
deletion would also delete or modify any row that cannot be proven to be demo-owned (for example a
real user who booked a demo provider), it stops, changes nothing, and names the rows.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.demo import cleaner
from apps.demo.models import DemoRecord


class Command(BaseCommand):
    help = "Delete the fictional demo data (and nothing else)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only; delete nothing.")
        parser.add_argument("--yes", action="store_true", help="Confirm the deletion.")

    def handle(self, *args, **options):
        if not DemoRecord.objects.exists():
            self.stdout.write("clear_demo_data: nothing registered; nothing to do.")
            return
        if not options["dry_run"] and not options["yes"]:
            raise CommandError("Pass --yes to delete, or --dry-run to preview.")
        try:
            plan = cleaner.execute(dry_run=options["dry_run"])
        except cleaner.ClearRefused as exc:
            raise CommandError(f"clear_demo_data refused and changed nothing: {exc}") from exc
        verb = "that would be deleted" if options["dry_run"] else "deleted"
        self.stdout.write(f"Registered demo rows {verb}:")
        for label, count in sorted(plan.registered.items()):
            self.stdout.write(f"  {label}: {count}")
        if plan.internal:
            self.stdout.write("Rows created later by activity among demo objects (also removed):")
            for label, count in sorted(plan.internal.items()):
                self.stdout.write(f"  {label}: {count}")
        if plan.links:
            self.stdout.write(f"Link rows (many-to-many): {sum(plan.links.values())}")
        if plan.stale_registry_rows:
            self.stdout.write(
                f"Registry rows whose object was already gone: {plan.stale_registry_rows}"
            )
        if options["dry_run"]:
            self.stdout.write("clear_demo_data --dry-run: nothing was deleted.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"clear_demo_data: removed {plan.deleted} rows. Staging is clean."
                )
            )
