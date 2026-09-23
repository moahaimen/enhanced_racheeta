# Backup and restore

The only stateful component is PostgreSQL. (Object storage for media is
**planned**; when it exists, add its bucket to this document.)

## Backup

Logical dump with `pg_dump` (custom format, compressed):

```bash
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-privileges \
  --file "racheeta-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

- Run from any machine with `pg_dump` 16 and network access to the database
  (Railway: use the public `DATABASE_URL` from the plugin's *Connect* tab, or
  `railway run`).
- Store dumps outside Railway (object storage, encrypted local disk). Keep at
  least 7 daily + 4 weekly copies.
- Railway's own volume snapshots/backups are a convenience, not the strategy:
  they do not survive leaving the platform.
- **Planned:** scheduled dump via GitHub Actions cron to object storage.

## Restore

Into an empty database:

```bash
createdb racheeta_restore
pg_restore --no-owner --no-privileges --dbname "postgres://…/racheeta_restore" racheeta-<stamp>.dump
```

Then point `DATABASE_URL` at it and run `python manage.py migrate` (no-op if
the dump is current; applies newer migrations otherwise).

## Verify a backup (do this monthly)

1. Restore into a throwaway database as above.
2. `python manage.py check` and `python manage.py showmigrations` against it.
3. Log in to the admin and open a few accounts.
4. Drop the throwaway database.

## Secrets

`SECRET_KEY` is not stored in the database. Keep a copy of every production
environment variable in the owner's password manager: a database dump alone
does not restore a working deployment (sessions and password-reset tokens are
signed with `SECRET_KEY`; JWTs are signed with it too, so rotating it logs
everyone out).
