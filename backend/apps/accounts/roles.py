"""Role and capability registry.

One `Account` has exactly one primary `role`. Finer-grained identity
(doctor vs nurse, hospital vs pharmacy, ...) lives in profile models under
the account (Phase 2). Capability codes returned by `/api/v1/me` are
informational for clients — the backend re-checks everything.

Rules:
* ADMIN is never assignable by a client. Only `create_superuser` or an
  administrator action can grant it.
* Add a role here, in `Account.Role`, and in docs/PERMISSIONS.md together.
"""

from django.db import models


class AccountRole(models.TextChoices):
    PATIENT = "PATIENT", "Patient"
    PROVIDER = "PROVIDER", "Healthcare provider"
    MEDICAL_COMPANY = "MEDICAL_COMPANY", "Medical company / supplier"
    REAL_ESTATE_SELLER = "REAL_ESTATE_SELLER", "Medical real-estate owner or agent"
    ADMIN = "ADMIN", "Racheeta administrator"


# Roles a client may pick for itself (registration, Firebase first sign-in).
# Mirrors settings.RACHEETA["SELF_REGISTRATION_ROLES"]; ADMIN is never here.
SELF_REGISTRATION_ROLE_CHOICES = [
    (r, r.label)
    for r in (
        AccountRole.PATIENT,
        AccountRole.PROVIDER,
        AccountRole.MEDICAL_COMPANY,
        AccountRole.REAL_ESTATE_SELLER,
    )
]


class AccountType(models.TextChoices):
    """The understandable "who are you" choice of the onboarding screen (finer than `role`).

    It maps to exactly one primary role (ACCOUNT_TYPE_ROLE) and preselects the profile the
    person completes next (provider type, company business type, seller kind). Job seeker is not
    a type: any account may add a job-seeker profile. ADMIN is never a type.
    """

    PATIENT = "PATIENT", "Patient"
    DOCTOR = "DOCTOR", "Doctor"
    NURSE = "NURSE", "Nurse"
    THERAPIST = "THERAPIST", "Therapist"
    HOSPITAL = "HOSPITAL", "Hospital"
    MEDICAL_CENTER = "MEDICAL_CENTER", "Medical center / clinic"
    PHARMACY = "PHARMACY", "Pharmacy"
    LABORATORY = "LABORATORY", "Laboratory"
    BEAUTY_CENTER = "BEAUTY_CENTER", "Beauty center"
    PHARMACEUTICAL_COMPANY = "PHARMACEUTICAL_COMPANY", "Pharmaceutical company"
    SCIENTIFIC_OFFICE = "SCIENTIFIC_OFFICE", "Scientific office"
    MEDICAL_SUPPLIES_OFFICE = "MEDICAL_SUPPLIES_OFFICE", "Medical supplies office"
    EQUIPMENT_SUPPLIER = "EQUIPMENT_SUPPLIER", "Medical equipment supplier"
    ASSISTIVE_DEVICE_STORE = "ASSISTIVE_DEVICE_STORE", "Assistive devices store"
    PHARMA_DISTRIBUTOR = "PHARMA_DISTRIBUTOR", "Pharmaceutical distributor"
    PROPERTY_OWNER = "PROPERTY_OWNER", "Medical property owner"
    PROPERTY_AGENT = "PROPERTY_AGENT", "Medical property agent / manager"


PROVIDER_ACCOUNT_TYPES = frozenset(
    {
        AccountType.DOCTOR,
        AccountType.NURSE,
        AccountType.THERAPIST,
        AccountType.HOSPITAL,
        AccountType.MEDICAL_CENTER,
        AccountType.PHARMACY,
        AccountType.LABORATORY,
        AccountType.BEAUTY_CENTER,
    }
)
BUSINESS_ACCOUNT_TYPES = frozenset(
    {
        AccountType.PHARMACEUTICAL_COMPANY,
        AccountType.SCIENTIFIC_OFFICE,
        AccountType.MEDICAL_SUPPLIES_OFFICE,
        AccountType.EQUIPMENT_SUPPLIER,
        AccountType.ASSISTIVE_DEVICE_STORE,
        AccountType.PHARMA_DISTRIBUTOR,
    }
)
PROPERTY_ACCOUNT_TYPES = frozenset({AccountType.PROPERTY_OWNER, AccountType.PROPERTY_AGENT})

ACCOUNT_TYPE_ROLE: dict[str, str] = {
    AccountType.PATIENT: AccountRole.PATIENT,
    **{t: AccountRole.PROVIDER for t in PROVIDER_ACCOUNT_TYPES},
    **{t: AccountRole.MEDICAL_COMPANY for t in BUSINESS_ACCOUNT_TYPES},
    **{t: AccountRole.REAL_ESTATE_SELLER for t in PROPERTY_ACCOUNT_TYPES},
}
assert set(ACCOUNT_TYPE_ROLE) == set(AccountType.values)  # noqa: S101 - every type has a role


# Capability codes per role. Format: "<module>.<action>".
ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    AccountRole.PATIENT: frozenset(
        {
            "accounts.view_self",
            "accounts.edit_self",
            "providers.search",
            "reservations.create_own",
            "reviews.create_own",
        }
    ),
    AccountRole.PROVIDER: frozenset(
        {
            "accounts.view_self",
            "accounts.edit_self",
            "providers.search",
            "providers.manage_own_profile",
            "reservations.manage_received",
            "offers.manage_own",
            "jobs.manage_own",
            "marketplace.view_targeted_products",
        }
    ),
    AccountRole.MEDICAL_COMPANY: frozenset(
        {
            "accounts.view_self",
            "accounts.edit_self",
            "marketplace.manage_own_products",
            "advertising.manage_own_campaigns",
        }
    ),
    AccountRole.REAL_ESTATE_SELLER: frozenset(
        {
            "accounts.view_self",
            "accounts.edit_self",
            "real_estate.manage_own_listings",
        }
    ),
    AccountRole.ADMIN: frozenset(
        {
            "accounts.view_self",
            "accounts.edit_self",
            "admin.access",
            "admin.manage_accounts",
            "admin.verify_providers",
            "admin.moderate_content",
        }
    ),
}

# Fields a client must never be able to set through any API.
CLIENT_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "is_staff",
        "is_superuser",
        "is_active",
        "permissions",
        "groups",
        "user_permissions",
        "email_verified",
        "email_verified_at",
        "firebase_uid",
        "last_login",
    }
)


def capabilities_for(account) -> list[str]:
    """Sorted capability codes for an account (role + staff flags)."""
    codes = set(ROLE_CAPABILITIES.get(account.role, frozenset()))
    if account.is_staff:
        codes.add("admin.access")
    if account.is_superuser:
        codes.update(ROLE_CAPABILITIES[AccountRole.ADMIN])
    return sorted(codes)
