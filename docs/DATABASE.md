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

### `geography_country`, `geography_governorate`, `geography_city`

Bilingual reference data (`name_ar`, `name_en`), `slug`, `sort_order`,
`is_active`, UUID ids. Unique: `(country, slug)`, `(governorate, slug)`.
FKs are `PROTECT`. Iraq is seeded by `geography.0002_seed_iraq` from
`apps/geography/seed_iraq.py`; add data only through a new migration.

### `specialties_specialty`

`slug` (unique), `name_ar`, `name_en`, nullable self-FK `parent` (PROTECT),
`sort_order`, `is_active`. Seeded by `specialties.0002_seed_specialties`.

### `providers_profile`

| Column | Notes |
| --- | --- |
| `account_id` | OneToOne → `accounts_account` (CASCADE) |
| `provider_type` | enum in code (`ProviderType`) |
| `display_name`, `about`, `phone`, `public_email`, `website`, `address`, `image_url` | text |
| `governorate_id` (PROTECT, required), `city_id` (PROTECT, nullable) | city must belong to governorate (validated in serializer) |
| `latitude`, `longitude` | decimal(9,6); check `providers_profile_coordinates_valid` (ranges) and `providers_profile_coordinates_both_or_none` |
| `verification_status`, `verification_note`, `verification_requested_at`, `verification_changed_at`, `verified_at` | admin-controlled |
| `is_visible` | provider-controlled |
| M2M `providers_profile_specialties` | |

Indexes: `providers_profile_discover_idx (verification_status, is_visible,
provider_type)` — matches the discovery filter prefix; `providers_profile_geo_idx
(governorate, city)`.

### `providers_membership`

`practitioner_id`, `facility_id` (both → `providers_profile`, CASCADE),
`status` (PENDING/ACTIVE/REJECTED/ENDED), `initiated_by`, `role_title`,
`responded_at`, `joined_at`, `ended_at`. Constraints: not-self
(`providers_membership_not_self`), partial unique
`providers_membership_one_live_per_pair` on `(practitioner, facility)` where
status ∈ {PENDING, ACTIVE}. Indexes on `(facility, status)` and
`(practitioner, status)`.

### `providers_service`

`provider_id` (CASCADE), `title`, `description`, `specialty_id` (PROTECT,
nullable), `price` decimal(12,2) ≥ 0 (`providers_service_price_nonneg`),
`currency` (IQD default; allowed list in `settings.RACHEETA["CURRENCIES"]`),
`duration_minutes` > 0 or null (`providers_service_duration_positive`),
`is_active`. Unique `(provider, title)`; index `(provider, is_active)`.

### Phase 3 — audit, billing, jobs

| Table | Purpose / notable constraints |
| --- | --- |
| `audit_event` | actor (nullable FK), action, target_type/target_id, summary, JSON data; indexed by (target_type, target_id) and created_at |
| `billing_plan`, `billing_plan_entitlement` | plan catalogue; unique (plan, key); `price_amount` nullable (no prices seeded) |
| `billing_account` | unique (subject_type, subject_id) |
| `billing_subscription` | one live (PENDING/ACTIVE) subscription per account (partial unique index); `billing_subscription_event` history |
| `billing_payment_record` | minimal admin bookkeeping |
| `billing_credit_balance` (unique account+key), `billing_credit_transaction` | credits ledger |
| `billing_usage_counter` (unique account+key+period_start), `billing_usage_event` (unique account+key+reference when set) | atomic usage |
| `jobs_employer` | verification/recruitment status, optional FK to `providers_profile`, `created_by` |
| `jobs_employer_membership` | one live membership per account (partial unique), role, status |
| `jobs_seeker_profile` (one per account) + `jobs_seeker_experience`, `jobs_seeker_education`, `jobs_seeker_skill` (unique profile+name_normalized), `jobs_seeker_language` (unique profile+language), `jobs_seeker_credential` | structured résumé, no files |
| `jobs_post`, `jobs_post_transition` | status, moderation note/flags, featured window, deadline; indexes on (status, published_at), profession, governorate |
| `jobs_application` (unique job+job_seeker), `jobs_application_transition` | snapshot JSON of the profile at apply time |
| `jobs_interview_request`, `jobs_recruitment_message` | scoped to an application; messages immutable |
| `jobs_saved_candidate` (unique employer+job_seeker), `jobs_invitation` (unique job+job_seeker), `jobs_talent_search_query` (unique employer+signature+day) | talent marketplace |

Migrations: `audit/0001`, `billing/0001`, `billing/0002_seed_plans` (data), `jobs/0001`.

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
