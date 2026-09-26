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
| PROVIDER | accounts.view_self, accounts.edit_self, providers.search, providers.manage_own_profile, reservations.manage_received, offers.manage_own, jobs.manage_own |
| MEDICAL_COMPANY | accounts.view_self, accounts.edit_self, marketplace.manage_own_products, advertising.manage_own_campaigns |
| REAL_ESTATE_SELLER | accounts.view_self, accounts.edit_self, real_estate.manage_own_listings |
| ADMIN | accounts.view_self, accounts.edit_self, admin.access, admin.manage_accounts, admin.verify_providers, admin.moderate_content |

`is_staff` adds `admin.access`; `is_superuser` adds every ADMIN capability.

These codes are forward-looking labels for modules that do not exist yet. They
are not enforced anywhere until the module ships. Keep this table, the
`ROLE_CAPABILITIES` dict, and the module's permission classes in sync.

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
| `provider_type` change | provider while not VERIFIED; afterwards administrators only (Django admin) |

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
| `CanRecruit` | OWNER or RECRUITER (job writes, applicant transitions, interviews, invitations, messages); VIEWER is read-only. The employer workspace mirrors this: New Job and talent search are shown only to OWNER/RECRUITER, the job editor renders read-only for a VIEWER who reaches it by URL, and the applicants page shows a VIEWER the applicant data but no transition, interview, reason or messaging control (employer-side messaging is part of applicant review, so a VIEWER is not a party to the thread). An unknown or missing role gets no write control; on the talent detail page Save/Unsave and Invite appear only when the plan carries `talent.save_candidate` / `talent.invite`. UX only, the backend stays authoritative. |
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
