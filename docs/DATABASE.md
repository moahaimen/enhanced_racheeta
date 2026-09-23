# Database

PostgreSQL 16. Configured only through `DATABASE_URL`. No other engine is
supported or tested.

## Rules

- Every schema change ships as a migration in the same commit.
- Never edit a production schema by hand.
- Integrity lives in the database: foreign keys, unique constraints, check
  constraints. Frontend validation is a convenience, not a guarantee.
- New domain entities extend `apps.core.models.BaseModel` (UUID id + timestamps).
- Soft deletion only when there is a business reason; document it in the model.
- Add indexes with the query that needs them, not speculatively.

## Current schema (application tables)

### `accounts_account`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `email` | varchar(254) | unique; **also** unique on `LOWER(email)` (`accounts_account_email_ci_unique`) |
| `password` | varchar(128) | Django hash; unusable for social accounts |
| `full_name` | varchar(150) | |
| `phone_number` | varchar(32) | `''` when unknown; unique when non-empty (`accounts_account_phone_unique_when_set`) |
| `role` | varchar(32) | enum in code (`apps/accounts/roles.py`); indexed |
| `preferred_language` | varchar(2) | `ar` (default) or `en` |
| `email_verified` | bool | default false; no verification flow yet |
| `is_active` | bool | |
| `is_staff` | bool | Django admin access |
| `is_superuser` | bool | |
| `last_login` | timestamptz null | |
| `created_at` / `updated_at` | timestamptz | |

Check constraint `accounts_account_admin_role_requires_staff`:
`role <> 'ADMIN' OR is_staff = true`.

Django's `auth` tables (`auth_group`, `auth_permission`, M2M tables) exist
because of `PermissionsMixin`; they are reserved for admin-site permissions,
not for API authorization.

### SimpleJWT

`token_blacklist_outstandingtoken`, `token_blacklist_blacklistedtoken` — one
row per issued refresh token, one per revoked token. Prune periodically with
`python manage.py flushexpiredtokens` (a scheduled job is **planned**).

## Migrations

```bash
cd backend
.venv/bin/python manage.py makemigrations <app>
.venv/bin/python manage.py migrate
.venv/bin/python manage.py makemigrations --check --dry-run   # CI runs this
```

Migration files live in `backend/apps/<app>/migrations/` and are committed.

## Backups

See `BACKUP_RESTORE.md`.
