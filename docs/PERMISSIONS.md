# Permissions

## Model

- **Primary role** — `Account.role`, one of `PATIENT`, `PROVIDER`,
  `MEDICAL_COMPANY`, `REAL_ESTATE_SELLER`, `ADMIN`. Set at registration
  (never `ADMIN`) or by an administrator.
- **Staff flags** — `is_staff` (Django admin access), `is_superuser`. Only
  `create_superuser` or an existing administrator can set them.
- **Capability codes** — strings like `reservations.create_own`, derived from
  role + flags by `apps.accounts.roles.capabilities_for`. Returned in
  `GET /api/v1/me` as `permissions`. They let clients show/hide UI; the backend
  re-checks every action regardless.
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

## Adding a role

1. Add to `AccountRole` and `ROLE_CAPABILITIES` in `apps/accounts/roles.py`.
2. Decide whether it is self-registrable (`settings.RACHEETA["SELF_REGISTRATION_ROLES"]`).
3. Migration (choices change → `makemigrations`).
4. Update this file and `docs/api/openapi.yaml` (`make openapi`).
