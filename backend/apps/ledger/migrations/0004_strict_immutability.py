"""Audit 2026-11-06: ledger immutability without a session-level bypass.

Findings fixed here:
* `ledger_refuse_change()` returned early when `racheeta.ledger_purge = 'on'`. Any session can set a
  custom setting, so the application's own credentials could delete financial history.
* TRUNCATE bypasses row triggers: `TRUNCATE ledger_line` wiped history with no error.

Now the function has no bypass at all, and BEFORE TRUNCATE statement triggers refuse truncating a
table that holds any row.
The only way left to change ledger rows is to DISABLE the triggers, which PostgreSQL allows only to
the table OWNER (or a superuser). Production must therefore run the app with a role that neither
owns these tables nor holds UPDATE/DELETE/TRUNCATE on them (see `manage.py ledger_db_audit` and
docs/MARKETPLACE_COMMERCE.md §Database roles). The local demo cleaner, as the owner of its
disposable database, disables the triggers inside its own guarded transaction only.
"""

from django.db import migrations

STRICT = """
CREATE OR REPLACE FUNCTION ledger_refuse_change() RETURNS trigger AS $$
BEGIN
  -- An UPDATE that changes nothing alters no history (e.g. an ORM re-save of identical values).
  IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ledger rows are immutable (post a compensating entry)'
    USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
-- TRUNCATE is refused whenever the table holds any row (truncating an empty table destroys
-- nothing; the lock TRUNCATE takes first makes the check race-free).
CREATE OR REPLACE FUNCTION ledger_refuse_truncate() RETURNS trigger AS $$
DECLARE
  has_rows boolean;
BEGIN
  EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.%I)', TG_TABLE_SCHEMA, TG_TABLE_NAME)
    INTO has_rows;
  IF has_rows THEN
    RAISE EXCEPTION 'ledger rows are immutable (TRUNCATE refused on %)', TG_TABLE_NAME
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ledger_entry_no_truncate ON ledger_entry;
CREATE TRIGGER ledger_entry_no_truncate BEFORE TRUNCATE ON ledger_entry
  FOR EACH STATEMENT EXECUTE FUNCTION ledger_refuse_truncate();
DROP TRIGGER IF EXISTS ledger_line_no_truncate ON ledger_line;
CREATE TRIGGER ledger_line_no_truncate BEFORE TRUNCATE ON ledger_line
  FOR EACH STATEMENT EXECUTE FUNCTION ledger_refuse_truncate();
DROP TRIGGER IF EXISTS ledger_recovery_immutable ON ledger_recovery;
CREATE TRIGGER ledger_recovery_immutable BEFORE UPDATE OR DELETE ON ledger_recovery
  FOR EACH ROW EXECUTE FUNCTION ledger_refuse_change();
DROP TRIGGER IF EXISTS ledger_recovery_no_truncate ON ledger_recovery;
CREATE TRIGGER ledger_recovery_no_truncate BEFORE TRUNCATE ON ledger_recovery
  FOR EACH STATEMENT EXECUTE FUNCTION ledger_refuse_truncate();
-- Commission policy versions: a new rate is a NEW version, never an edit of an old one. Only the
-- bookkeeping timestamps may be re-saved; version, rate, effective date and note never change.
CREATE OR REPLACE FUNCTION ledger_policy_refuse_change() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE'
     AND NEW.id = OLD.id
     AND NEW.version IS NOT DISTINCT FROM OLD.version
     AND NEW.rate_percent IS NOT DISTINCT FROM OLD.rate_percent
     AND NEW.effective_from IS NOT DISTINCT FROM OLD.effective_from
     AND NEW.note IS NOT DISTINCT FROM OLD.note THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'commission policy versions are immutable (create a new version)'
    USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ledger_policy_immutable ON ledger_commission_policy;
CREATE TRIGGER ledger_policy_immutable BEFORE UPDATE OR DELETE ON ledger_commission_policy
  FOR EACH ROW EXECUTE FUNCTION ledger_policy_refuse_change();
DROP TRIGGER IF EXISTS ledger_policy_no_truncate ON ledger_commission_policy;
CREATE TRIGGER ledger_policy_no_truncate BEFORE TRUNCATE ON ledger_commission_policy
  FOR EACH STATEMENT EXECUTE FUNCTION ledger_refuse_truncate();
"""

# Reverse: back to the 0002 function (with its bypass), and drop the new triggers.
PREVIOUS = """
DROP TRIGGER IF EXISTS ledger_policy_no_truncate ON ledger_commission_policy;
DROP TRIGGER IF EXISTS ledger_policy_immutable ON ledger_commission_policy;
DROP FUNCTION IF EXISTS ledger_policy_refuse_change();
DROP TRIGGER IF EXISTS ledger_recovery_no_truncate ON ledger_recovery;
DROP TRIGGER IF EXISTS ledger_recovery_immutable ON ledger_recovery;
DROP TRIGGER IF EXISTS ledger_line_no_truncate ON ledger_line;
DROP TRIGGER IF EXISTS ledger_entry_no_truncate ON ledger_entry;
DROP FUNCTION IF EXISTS ledger_refuse_truncate();
CREATE OR REPLACE FUNCTION ledger_refuse_change() RETURNS trigger AS $$
BEGIN
  IF current_setting('racheeta.ledger_purge', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'ledger rows are immutable (post a compensating entry)';
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [("ledger", "0003_seller_receivable")]

    operations = [migrations.RunSQL(STRICT, PREVIOUS)]
