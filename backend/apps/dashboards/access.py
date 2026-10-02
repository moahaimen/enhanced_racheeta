"""Who may open which dashboard. ONE source of truth used by both the permission classes and the
`GET /dashboards/` index, so the index can never advertise a dashboard its endpoint refuses (or
the reverse). Every answer is read from current database state; nothing comes from the client."""

from __future__ import annotations

from apps.accounts.roles import AccountRole
from apps.jobs.models import EmployerMembership
from apps.jobs.services import membership_for
from apps.marketplace.models import MedicalCompany
from apps.providers.models import ProviderProfile
from apps.real_estate.models import RealEstateSeller

PATIENT = "patient"
DOCTOR = "doctor"
FACILITY = "facility"
MEDICAL_COMPANY = "medical_company"
REAL_ESTATE_OWNER = "real_estate_owner"
RECRUITER = "recruiter"
ADMIN = "admin"

ALL = (PATIENT, DOCTOR, FACILITY, MEDICAL_COMPANY, REAL_ESTATE_OWNER, RECRUITER, ADMIN)


def is_patient(account) -> bool:
    return bool(account.is_authenticated and account.role == AccountRole.PATIENT)


def provider_profile_for(account) -> ProviderProfile | None:
    """The caller's own profile, only for an authenticated PROVIDER account."""
    if not (account.is_authenticated and account.role == AccountRole.PROVIDER):
        return None
    return ProviderProfile.objects.filter(account=account).first()


def practitioner_profile_for(account) -> ProviderProfile | None:
    profile = provider_profile_for(account)
    return profile if profile is not None and profile.is_practitioner else None


def facility_profile_for(account) -> ProviderProfile | None:
    profile = provider_profile_for(account)
    return profile if profile is not None and profile.is_facility else None


def company_for(account) -> MedicalCompany | None:
    if not (account.is_authenticated and account.role == AccountRole.MEDICAL_COMPANY):
        return None
    return MedicalCompany.objects.filter(account=account).first()


def seller_exists(account) -> bool:
    return bool(
        account.is_authenticated
        and account.role == AccountRole.REAL_ESTATE_SELLER
        and RealEstateSeller.objects.filter(account=account).exists()
    )


def recruiter_membership_for(account) -> EmployerMembership | None:
    return membership_for(account)


def is_staff(account) -> bool:
    return bool(account.is_authenticated and account.is_staff)


def available_dashboards(account) -> list[str]:
    """Dashboard keys the account can open right now, primary role first."""
    keys: list[str] = []
    if is_patient(account):
        keys.append(PATIENT)
    profile = provider_profile_for(account)
    if profile is not None:
        keys.append(FACILITY if profile.is_facility else DOCTOR)
    if company_for(account) is not None:
        keys.append(MEDICAL_COMPANY)
    if seller_exists(account):
        keys.append(REAL_ESTATE_OWNER)
    if recruiter_membership_for(account) is not None:
        keys.append(RECRUITER)
    if is_staff(account):
        keys.append(ADMIN)
    return keys
