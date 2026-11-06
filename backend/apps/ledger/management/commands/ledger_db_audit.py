"""Report whether the database role this app connects with could change financial history.

    manage.py ledger_db_audit                 # report (exit 0)
    manage.py ledger_db_audit --strict        # exit 1 if any problem (use before production)
    manage.py ledger_db_audit --grant-sql ROLE  # print the GRANT/REVOKE statements for ROLE

Read-only: it never changes roles or privileges. Locally the developer role owns the tables, so a
plain run lists that as a problem on purpose — it is exactly what production must not do.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.ledger import dbroles


class Command(BaseCommand):
    help = "Audit database-level protection of the marketplace ledger."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--grant-sql", metavar="ROLE")

    def handle(self, *args, **options):
        if options["grant_sql"]:
            for statement in dbroles.runtime_role_sql(options["grant_sql"]):
                self.stdout.write(statement)
            return
        report = dbroles.audit()
        self.stdout.write(f"connected as {report['user']} (superuser: {report['superuser']})")
        for table, info in report["tables"].items():
            granted = ",".join(p for p, ok in info["privileges"].items() if ok) or "-"
            self.stdout.write(f"  {table}: owner={info['owner']} risky_privileges={granted}")
        if not report["problems"]:
            self.stdout.write(
                self.style.SUCCESS("OK: the application role cannot alter ledger history.")
            )
            return
        for problem in report["problems"]:
            self.stdout.write(self.style.WARNING(f"PROBLEM: {problem}"))
        if options["strict"]:
            raise CommandError(f"{len(report['problems'])} ledger protection problem(s).")
