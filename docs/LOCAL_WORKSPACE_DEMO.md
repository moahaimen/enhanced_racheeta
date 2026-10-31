# Local multi-workspace demo (branch `feat/local-racheeta-multiworkspace`)

Local-only work. Nothing here was pushed, deployed, or run against Railway, staging or production,
and the Flutter app was not touched. Results are in `docs/LOCAL_DEMO_TEST_MATRIX.md`.

## 1. Disposable database and commands

All database work runs against **`racheeta_workspace_demo`** on `localhost`. The database was created
by `scripts/local_demo.sh create-db` and carries the comment marker `racheeta-disposable-local-demo`.
Settings come from `local-demo/.env.demo`. The `local-demo/` folder is git-ignored, the file has mode
600, and it holds two generated passwords: the shared demo password and a **separate** local admin
password.

```bash
scripts/local_demo.sh create-db   # once: create the database and set the marker
scripts/local_demo.sh migrate     # guard, then migrate
scripts/local_demo.sh seed        # guard, migrate, seed_local_demo --with-admin
scripts/local_demo.sh dry-run     # what the seed would create
scripts/local_demo.sh clear-dry   # what clear would delete
scripts/local_demo.sh clear       # delete exactly the registered demo rows
scripts/local_demo.sh serve       # API  http://127.0.0.1:8010 (demo DB)
scripts/local_demo.sh web         # web  http://127.0.0.1:5180 (proxied to 8010)
scripts/local_demo.sh drop-db     # drop the disposable database (asks first)
```

**Guard** (`apps/demo/local_guard.py`). Every local command runs it first, and every local seed
phase runs it again. It refuses unless all of these hold:

- `RACHEETA_LOCAL_DEMO=1` is set.
- No `RAILWAY_*` variable is present, and the URL has no hosting-provider hint.
- The database host is this machine.
- The database name contains `demo`.
- The database carries the marker comment.

It reads the settings of the connection that would actually be used, and it never prints
credentials. The staging command's `DEMO_DATA_ENABLED` gate is unchanged.

**Lifecycle verified:** `seed` → `seed` (no-op, 1 646 rows) → `clear --dry-run` → `clear`
(removed 1 691 rows, including the audit and token rows created by demo activity) → `seed`
(1 646 rows again).

## 2. Account types and onboarding

`Account.account_type` is optional and additive. Registration accepts `account_type`; the server
derives the role (`ACCOUNT_TYPE_ROLE`) and rejects a contradicting `role`. The user cannot change the
type afterwards, because the profile update forbids it.

The web registration form offers grouped account types:

- people
- practitioners
- facilities
- businesses
- property

Sign-in and registration now land on `/dashboard` instead of `/profile`. A job seeker is a feature
any account can add (a résumé), not an account type.

## 3. Organizations, workspaces and the capability matrix

`apps/workspaces.OrganizationMember` links a personal account to **one** facility (`ProviderProfile`
of a facility type) or **one** business (`MedicalCompany`). This is separate from
`ProviderMembership` (practitioner ↔ facility) and from `EmployerMembership` (recruitment).

**Roles.** `OWNER` is implicit: it is the account that owns the organization and is never granted.
The grantable roles are `MANAGER`, `STAFF` and `VIEWER`.

| Capability | OWNER | MANAGER | STAFF | VIEWER |
|---|---|---|---|---|
| facility.view / company.view | ✓ | ✓ | ✓ | ✓ |
| facility.reservations.view | ✓ | ✓ | ✓ | ✓ |
| facility.reservations.manage | ✓ | ✓ | ✓ | – |
| company.orders.view | ✓ | ✓ | ✓ | ✓ |
| company.orders.manage | ✓ | ✓ | ✓ | – |
| company.quotes.view | ✓ | ✓ | ✓ | ✓ |
| company.quotes.respond | ✓ | ✓ | – | – |
| members.view | ✓ | ✓ | – | – |
| members.manage | ✓ | – | – | – |

**How access is decided** (`apps/workspaces/access.py`):

- The decision is re-read from the database on every request.
- An ended membership, a deactivated owner account or a malformed id means no access.
- An organization the caller has no role in returns **404**, so organizations cannot be enumerated.
- A missing capability returns **403**.

**`GET /api/v1/workspaces`** lists every workspace the account can open right now:

- personal
- practitioner
- facility (owned or as a member)
- business (owned or as a member)
- property
- employer
- job seeker
- administration

Each entry carries `org_id`, `path` and `team_path`. The web switcher (`/workspaces`) only renders
this list. `/workspace/:kind/:id` shows the counts, the facility reservations (with actions when the
role has the capability), the business order and quote links, and the team panel.

## 4. Commerce (`apps/commerce`)

**Business classification.** `MedicalCompany.business_type` is one of:

- pharmaceutical company
- scientific office
- medical supplies office
- equipment supplier
- assistive device store
- pharma distributor

Only the **retail** types (assistive device store, equipment supplier, medical supplies office) can
sell to consumers.

**Products.** Each product has:

- `sale_channel`: `B2B`, `B2C` or `BOTH`
- `is_restricted`: restricted or prescription items are **B2B only**, enforced by the database
  check constraint `marketplace_product_restricted_is_b2b`
- `stock_quantity`

Consumer products also need a category with `consumer_allowed`.

**Public store.** `/store/products` exposes only `Product.objects.consumer_store()`. No exact stock
figure is exposed, only `in_stock`.

**Orders.** `POST /orders` accepts only product ids and quantities:

- Products are locked in id order with `select_for_update`.
- Prices and the total come from the locked rows, so a tampered price is ignored.
- Stock is decremented under the lock (concurrency-tested).
- One order covers one store.
- Each line is limited to a quantity of 20, and an order to 20 lines.
- The buyer needs a verified e-mail address.
- A business cannot order from itself.
- Payment is cash on delivery or a manual transfer recorded by the store. This is demo only:
  nothing is charged and no card field exists.
- Cancelling restores the stock. Cash on delivery becomes `PAID` on delivery. A paid order that is
  cancelled becomes `REFUND_DUE`.
- Every step is audited and sends a transactional notification.

**B2B quotes** (`/quotes`, `/merchant/quotes`):

- A quote can only be requested for a product that `targeted_for(provider)` admits, so a forged
  product id returns 404.
- Each requester can have one open quote per product.
- The business sees only the requester's display name and type. It gets no e-mail or phone number.

## 5. Ads, preferences and outreach

**Preferences.** `apps/preferences.MarketingPreference` has these fields and defaults:

| Field | Purpose | Default |
|---|---|---|
| `show_sponsored_products` | Display | on |
| `real_estate_promotions` | Outreach (opt-in) | off |
| `job_alerts` | Outreach (opt-in) | off |
| `offers_and_news` | Outreach (opt-in) | off |
| `channel_in_app` | Channel | on |
| `channel_email` | Channel (inactive in the demo) | off |
| `channel_push` | Channel (inactive in the demo) | off |

**Display is separate from consent.** The sponsored feed honours `show_sponsored_products`. A
sponsored-product *notification* needs the separate opt-in `offers_and_news`. Transactional
notifications (reservations, orders, quotes) never consult preferences.

**Outreach** (`apps/preferences/outreach.deliver`) runs only after the campaign activation or the
promotion approval has committed (`on_commit(robust=True)`). For each recipient it checks:

- consent, evaluated at delivery time
- the account is active, under a row lock
- dedupe: `sponsored:{campaign}:{account}` or `promotion:{promotion}:{account}`
- at most **3 marketing notifications per account per day**
- at most **200 recipients per send**

Recipients are exactly the providers that `visible_to` admits at send time, so the current
eligibility rules apply. The advertiser never sees who was notified. Sponsored alerts are titled
«إعلان ممول» / "Sponsored", and dashboard sections carry the same badge. Impressions and clicks are
not recorded or invented.

**Real-estate promotions** (`ListingPromotion`):

- **Seller** requests a promotion (1–60 days, target provider types; one open promotion per
  listing) or ends one.
- **Admin** approves or rejects it; a rejection needs a reason.
- **Feed:** `/real-estate/promoted` shows the promotion only to **verified providers who opted in**
  and whose type is targeted, and only while the listing is publicly visible.

## 6. Professions

`Profession` now lists healthcare first, then health business, technology and business roles.
`PROFESSION_GROUPS` assigns each profession exactly one group, and `GET /jobs/professions` returns
the groups. The demo jobs that used `OTHER` now use the matching new values.

## 7. Refresh-token hardening: design review (not implemented)

**Today.** The refresh token is kept in `localStorage`, the access token in memory (ADR-061, CSP
mitigations).

**Proposed for production:**

- A `POST /auth/web/refresh` that reads an `HttpOnly; Secure; SameSite=Strict` cookie
  `racheeta_rt`, scoped `Path=/api/v1/auth/web/`.
- Login and refresh on that path set the cookie and return only the access token.
- Rotation and the blacklist stay as they are.
- CSRF: `SameSite=Strict`, a required `X-Requested-With` header, and an `Origin` check against the
  allowed host.
- Logout clears the cookie and blacklists the token.
- Mobile keeps the body-delivered token.

**Required tests before claiming the fix:**

- The cookie flags.
- No refresh token in any JSON response on the web path.
- A cross-origin POST is refused.
- Rotation and reuse detection.
- Logout.
- No regression on the mobile endpoints.

**Not implemented here** because it depends on the final domain layout (first-party cookie between
the web and API origins).

## 8. Deferred / not implemented

- External e-mail or push for marketing: always off in this demo.
- Card or online payments: never implemented, by design.
- Order delivery-zone pricing and taxes.
- Pagination UI on the merchant and quote pages (the API paginates; the pages show the first 20).
- An org-workspace view for property sellers.
- Enforcing `account_type` against the provider or business type when the profile is created later.
- The refresh-cookie migration (§7).
