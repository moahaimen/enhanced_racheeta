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

## Web route guards

`web/src/app/guards.tsx`: `RequireAuth` wraps protected routes, `PublicOnly`
wraps login/register. Pages contain no authentication checks. Guards improve
UX only; a protected page's data calls still fail with 401 without a valid
token.

## Adding a role

1. Add to `AccountRole` and `ROLE_CAPABILITIES` in `apps/accounts/roles.py`.
2. Decide whether it is self-registrable (`SELF_REGISTRATION_ROLE_CHOICES`
   and `settings.RACHEETA["SELF_REGISTRATION_ROLES"]`; web `auth/roles.ts`
   and `roles.*` translations).
3. Migration (choices change → `makemigrations`).
4. Update this file and `docs/api/openapi.yaml` (`make openapi`).
