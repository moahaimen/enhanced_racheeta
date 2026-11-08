"""Who can change financial history at the DATABASE level (audit 2026-11-06).

Triggers make ledger rows append-only, but PostgreSQL lets a SUPERUSER or the table OWNER disable
triggers, and a role with UPDATE/DELETE/TRUNCATE privileges is only stopped by the trigger itself.
So production must connect the application with a RUNTIME role that:

* is not a superuser,
* does not own the ledger tables (the migration role owns them),
* holds only SELECT and INSERT on the append-only tables.

`audit()` reports the current connection against these rules; `runtime_role_sql(role)` returns the
statements an operator runs (as the owner) to configure such a role. Nothing here runs on its own.
"""

from __future__ import annotations

from django.db import connection

APPEND_ONLY = ("ledger_entry", "ledger_line", "ledger_recovery", "ledger_commission_policy")
MUTABLE = ("ledger_settlement",)  # payout batches change status (DRAFT -> PAID / CANCELLED)
FORBIDDEN = ("UPDATE", "DELETE", "TRUNCATE", "TRIGGER")
REQUIRED_TRIGGERS = {
    "ledger_entry": ("ledger_entry_immutable", "ledger_entry_no_truncate"),
    "ledger_line": ("ledger_line_immutable", "ledger_line_no_truncate"),
    "ledger_recovery": ("ledger_recovery_immutable", "ledger_recovery_no_truncate"),
    "ledger_commission_policy": ("ledger_policy_immutable", "ledger_policy_no_truncate"),
}


def audit(conn=connection) -> dict:
    with conn.cursor() as cursor:
        cursor.execute("SELECT current_user, rolsuper FROM pg_roles WHERE rolname = current_user")
        user, superuser = cursor.fetchone()
        tables = {}
        for table in APPEND_ONLY + MUTABLE:
            cursor.execute(
                "SELECT pg_get_userbyid(c.relowner) FROM pg_class c WHERE c.relname = %s",
                [table],
            )
            owner = (cursor.fetchone() or [None])[0]
            privileges = {}
            for privilege in FORBIDDEN:
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, %s)", [table, privilege]
                )
                privileges[privilege] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT t.tgname, t.tgenabled FROM pg_trigger t"
                " JOIN pg_class c ON c.oid = t.tgrelid"
                " WHERE c.relname = %s AND NOT t.tgisinternal",
                [table],
            )
            triggers = dict(cursor.fetchall())
            tables[table] = {"owner": owner, "privileges": privileges, "triggers": triggers}
        cursor.execute(
            "SELECT pg_get_functiondef(p.oid) FROM pg_proc p"
            " WHERE p.proname = 'ledger_refuse_change'"
        )
        row = cursor.fetchone()
    function_source = row[0] if row else ""
    problems = []
    if superuser:
        problems.append(f"the application connects as a superuser ({user})")
    for table, info in tables.items():
        if info["owner"] == user:
            problems.append(f"the application role owns {table} (it could disable its triggers)")
        if table in APPEND_ONLY:
            granted = [p for p, ok in info["privileges"].items() if ok]
            if granted and info["owner"] != user and not superuser:
                problems.append(f"the application role holds {', '.join(granted)} on {table}")
            for trigger in REQUIRED_TRIGGERS[table]:
                state = info["triggers"].get(trigger)
                if state is None:
                    problems.append(f"trigger {trigger} is missing on {table}")
                elif state == "D":
                    problems.append(f"trigger {trigger} is DISABLED on {table}")
    if not function_source:
        problems.append("ledger_refuse_change() is missing")
    elif "current_setting" in function_source:
        problems.append("ledger_refuse_change() still has a session-setting bypass")
    return {"user": user, "superuser": superuser, "tables": tables, "problems": problems}


def runtime_role_sql(role: str) -> list[str]:
    """Statements (run as the table owner) that give `role` exactly what the app needs."""
    quoted = '"' + role.replace('"', '""') + '"'
    statements = []
    for table in APPEND_ONLY:
        statements += [
            f"REVOKE ALL ON TABLE {table} FROM {quoted};",
            f"GRANT SELECT, INSERT ON TABLE {table} TO {quoted};",
        ]
    for table in MUTABLE:
        statements += [
            f"REVOKE ALL ON TABLE {table} FROM {quoted};",
            f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO {quoted};",
        ]
    return statements
