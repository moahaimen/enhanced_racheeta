# Medical Marketplace (Phase 6)

A **B2B** catalogue: verified medical companies publish products; verified
healthcare providers browse the products whose category targets them.
Targeting is decided by the backend from administrator rules — a company or a
browser can never choose, widen or inspect an audience.

## Entities (`apps/marketplace`)

| Model | Owner | Notes |
| --- | --- | --- |
| `MedicalCompany` | the `MEDICAL_COMPANY` account (one-to-one) | name, description, contact, governorate/city/address; `verification_status` UNVERIFIED → PENDING (company request) → VERIFIED / REJECTED / SUSPENDED / UNVERIFIED (administrator only). `can_publish` = VERIFIED and account active. |
| `ProductCategory` | administrators (Django admin) | bilingual names, unique slug, optional parent, sort order, `is_active`. **No taxonomy is seeded**; the Master Plan's list is examples only. |
| `ProductAudience` | administrators (Django admin, inline on the category) | one targeting rule: `provider_type` and/or `specialty`. A rule with neither is refused (model validation + DB check constraint `marketplace_audience_meaningful`); duplicates are refused (`marketplace_audience_unique`). |
| `Product` | the company | category, title, description, brand, model, `price` (nullable = price on request, ≥ 0, DB check), `currency` (settings allow-list IQD/USD), `is_active` (the company's publication switch; created inactive). |

Companies and products are **inspection-only** in Django admin (their state
changes go through the services, which lock, validate and audit). Categories
and audience rules are editable there.

## Verified identity (ADR-045)

Exposure and targeting rest only on identity an administrator reviewed:

- **Company**: `name`, `governorate`, `city`, `address`, `website` are frozen
  while the company is PENDING or VERIFIED (typed `identity_locked`, 400, per
  field). `description`, `phone` and `public_email` stay editable; resending
  the current value is not a change. To change identity, an administrator moves
  the company back to UNVERIFIED (products are hidden at once), the company
  edits, then requests review again.
- **Provider**: `provider_type` and `specialty_ids` are frozen while the
  provider profile is PENDING or VERIFIED (same rule, same error code; the type
  keeps its historical `type_locked` code). Only a VERIFIED provider browses, so
  any specialty change happens outside verification and marketplace access
  returns only after re-verification.

Both checks run on the **locked** row inside the write's transaction, and the
administrator's verification decision locks the same row. **VERIFIED is
granted only from PENDING** — the owner's review request is what freezes the
identity — so the re-review path is: edit while UNVERIFIED/REJECTED/SUSPENDED →
request verification (PENDING, identity frozen) → administrator decides.
UNVERIFIED/REJECTED/SUSPENDED → VERIFIED is refused (`invalid_transition`),
for companies and providers alike. The web forms disable the frozen fields and
never send them.

## Targeting algorithm (`ProductQuerySet.targeted_for(provider)`)

A product is shown to a provider only when **all** hold:

1. `product.is_active`;
2. the company is `VERIFIED` and its account is active;
3. the category is active;
4. at least one **active** audience rule of the category matches the provider:
   - `rule.provider_type` is empty **or** equals `provider.provider_type`; **and**
   - `rule.specialty` is empty **or** is one of the provider's specialties.

All rule conditions sit in one `filter()` call, so they apply to the **same**
rule row (a type from one rule and a specialty from another never combine).
The list, the category filter and the detail endpoint all use this one
queryset, so a product outside the audience is absent from every page and its
detail answers the standard 404 whatever the client sends. State changes
(company suspension, category deactivation, rule deactivation, account
deactivation) take effect on the next request; there is no scheduled worker.

**Who may browse** (`marketplace.view_targeted_products`): a `PROVIDER`
account whose provider profile is `VERIFIED`, decided by
`current_verified_provider(account)`, which re-reads the profile from the
database when the catalogue queryset is built (the permission check is only an
early answer). `targeted_for` then reads the provider's verification, type and
specialties through subqueries in the same SQL statement that returns the
products, so a provider suspended or unverified mid-request gets 403 or no rows,
and specialties it could edit once unlocked are never matched. The provider's public
`is_visible` flag is **not** required — hiding a practice from patient search
does not remove its B2B access. Unverified providers, patients, companies and
anonymous users are refused (403 / 401).

## Publication gate (`services.update_product`)

Creating a product never publishes it. Activation (and any edit of an active
product) re-checks, on locked rows (company → product → category):

- the company can publish (`company_not_verified`, 403 otherwise);
- the category is active and has at least one active audience rule
  (`category_unavailable`, 409 otherwise).

An unverified, rejected or suspended company keeps and edits its drafts and
history; deactivation is always possible. Exposure is derived at read time
from current state, so a later suspension hides products immediately without
touching them.

The product payload accepts only `category, title, description, brand,
model_name, price, currency`. Any of `company, is_active, provider_type(s),
specialty/specialties/specialty_ids, audience(s), target(s), targeting` is
refused with `field_not_allowed`; publication goes through
`/activate` and `/deactivate`.

## API (`/api/v1/`)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| GET | `marketplace/categories` | anyone | active categories, unpaginated reference data |
| GET | `marketplace/products` | verified provider | targeted, paginated (20), newest first (`created_at`, `id`), `?category=` |
| GET | `marketplace/products/{id}` | verified provider | same targeting; 404 otherwise |
| GET/POST/PATCH | `marketplace/company` | `MEDICAL_COMPANY` | own profile; one per account (`already_exists`, 409) |
| POST | `marketplace/company/verification/request` | company | UNVERIFIED/REJECTED → PENDING |
| GET | `marketplace/company/dashboard` | company | backend counts: total, active, inactive, exposable, verification state |
| GET/POST | `marketplace/company/products` | company | own products, paginated, newest first; create (inactive) |
| GET/PATCH | `marketplace/company/products/{id}` | company | foreign ids → 404 |
| POST | `marketplace/company/products/{id}/activate` · `/deactivate` | company | publication gate above |
| GET | `admin/marketplace/companies` | staff | paginated, `?verification_status=` |
| POST | `admin/marketplace/companies/{id}/verification` | staff | `{status, note?}` |

Audit events: `marketplace.company.created`,
`marketplace.company.verification_requested`,
`marketplace.company.verification_set`, `marketplace.product.created`,
`marketplace.product.updated`.

## Web

- `/marketplace`, `/marketplace/products/:id` (PROVIDER): the backend list and
  detail, URL-backed page and category filter, shared Pagination; no audience
  logic in React.
- `/company` (MEDICAL_COMPANY): onboarding, verification state and request,
  backend dashboard, product create/edit, publish/unpublish (Publish is not
  rendered while the company cannot publish), paginated own products, profile.
- Header links and the home "Medical marketplace" card are live.

## Deferred (explicitly out of Phase 6)

- **Product images/files** — no uploads until production object storage and a
  media pipeline exist (no local/Railway disk, no S3/R2/B2 configuration).
- **ProductCampaign, advertising, paid placement, payments** — Phase 8.
- Stock, cart, checkout, orders, shipping, purchase requests, chat — not in the
  requirement.
