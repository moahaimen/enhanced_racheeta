# Data migration from the legacy Racheeta system

> **Status (Phase 12A): no legacy data migration is authorized, designed in detail, or
> performed.** The master plan says "do not migrate old data yet" (§29 "First Task", which also says not to touch the old production database), and this phase
> neither opened nor connected to the legacy database. This document only records what a future,
> separately authorized migration would have to decide and prove. Racheeta 2.0 launches with an
> empty database plus the seeded reference data (Iraqi governorates/cities, specialties, billing
> plans).

## 1. What exists

- The legacy Flutter app is at `~/Documents/RACHEETA` on the owner's development machine; the
  legacy repository (`virach`) and its production data are **read-only references** and must never be
  modified by this project.
- This repository has not inspected the legacy schema or data; nothing here describes it. Any
  mapping below is a template, not a finding.

## 2. Decision for 12A

**Do not migrate.** Reasons: (a) no owner authorization; (b) the 2.0 data model was deliberately
redesigned (structured profiles, separate account/role model, backend-decided pricing — the plan
forbids reproducing the legacy denormalised IDs) so a migration is a transformation project, not a
copy; (c) personal data of real patients and providers is involved, which needs an explicit legal
basis and consent review (owner/legal); (d) launching clean lets staging and production be
validated without a data-quality variable.

## 3. If the owner later authorizes a migration

It becomes its own phase (suggested name: *Phase 12D — Legacy data import*) with its own prompt,
branch and review. Minimum content:

1. **Authorization and scope in writing:** which entities (accounts? providers? reservations
   history? chat?), from which source, for which users, legal basis, retention.
2. **Read-only access:** a database read replica or a dump restored into a private scratch database.
   Never connect the importer to the legacy production database with write rights.
3. **Inventory and mapping document:** every legacy table/collection → 2.0 model and field,
   transformation rule, what is dropped and why, how roles map to `AccountRole`, how duplicate
   people/phones/emails are resolved.
4. **Passwords and identities:** legacy password hashes cannot be assumed compatible; the default
   plan is *no password import* — imported accounts get the password-reset flow (requires working
   e-mail) or Firebase sign-in once activated. Never email passwords.
5. **Importer design:** an idempotent management command (re-runnable, keyed by a stable legacy id
   stored in an `external_id`/provenance column added by a reviewed migration), batch-transactional,
   with `--dry-run` that validates everything and writes nothing, and a report of
   created/updated/skipped/rejected rows with reasons.
6. **Reconciliation:** counts per entity (legacy vs imported + explained rejects), spot checks of N
   random records per entity compared by a human, referential integrity checks, a query that proves no
   record is visible publicly that the owner did not approve (listings, providers need re-verification
   by the 2.0 rules; imports must land *unverified/unpublished*).
7. **Rehearsals:** full import into staging from a recent dump at least twice; record duration and
   defects; the second run must be a no-op.
8. **Cutover plan:** freeze window, final import, verification checklist, rollback (drop the imported
   rows by provenance marker or restore the pre-import backup — take one first,
   `docs/BACKUP_RESTORE.md`).
9. **Privacy:** minimise fields, mask data in logs and reports, keep the working copies encrypted and
   delete them after the retention period.

## 4. Owner decisions needed before any migration

- Is legacy data to be migrated at all, or do users re-register?
- Which user groups (providers only? patients?) and what consent/communication to users.
- Who provides the legacy export, and in what form (SQL dump, Firebase export, API).
- Whether migrated providers keep any "verified" status or must be re-verified (recommended:
  re-verify).

## 5. Explicitly not done in 12A

No legacy connection, no import code, no schema changes for provenance, no sample or real legacy
rows anywhere in the repository, CI, or backups.
