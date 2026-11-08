"""Refuse to run local demo tooling anywhere but a disposable database on this machine.

Every `*_local_demo` command calls `assert_local_disposable_database()` BEFORE it touches the
database. All of these must hold, otherwise nothing runs:

1. `RACHEETA_LOCAL_DEMO=1` is set (an explicit, local-only opt-in);
2. no Railway variable is present in the environment (`RAILWAY_*`), and the database URL does not
   mention a known hosting provider;
3. the database host is this machine (unix socket, `localhost`, `127.0.0.1`, `::1`);
4. the database name contains `demo`;
5. the database itself carries the marker comment `racheeta-disposable-local-demo`, which is set
   only when the disposable database is created (`scripts/local_demo.sh create-db`). A database
   that merely has a demo-looking name is refused.

The checks never print credentials. Staging/production protections of `seed_demo_data`
(`DEMO_DATA_ENABLED`) are untouched; this guard is an additional, stricter gate for local use.
"""

from __future__ import annotations

import os

from django.db import connection

MARKER = "racheeta-disposable-local-demo"
LOCAL_HOSTS = frozenset({"", "localhost", "127.0.0.1", "::1"})
REMOTE_HINTS = ("railway", "rlwy", "render.com", "amazonaws", "neon.tech", "supabase", "azure")


class LocalDemoRefused(Exception):
    """The current database is not a disposable local demo database."""


def check(environ=None, db=None) -> list[str]:
    """Reasons to refuse (empty list = safe). Pure checks first; the database is asked last.
    `db` defaults to the settings of the connection that would actually be used."""
    environ = os.environ if environ is None else environ
    db = connection.settings_dict if db is None else db
    host = str(db.get("HOST") or "")
    name = str(db.get("NAME") or "")
    url = str(environ.get("DATABASE_URL", "")).lower()
    reasons = []
    if environ.get("RACHEETA_LOCAL_DEMO") != "1":
        reasons.append("RACHEETA_LOCAL_DEMO=1 is not set")
    railway = sorted(k for k in environ if k.startswith("RAILWAY_"))
    if railway:
        reasons.append(f"Railway variables are present ({', '.join(railway)})")
    if any(hint in url or hint in host.lower() for hint in REMOTE_HINTS):
        reasons.append("the database URL points at a hosting provider")
    if host not in LOCAL_HOSTS:
        reasons.append(f"database host {host!r} is not this machine")
    if "demo" not in name:
        reasons.append(f"database name {name!r} does not contain 'demo'")
    if reasons:
        return reasons  # never connect to a database that already failed a static check
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
            [name],
        )
        row = cursor.fetchone()
    if not row or row[0] != MARKER:
        reasons.append(f"database {name!r} does not carry the disposable-demo marker")
    return reasons


def assert_local_disposable_database(environ=None) -> str:
    reasons = check(environ)
    if reasons:
        raise LocalDemoRefused("Refusing (local demo guard): " + "; ".join(reasons) + ".")
    return str(connection.settings_dict["NAME"])
