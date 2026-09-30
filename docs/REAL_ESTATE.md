# Medical Real Estate (Phase 7)

Owners and agents advertise properties suited to medical use (clinics,
buildings, pharmacy or laboratory locations, land for medical investment) for
**sale or rent**. The catalogue is **public**: anyone can browse it and find a
property by transaction, type, place, suitable medical use, price and area.
Publication is decided by the seller's own action **and** by a backend gate;
what the public sees is decided by one visibility rule evaluated on every read.

There is no seller verification, no images, no advertising/payment and no
proximity search in this phase (see *Deferred*).

## Entities (`apps/real_estate`)

| Model | Owner | Notes |
| --- | --- | --- |
| `RealEstateSeller` | the `REAL_ESTATE_SELLER` account (one-to-one) | `seller_type` OWNER/AGENT, `display_name`, `about`, `phone`, `public_email`. **`account` is immutable** after creation (model guard; the API never accepts it). No verification lifecycle. |
| `PropertyListing` | the seller | `title`, `description`, `property_type`, `transaction_type`, `governorate` (required), `city` (optional), `district`, `latitude`/`longitude` (optional pair), `area_sqm`, `price` (null = price on request), `currency`, `facilities` (text), `contact_method`, `contact_phone`, `contact_email`, server-owned `publication_status`, `published_at`, and `expires_at`. `seller` is immutable. |
| `ListingSuitableUse` | the seller, through the services only | one row per (listing, use): structured and searchable. |

Every entity extends `BaseModel` (UUID id, timestamps). Migration:
`real_estate/0001_initial`.

### Controlled vocabularies (`types.py`)

- **Property type** — `CLINIC`, `APARTMENT_FOR_CLINIC`, `MEDICAL_BUILDING`,
  `PHARMACY_LOCATION`, `LABORATORY_LOCATION`, `MEDICAL_CENTER`,
  `HOSPITAL_BUILDING`, `COMMERCIAL_MEDICAL_PROPERTY`, `MEDICAL_INVESTMENT_LAND`
  (Master Plan §15).
- **Transaction** — `SALE`, `RENT`.
- **Suitable use** — `CLINIC`, `PHARMACY`, `LABORATORY`, `MEDICAL_CENTER`,
  `HOSPITAL`, `GENERAL_MEDICAL_USE`, `MEDICAL_INVESTMENT`. These codes are
  implementation defaults derived from the medical uses named in §15; they are
  code, not an administrator-managed taxonomy.
- **Contact method** — `PHONE`, `EMAIL`, `BOTH`.
- **Publication status** — `DRAFT`, `PUBLISHED`.
- **Seller type** — `OWNER`, `AGENT`.

Clients can never invent a value: the serializers, the services and (where a
rule can be expressed) the database all reject anything else. The web mirrors
the code lists and translates every code into Arabic and English.

### Database constraints and indexes

Check constraints: `price` null or ≥ 0; `area_sqm` null or > 0; latitude in
[-90, 90]; longitude in [-180, 180]; coordinates both null or both set;
`PUBLISHED` requires `area_sqm` and `expires_at`. Unique
`(listing, use)` for suitable uses; one seller per account. Indexes for the
public filters: `(seller, publication_status)`, `(publication_status,
expires_at)`, `(publication_status, transaction_type)`, `(publication_status,
property_type)`, `(governorate, city)`, and `use`. Coordinates are plain
decimals; there is no PostGIS.

## The seller role

`REAL_ESTATE_SELLER` already existed (`apps/accounts/roles.py`, capability
`real_estate.manage_own_listings`, self-registration). Phase 7 adds no role and
no authentication. Owner endpoints require that role
(`IsRealEstateSellerAccount`), and those needing a profile also require the
profile (`HasRealEstateSeller`); ownership always comes from
`request.user.real_estate_seller`, never from a client id. `GET /api/v1/me`
remains the identity source; the web guards are UX only.

## Public visibility — one rule

`PropertyListingQuerySet.publicly_visible()` is the single rule. The public
list and detail both start from it; every filter only narrows it. A listing is
visible **now** only when all hold:

1. `publication_status = PUBLISHED`;
2. `expires_at > now` (server time, at read time — see *Expiration*);
3. the seller's account is active;
4. the seller's account role is still exactly `REAL_ESTATE_SELLER`;
5. the governorate is active;
6. the city, when set, is active **and still belongs to the listing's governorate** (`city.governorate_id = listing.governorate_id`) — an administrator can move a city between governorates, so the relationship is read live, not assumed from when the listing was saved.

Everything is read from live database state, so a role change, a city moved to another governorate, an account
deactivation, a deactivated governorate or city, or the passing of the expiry
hides the listing on the next request without touching it; restoring the state
restores it. Anything not visible answers the ordinary **404** on detail — the
same body as an id that never existed — and never discloses the title, seller
name or contact data.

The owner sees derived, read-only state on their own rows (`is_public`,
`is_expired`), annotated in SQL by `with_public_state()` from the same rule, and
the owner's nested governorate and city also carry the **current** `is_active`
(and the city's present `governorate`) so the workspace can recognise an
inactive or moved reference. The public representation is unchanged; the public
geography endpoints stay active-only.

## The publication gate

`services.publication_problems()` is the one authoritative gate. It is used to
**publish** and to accept **every edit of a PUBLISHED listing**, evaluated on
the *resulting* state (an edit that would break a requirement is refused and
nothing is written). It also requires the seller to be eligible: an active
account whose role is still `REAL_ESTATE_SELLER`, read from the seller and
account **locked fresh in the transaction**, never from the request's snapshot
(`seller_not_eligible`, 403).

| Requirement | Field → typed code |
| --- | --- |
| non-empty title | `title` → `title_required` |
| valid property type, transaction, contact method | `invalid_choice` |
| governorate exists and is active | `governorate` → `geography_inactive` |
| city active; belongs to the governorate | `city` → `city_inactive`, `city_mismatch` |
| area present and > 0 | `area_sqm` → `area_required`, `area_invalid` |
| coordinates both-or-neither and in range | `latitude` → `coordinates_invalid` |
| at least one suitable use | `suitable_uses` → `suitable_use_required` |
| contact data for the method (PHONE / EMAIL / BOTH) | `contact_phone` → `contact_phone_required`; `contact_email` → `contact_email_required`, `contact_email_invalid` |
| expiry present and in the future | `expires_at` → `expiry_required`, `expiry_in_past` |
| price null or ≥ 0; supported currency | `price_invalid`, `currency_unsupported` |

Failures are a 400 validation error whose `codes` carry those typed values per
field, all at once. A **draft** may be incomplete (only title, types and
governorate are needed to save one); only the structural rules (valid values,
ranges, city/governorate agreement) apply to drafts.

Publication is server-controlled: the API never accepts `publication_status`,
`published_at`, `is_public`, `is_expired` or ownership fields
(`field_not_allowed`). `POST …/publish` sets `PUBLISHED` and stamps
`published_at` from server time; `POST …/unpublish` returns to `DRAFT` and is
always possible (even after role loss). Publishing a published listing or
unpublishing a draft is `invalid_transition`. There is no DELETE: history is
kept.

## Expiration

`expires_at` is required to publish and must be in the future. There is no
scheduler: expiry is compared with server time on every read, so an expired
row stays `PUBLISHED` in storage but is not public. Editing a published
listing re-runs the gate, so an expired listing can only be edited if the same
update sets a future date (or the owner unpublishes it first).

## Suitable uses

Stored as normalized rows, never a text blob or JSON list. A draft may have
none; publication needs at least one. The public API returns them in a fixed
order and `?suitable_use=` filters by an `EXISTS` on the rows. Replacing uses
happens only in the services, **after taking the listing's row lock**.

## Locking and races

**Every ordinary seller mutation** — profile update, draft creation, draft edit,
published edit and publish — re-checks the CURRENT seller state after taking
the lock: the account exists, is active and its role is exactly
`REAL_ESTATE_SELLER` (`seller_not_eligible`, 403), before anything is written.
The view resolves the seller with the same check, but only the service closes the
race. The one exception is **unpublish**, which only reduces exposure and is
always allowed at the service level.

Lock order: seller (with its account) → listing → suitable uses. Every
mutation re-reads and locks in that order and writes only the fields it owns
(`update_fields`), never a stale instance. Consequences, each proven by tests
with a real second database connection:

- publishing, profile updates, draft creation and draft edits with a seller role
  that changed after the view loaded it fail and leave the data unchanged;
- publishing in that situation leaves the listing `DRAFT` and out of the catalogue;
- use replacement and publication wait for the listing lock, and publication
  decides on the uses committed under that lock.

## Public API (`/api/v1/real-estate/…`)

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| GET | `listings` | anyone | paginated (`StandardPagination`, 20, `page_size` ≤ 100) |
| GET | `listings/{id}` | anyone | plain 404 unless publicly visible |

**Filters** (all optional, all backend-side; unknown values are a 400):
`transaction_type`, `property_type`, `governorate`, `city`, `suitable_use`,
`min_price`, `max_price`, `min_area`, `max_area` (a price on request matches no
price range), and `search` over title, description and district.
**Ordering** (`?ordering=`, allow-list only): `created_at`, `-created_at`
(default), `price`, `-price`, `area_sqm`, `-area_sqm`. Every ordering ends in
`id`, so pages are stable when the key ties; a null price/area sorts last.

The public listing carries: id, title, description, property type,
transaction, nested governorate/city, district, coordinates, area, price,
currency, suitable uses, facilities, contact method, **only the contact values
that method makes public** (the other is `null`), a seller summary (`id`,
`display_name`, `seller_type` — the profile id, never account identity),
`published_at`, `expires_at` and timestamps. It never carries the account
e-mail or id, roles or staff flags.

## Owner API

| Method | Path | Notes |
| --- | --- | --- |
| GET / POST / PATCH | `owner` | own seller profile; GET before onboarding is a 404; a second POST is `already_exists` (409); PATCH edits only `seller_type`, `display_name`, `about`, `phone`, `public_email` |
| GET | `owner/dashboard` | backend counts, below |
| GET / POST | `owner/listings` | own listings (paginated, newest first, `?publication_status=`); create a draft |
| GET / PATCH | `owner/listings/{id}` | foreign ids → 404; PATCH re-validates a published listing in full |
| POST | `owner/listings/{id}/publish` · `/unpublish` | the gate above |

The listing payload accepts only `title, description, property_type,
transaction_type, governorate, city, district, latitude, longitude, area_sqm,
price, currency, facilities, contact_method, contact_phone, contact_email,
expires_at, suitable_uses`. Ownership, lifecycle, derived state, targeting,
payment, advertising and image fields are refused with `field_not_allowed`.
Error codes: `already_exists` (409), `seller_not_eligible` (403), `not_found`
(404), `invalid_transition` (400), and the per-field codes above (400).

Audit events: `real_estate.seller.created`, `.seller.updated`,
`.listing.created`, `.listing.updated`, `.listing.published`,
`.listing.unpublished`.

### Dashboard (`owner/dashboard`)

Computed in SQL, never by the client: `listings_total`, `listings_draft`,
`listings_published` (stored status), `listings_visible` (passes the full public
rule right now), `listings_expired` (PUBLISHED with `expires_at <= now`),
`listings_sale`, `listings_rent`. No views, leads or revenue exist, so none are
reported.

## Django admin

Sellers, listings and suitable uses are **inspection-only** (no add, change or
delete): ownership cannot be transferred and publication cannot bypass the
services.

## Web

- `/real-estate` — the public catalogue: URL-backed filters and ordering sent
  to the backend, backend pagination, loading / empty / error states.
- `/real-estate/:id` — detail with only the contact values returned; a hidden
  listing shows one non-disclosing message.
- `/real-estate/owner` (`RequireRole REAL_ESTATE_SELLER`) — onboarding, the
  backend dashboard, the listing form (structured suitable-use checkboxes),
  paginated own listings with badges and expiry, publish/unpublish through
  `ApiActionButton`. **Publish is guidance only**: it is not offered when the
  loaded data already says the gate would refuse (the missing items are listed),
  and the backend's typed refusals are shown if it says no anyway.
- A listing that references a governorate or city an administrator has since
  deactivated keeps it as the selected current option, labelled "no longer
  available" and disabled once the user moves away; an untouched inactive
  reference is not resent when other fields are saved. The stored city stays
  visible **while the user is on the listing's stored governorate**, also when an
  administrator moved it to another governorate (so it is missing from that
  governorate's active list); it is never injected into another governorate's
  options and is only for recovery. Publish is not offered (the missing item is
  listed) when the loaded owner data shows an inactive governorate, an inactive
  city, or a city that no longer belongs to the governorate. This is guidance
  only: the backend gate stays authoritative and its typed refusals are shown.
  The public geography endpoints stay active-only.
- Header links (public; workspace for sellers), footer link and a live home
  card. Every label is available in Arabic and English.

## Deferred (by design)

- **Images / media uploads** — there is still no production object storage
  (ADR-044/046). No upload, URL or gallery placeholder exists.
- **Advertising, featured/boosted listings, campaigns, payments** — Phase 8.
  Publication is not billing-gated and never consults `apps.billing`.
- **Chat, notifications, analytics** — Phase 9+. Contact is the listing's own
  public contact method.
- **PostGIS / proximity search** — coordinates are stored only; added when
  radius search is genuinely required.
- Seller verification, listing deletion, map integration.
