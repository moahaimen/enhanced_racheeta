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

## 9. Module-based dashboards (all account types)

**Endpoint and composer.** `GET /api/v1/workspaces/dashboard?ws=<workspace id>` is composed by
`apps/workspaces/dashboard.py`:

- The workspace id is checked against `build_workspaces(account)` as it stands *now*. A forged,
  foreign, revoked or suspended id answers **404**.
- Modules are chosen from the workspace kind, its subtype and the caller's **current** capability
  in that organization.
- Every figure is a real query over the caller's own rows, or the organization's rows for a
  member. No impressions, clicks or revenue are invented.
- Lists contain business facts only: no patient contact data and no requester e-mail.
- Responses are `Cache-Control: private, no-store`.

**Web page.** `/dashboard` is one React page (`WorkspaceDashboardPage`) that renders exactly the
modules it receives. Two of them are feeds that load from their own eligibility-checked endpoints:
`sponsored` («إعلان ممول») and `promoted`. The previous tabbed statistics remain at
`/dashboard/summary`.

### Compositions

| Workspace | Modules |
|---|---|
| Doctor | profile · medical services · appointments · offers · reviews · products for the specialty · my quotes · sponsored · promoted* |
| Nurse | profile · nursing services · appointments · offers · professional connections · relevant suppliers · my quotes · sponsored · promoted* |
| Therapist | profile · therapy & rehabilitation services · sessions · offers · reviews · rehabilitation products · my quotes · sponsored · promoted* |
| Hospital | profile · departments · practitioners · appointments · offers · team · recruitment · equipment suppliers · my quotes · sponsored · promoted* |
| Medical center | profile · clinics · practitioners · appointments · offers · team · recruitment · suppliers · my quotes · sponsored · promoted* |
| Pharmacy | pharmacy profile · offers · team · recruitment · eligible product categories · suppliers · my quotes · sponsored · promoted* |
| Laboratory | profile · lab tests · appointments · offers · team · recruitment (staffing) · lab equipment & supplies · my quotes · sponsored · promoted* |
| Beauty center | profile · permitted aesthetic services · appointments · promotions & offers · team · recruitment · equipment suppliers · sponsored · promoted* |
| Pharmaceutical company / distributor | product management (incl. restricted B2B count) · quote requests · campaigns · team · recruitment |
| Scientific office | product management · quote requests · campaigns · team · recruitment |
| Equipment supplier / medical supplies office / assistive-device store (retail) | product management · inventory & stock (low / out) · store orders · quote requests · campaigns · team · recruitment |
| Property owner / agent | listings & publication · promotions |
| Employer / recruiter | jobs · applicants · interviews · invitations · subscription & seats |
| Job seeker | professional profile · applications · interviews · invitations · jobs for you |
| Patient / customer | my store orders · reservations · assistive-device store · my reviews |
| Administrator | verification queues · review & moderation · campaigns · subscriptions · users · audit |

\* `promoted` appears only for verified providers who opted in to real-estate promotions.
`sponsored` appears only for verified providers whose display preference is on.

Every dashboard also ends with **notifications & messages** and **account settings**.

**Organization members** get only what their capability allows:

| Role | Gets | Never gets |
|---|---|---|
| VIEWER, STAFF | Read modules: services, practitioners, reservations, catalogue, inventory, orders, quotes | Owner tools: campaigns (MANAGER+), team (MANAGER+), recruitment, sponsored, promoted, the B2B catalogue and buyer quotes |
| MANAGER | Team and campaigns, in addition | Recruitment and the owner-only feeds |

### Switching workspaces

`GET /api/v1/workspaces` marks one entry `is_default`. A personal account with an active
organization membership (staff) lands in that organization, not in the patient dashboard.

The header switcher lists only server-returned workspaces and changes `?ws=`. The dashboard body
is keyed by account and workspace, so each switch remounts it:

- previous data is dropped;
- the in-flight request is aborted;
- a late response can never render.

Web tests cover workspace switching, logout-and-login as another account, and forged ids.

### Reservations

Online booking is switched **off by default** (reversible sunset; details in
`docs/RESERVATIONS.md` "Booking sunset switch"). One server setting controls it:
`RACHEETA["RESERVATIONS_ENABLED"]`, read from the env variable `RESERVATIONS_ENABLED`
(default `false`). The web app reads it from `GET /api/v1/platform/features`.

To see the old booking behaviour locally, add `RESERVATIONS_ENABLED=true` to
`local-demo/.env.demo` and restart `scripts/local_demo.sh serve`; remove the line (or set it to
`false`) to switch booking off again. No migration, no data change either way.

### Migrations

No new migrations in this step. The capabilities `company.products.view`,
`company.campaigns.view` and `org.owner_tools` are code-only, and the dashboard reads existing
tables. The earlier additive migrations of this branch are unchanged:

- `accounts/0003`
- `marketplace/0002`
- `jobs/0002`
- `notifications/0004`
- `real_estate/0002`
- `preferences/0001`
- `commerce/0001`
- `workspaces/0001`

All of them add columns with defaults, new tables, or choice-list changes. None drops or rewrites
existing data, so they are backward-compatible with existing rows.

## 10. Multi-vendor marketplace with the 20% commission (simulated money)

Design and rules: `docs/MARKETPLACE_COMMERCE.md`. Feature status: `docs/local-commerce-implementation-matrix.md`.

Demo accounts are listed in `local-demo/DEMO_ACCOUNTS.md`, which is git-ignored and holds no passwords.

The seed (`scripts/local_demo.sh seed`, which includes `--with-admin`) creates the marketplace scenarios:
- every order state;
- the exact examples (100,000 → 20,000 / 80,000 and 90,000 → 18,000 / 72,000);
- a Racheeta-funded coupon, a multi-vendor checkout and a partial return;
- an open return, an open dispute, a paid-then-cancelled refund and a quote → order;
- one paid and one draft payout.

Browser walkthrough:
1. **Buyer**: put two stores' items in the cart, apply a coupon and place the order.
2. **Seller**: accept and ship.
3. **Buyer**: confirm receipt.
4. **Finance** (`local-finance`, /admin-finance): verify the simulated payment and complete the order (the commission is recorded).
5. **Refund**: the buyer requests a return, the seller approves and receives it, and finance refunds it.
6. **Payout**: finance prepares the payout and marks it paid. The reconciliation tab then shows every check PASS.

Notes:
- A staff account without the finance permission (`local-support`) is refused.
- The ledger is append-only. Only `scripts/local_demo.sh clear` can remove demo ledger rows, inside its guarded transaction.

