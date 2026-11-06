"""Ledger rows are immutable at the database level, and the 20% commission policy (version 1).

UPDATE/DELETE on ledger_entry / ledger_line raise unless the transaction set
`racheeta.ledger_purge = 'on'` — which only the guarded demo cleaner does, for registered demo rows.
"""

from django.db import migrations
from django.utils import timezone

GUARD = """
CREATE OR REPLACE FUNCTION ledger_refuse_change() RETURNS trigger AS $$
BEGIN
  IF current_setting('racheeta.ledger_purge', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'ledger rows are immutable (post a compensating entry)';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ledger_entry_immutable ON ledger_entry;
CREATE TRIGGER ledger_entry_immutable BEFORE UPDATE OR DELETE ON ledger_entry
  FOR EACH ROW EXECUTE FUNCTION ledger_refuse_change();
DROP TRIGGER IF EXISTS ledger_line_immutable ON ledger_line;
CREATE TRIGGER ledger_line_immutable BEFORE UPDATE OR DELETE ON ledger_line
  FOR EACH ROW EXECUTE FUNCTION ledger_refuse_change();
"""
UNGUARD = """
DROP TRIGGER IF EXISTS ledger_line_immutable ON ledger_line;
DROP TRIGGER IF EXISTS ledger_entry_immutable ON ledger_entry;
DROP FUNCTION IF EXISTS ledger_refuse_change();
"""


def seed_policy(apps, schema_editor):
    Policy = apps.get_model("ledger", "MarketplaceCommissionPolicy")
    if not Policy.objects.exists():
        Policy.objects.create(
            version=1,
            rate_percent="20.00",
            effective_from=timezone.datetime(2026, 1, 1, tzinfo=timezone.get_current_timezone()),
            note="Owner decision: 20% of eligible net merchandise value.",
        )


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial")]

    operations = [
        migrations.RunSQL(GUARD, UNGUARD),
        migrations.RunPython(seed_policy, migrations.RunPython.noop),
    ]
