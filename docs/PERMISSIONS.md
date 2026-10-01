# Permissions

## Model

- **Primary role** — `Account.role`, one of `PATIENT`, `PROVIDER`,
  `MEDICAL_COMPANY`, `REAL_ESTATE_SELLER`, `ADMIN`. Set at registration or
  first Firebase sign-in (never `ADMIN`) or by an administrator.
- **Staff flags** — `is_staff` (Django admin access), `is_superuser`. Only
  `create_superuser` or an existing administrator can set them.
- **Capability codes** — strings like `reservations.create_own`, derived from
  role + flags by `apps.accounts.roles.capabilities_for`. Returned in
  `GET /api/v1/me` as `permissions`. They let clients show/hide UI; the backend
  re-checks every action regardless. The web profile page renders them with
  an explicit "informational" label.
- **Verification state** — `email_verified_at`. No feature is gated on it
  yet. When a rule such as "providers must verify their email before
  publishing" is introduced, document it here and enforce it with a
  permission class.
- **Object ownership** — checked in each module's views/permissions (e.g. a
  provider may edit only its own offers). **(planned per module)**

Django's `auth.Permission` / `Group` tables are used only by the admin site.

## Capabilities by role (today)

| Role | Capabilities |
| --- | --- |
| PATIENT | accounts.view_self, accounts.edit_self, providers.search, reservations.create_own, reviews.create_own |
| PROVIDER | accounts.view_self, accounts.edit_self, providers.search, providers.manage_own_profile, reservations.manage_received, offers.manage_own, jobs.manage_own, marketplace.view_targeted_products |
| MEDICAL_COMPANY | accounts.view_self, accounts.edit_self, marketplace.manage_own_products, advertising.manage_own_campaigns |
| REAL_ESTATE_SELLER | accounts.view_self, accounts.edit_self, real_estate.manage_own_listings |
| ADMIN | accounts.view_self, accounts.edit_self, admin.access, admin.manage_accounts, admin.verify_providers, admin.moderate_content |

`is_staff` adds `admin.access`; `is_superuser` adds every ADMIN capability.

Codes for modules that do not exist yet are forward-looking labels, enforced
only once the module ships. `marketplace.manage_own_products` and
`marketplace.view_targeted_products` are enforced since Phase 6, and
`real_estate.manage_own_listings` since Phase 7, and `advertising.manage_own_campaigns` since Phase 8 (see below).
Keep this table, the `ROLE_CAPABILITIES` dict, and the module's permission
classes in sync.

## Self-registration roles

`apps.accounts.roles.SELF_REGISTRATION_ROLE_CHOICES` is the single list used
by registration, the Firebase exchange, and the OpenAPI enum
`SelfRegistrationRoleEnum`. A test asserts it matches
`settings.RACHEETA["SELF_REGISTRATION_ROLES"]`. The web app mirrors it in
`web/src/auth/roles.ts`; the backend remains authoritative.

## Enforcing in views

```python
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminAccount, has_role
from apps.accounts.roles import AccountRole

class OfferViewSet(...):
    permission_classes = [IsAuthenticated, has_role(AccountRole.PROVIDER)]
```

Default for every endpoint is `IsAuthenticated` (`REST_FRAMEWORK` settings);
public endpoints opt out explicitly with `AllowAny`.

## Marketplace permissions (`apps/marketplace/permissions.py`, Phase 6)

| Class | Grants |
| --- | --- |
| `IsMedicalCompanyAccount` | `role == MEDICAL_COMPANY` (`marketplace.manage_own_products`) — may create its company profile |
| `HasMedicalCompany` | company account with a profile — own products, verification request, dashboard; ownership comes from `request.user.medical_company`, never a client id |
| `CanBrowseMarketplace` | early answer only: `current_verified_provider(account)` — an active PROVIDER whose profile, re-read from the database, is VERIFIED (`marketplace.view_targeted_products`); `is_visible` is not required. The catalogue views re-read it when building the queryset, and `ProductQuerySet.targeted_for` re-checks verification, type and specialties inside the SQL statement; those inputs are frozen while PENDING or VERIFIED (ADR-045) |
| `IsAdminAccount` | company verification decisions and the company list |

Verified identity (ADR-045): a company's name, governorate, city, address and website, and a provider's type and specialties, are frozen for the owner while verification is PENDING or VERIFIED (`identity_locked`, decided on the locked row that the administrator's decision also locks). Owner payloads expose `identity_locked` so the web disables those fields. Administrators can grant VERIFIED only to a PENDING company or provider (`invalid_transition` otherwise), so the approved identity is always the one frozen by the review request.

Web mirrors (UX only): `/marketplace` and its detail sit behind `RequireRole(['PROVIDER'])`, `/company` behind `RequireRole(['MEDICAL_COMPANY'])`; the header shows the matching link per role and the company workspace hides Publish while `can_publish` is false and, for a published product, disables moving it to a category not open for publication. Publisher eligibility itself is backend state: VERIFIED, active account, role still `MEDICAL_COMPANY` (`MedicalCompany.can_publish` / `publishing()`, `Product.objects.exposable()` / `targeted_for()`, the activation gate and the dashboard all require it).

## Real-estate permissions (`apps/real_estate/permissions.py`, Phase 7)

| Class | Grants |
| --- | --- |
| `IsRealEstateSellerAccount` | `role == REAL_ESTATE_SELLER` (`real_estate.manage_own_listings`) — may read/create its seller profile |
| `HasRealEstateSeller` | seller account with a profile — dashboard and listing management; ownership comes from `request.user.real_estate_seller`, never a client id; a foreign listing id is a 404 |
| `AllowAny` | the public catalogue (list and detail), which only ever reads `publicly_visible()` |

The permission check is an early answer only: every mutation re-reads and locks the seller **and its account** in its transaction and requires an active account whose role is still `REAL_ESTATE_SELLER` to publish or to edit a published listing (`seller_not_eligible`); unpublishing is always allowed. A seller profile's `account` and a listing's `seller` are immutable. Django admin is inspection-only. Web mirror (UX only): `/real-estate/owner` sits behind `RequireRole(['REAL_ESTATE_SELLER'])`, and the workspace offers Publish only when the loaded data says the gate can succeed.

## Advertising permissions (`apps/advertising`, Phase 8)

| Class | Grants |
| --- | --- |
| `marketplace.HasMedicalCompany` | `role == MEDICAL_COMPANY` with a company profile (`advertising.manage_own_campaigns`): own campaigns, quote, submit, cancel, dashboard; ownership comes from `request.user.medical_company`, never a client id; a foreign campaign id is a 404 |
| `marketplace.CanBrowseMarketplace` | early answer for `advertising/marketplace`; the view re-reads the verified provider (`current_verified_provider`) and `visible_to()` re-checks it in SQL |
| `IsAdminAccount` (staff flag) | list/detail and the payment decisions; anonymous 401, non-staff 403 (a company can never verify or reject its own payment) |

Drafts need an active MEDICAL_COMPANY account; **submission and payment verification** need the current marketplace publisher eligibility (VERIFIED company, active account, role `MEDICAL_COMPANY`) read from the locked company, never the request's snapshot; cancelling is always allowed. Money, status, ownership and verification fields are never client input (`field_not_allowed`). Django admin: only `AdvertisingRate` is editable. Web mirror (UX only): `/company/advertising` behind `RequireRole(['MEDICAL_COMPANY'])`.

## Provider permissions (`apps/providers/permissions.py`)

| Class | Grants |
| --- | --- |
| `AllowAny` (public views) | discovery list/detail, geography, specialties |
| `IsProviderAccount` | authenticated account with `role == PROVIDER` — may create its profile |
| `HasProviderProfile` | provider account that completed onboarding — services, memberships, verification request |
| `IsAdminAccount` (`apps/accounts`) | verification decisions |

Ownership never comes from a client id: every self-management view resolves
`request.user.provider_profile` and scopes querysets to it, so a foreign
service or membership id is a 404. Public provider ids accept no writes.

The same rule governs linking an organisation to a facility profile
(`Employer.provider_profile`): `EmployerWriteSerializer.validate_provider_profile`
accepts only a profile owned by the caller, of FACILITY kind, not already linked
to another organisation. The employer form offers the caller's own profile from
`GET /providers/me` (404/403 simply means "nothing to choose") — it never lists
global provider identities — and the backend stays authoritative.

Verification state machine:

| Transition | Who |
| --- | --- |
| UNVERIFIED / REJECTED → PENDING | the provider (`/providers/me/verification/request`) |
| any → VERIFIED / REJECTED / SUSPENDED / UNVERIFIED | administrators only |
| `provider_type` / `specialties` change | the provider, only while not PENDING or VERIFIED (ADR-045); read-only for staff on the Django admin change form, as are `verification_status` and `verification_note` (verification moves only through the guarded admin actions / `services.set_verification`) |
| `account` (profile owner) | set once at creation; never changed afterwards (read-only on the admin change form, never written by admin or owner saves) |

Membership state machine:

| Transition | Who |
| --- | --- |
| create (PENDING) | a practitioner towards a discoverable facility, or a facility towards a discoverable practitioner |
| PENDING → ACTIVE | the side that did **not** initiate |
| PENDING → REJECTED | either side (initiator = withdraw) |
| ACTIVE → ENDED | either side |
| third parties | 404 on every action |

Provider role is assigned at registration (or first Firebase sign-in) and is
not client-changeable afterwards; a role change is an administrator action.

## Recruitment permissions (`apps/jobs/permissions.py`)

| Class | Rule |
| --- | --- |
| `IsEmployerMember` | caller has an ACTIVE `EmployerMembership`; sets `request.employer`/`request.membership`. Used by every `/jobs/employer/*` and `/talent/*` route. |
| `IsEmployerOwner` | membership role is OWNER (organisation edits, verification request, members, plan requests). Even the owner cannot change the verified identity fields (`name`, `organization_type`, `governorate`, `provider_profile`, `is_recruitment_agency`) once the organisation is PENDING or VERIFIED — the write serializer rejects them with `identity_locked`; only an administrator can. |
| `CanRecruit` | OWNER or RECRUITER (job writes, applicant transitions, interviews, invitations, messages); VIEWER is read-only. The permission class is a pre-check: every write service, and every candidate-data read (talent search, detail, saved candidates, sent invitations), re-reads the actor's membership, the organisation's recruiting state and the required entitlement under lock and refuses with the typed error if any was revoked meanwhile; reads build their response before releasing the locks. The employer workspace mirrors this: New Job and talent search are shown only to OWNER/RECRUITER, the job editor renders read-only for a VIEWER who reaches it by URL, and the applicants page shows a VIEWER the applicant data but no transition, interview, reason or messaging control (employer-side messaging is part of applicant review, so a VIEWER is not a party to the thread). An unknown or missing role gets no write control; on the talent detail page Save/Unsave and Invite appear only when the plan carries `talent.save_candidate` / `talent.invite`, on the workspace the Talent action needs `talent.search` and each Applicants link a recruiting organisation with `jobs.application_review` (a read gate, so VIEWER sees it; hidden while the billing summary loads), in the job editor Feature needs `jobs.featured`, Submit `jobs.post`, and the Applicants link a recruiting organisation with `jobs.application_review` (a read gate, so VIEWER sees it too), while Unfeature stays available for an already-featured job; on the applicants page actions need `jobs.application_review` and the message composer also `recruitment.messaging` (the history stays readable); on the talent detail Invite also needs the server's `can_invite`. UX only, the backend stays authoritative. |
| `IsAdminAccount` (accounts) | `is_staff` for every `/admin/*` route. |

Talent reads (`GET /talent`, `/talent/{id}`, `/talent/saved`, `/talent/invitations`)
require a verified, active organisation plus the matching capability
(`talent.search`, `talent.save_candidate`, `talent.invite`), enforced by
`_require_talent_access` in `apps/jobs/views.py`.

Employer-side applicant endpoints additionally require that the organisation
is still allowed to recruit (`organization_not_verified` otherwise) and the
plan capability `jobs.application_review`, through one shared gate (`_require_application_review`
in `apps/jobs/views.py`): list, detail, transition, interview request and the
employer side of message threads. The typed `entitlement_required` error (403)
is returned even for a known application id.

Job seekers act only on their own profile/applications (`request.user`);
message threads accept the candidate of the application or an active member of
the employer, nobody else (404 for third parties). Commercial capability is a
separate axis enforced by the billing service, not by permission classes.

## Web route guards

`web/src/app/guards.tsx`: `RequireAuth` wraps protected routes, `PublicOnly`
wraps login/register, `RequireRole` wraps role-specific pages (`/provider/profile`), `RequireStaff` wraps `/admin-console` (`account.is_staff`). Pages contain no authentication checks. Guards improve
UX only; a protected page's data calls still fail with 401 without a valid
token.

## Adding a role

1. Add to `AccountRole` and `ROLE_CAPABILITIES` in `apps/accounts/roles.py`.
2. Decide whether it is self-registrable (`SELF_REGISTRATION_ROLE_CHOICES`
   and `settings.RACHEETA["SELF_REGISTRATION_ROLES"]`; web `auth/roles.ts`
   and `roles.*` translations).
3. Migration (choices change → `makemigrations`).
4. Update this file and `docs/api/openapi.yaml` (`make openapi`).
