"""The local demo guard refuses every database that is not the disposable local demo database."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.demo import local_guard

pytestmark = pytest.mark.django_db

SAFE = {
    "RACHEETA_LOCAL_DEMO": "1",
    "DATABASE_URL": "postgres://me@localhost:5432/racheeta_workspace_demo",
}


def _db(host="localhost", name="racheeta_workspace_demo"):
    """A database description for the guard (the live connection settings are never mutated)."""
    return {"HOST": host, "NAME": name}


def test_requires_the_explicit_local_opt_in():
    reasons = local_guard.check({**SAFE, "RACHEETA_LOCAL_DEMO": ""}, _db())
    assert any("RACHEETA_LOCAL_DEMO" in r for r in reasons)


@pytest.mark.parametrize(
    "var", ["RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_NAME"]
)
def test_refuses_whenever_a_railway_variable_is_present(var):
    assert any("Railway" in r for r in local_guard.check({**SAFE, var: "x"}, _db()))


@pytest.mark.parametrize(
    "host,url",
    [
        ("db.internal.railway.app", "postgres://u:p@db.internal.railway.app:5432/racheeta_demo"),
        ("x.proxy.rlwy.net", "postgres://u:p@x.proxy.rlwy.net:1234/racheeta_demo"),
        ("10.0.0.5", "postgres://u:p@10.0.0.5:5432/racheeta_demo"),
        ("db.example.com", "postgres://u:p@db.example.com:5432/racheeta_demo"),
    ],
)
def test_refuses_remote_hosts(host, url):
    reasons = local_guard.check({**SAFE, "DATABASE_URL": url}, _db(host, "racheeta_demo"))
    assert any("not this machine" in r for r in reasons)


def test_refuses_a_database_whose_name_is_not_a_demo():
    assert any(
        "does not contain 'demo'" in r for r in local_guard.check(SAFE, _db(name="racheeta_dev"))
    )


def test_refuses_a_local_demo_named_database_without_the_marker():
    # local host, demo-looking name, opt-in set: still refused, because pg_database has no marker
    reasons = local_guard.check(SAFE, _db(name="racheeta_unmarked_demo"))
    assert reasons == [
        "database 'racheeta_unmarked_demo' does not carry the disposable-demo marker"
    ]


def test_local_commands_refuse_and_change_nothing_outside_the_disposable_database(monkeypatch):
    monkeypatch.delenv("RACHEETA_LOCAL_DEMO", raising=False)
    for command, kwargs in (
        ("check_local_demo_db", {}),
        ("seed_local_demo", {}),
        ("clear_local_demo", {"yes": True}),
    ):
        with pytest.raises(CommandError, match="local demo guard"):
            call_command(command, **kwargs)
    from apps.accounts.models import Account

    assert not Account.objects.exists()


def test_the_guard_never_reveals_credentials():
    reasons = local_guard.check(
        {**SAFE, "DATABASE_URL": "postgres://user:SuperSecret@db.example.com/racheeta_demo"},
        _db("db.example.com", "racheeta_demo"),
    )
    assert "SuperSecret" not in " ".join(reasons)


def test_the_guard_never_mutates_the_live_connection_settings():
    from django.db import connection

    before = dict(connection.settings_dict)
    local_guard.check(SAFE, _db("db.example.com", "racheeta_demo"))
    local_guard.check(SAFE)
    assert connection.settings_dict == before
