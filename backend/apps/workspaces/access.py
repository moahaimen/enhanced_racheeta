"""THE organization access decision. Always reads current database state (never the request's
cached objects): an ended membership, a deactivated account or a suspended organization stops
access on the very next request.
"""

from __future__ import annotations

from uuid import UUID

from apps.accounts.roles import AccountRole
from apps.marketplace.models import MedicalCompany
from apps.providers.models import ProviderProfile
from apps.providers.types import FACILITY_TYPES

from .models import OrganizationMember
from .types import MemberStatus, OrgRole, role_has


def _uuid(value):
    """A malformed id is simply "no such organization" (never a server error)."""
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError):
        return None


def facility_role(account, facility_id) -> str | None:
    """The account's role in this facility, or None (no access)."""
    facility_id = _uuid(facility_id)
    if facility_id is None or not (account and account.is_authenticated and account.is_active):
        return None
    facility = (
        ProviderProfile.objects.filter(
            pk=facility_id,
            provider_type__in=FACILITY_TYPES,
            account__is_active=True,
            account__role=AccountRole.PROVIDER,
        )
        .only("pk", "account_id")
        .first()
    )
    if facility is None:
        return None
    if facility.account_id == account.pk:
        return OrgRole.OWNER
    member = OrganizationMember.objects.filter(
        account=account, facility_id=facility.pk, status=MemberStatus.ACTIVE
    ).first()
    return member.role if member else None


def company_role(account, company_id) -> str | None:
    company_id = _uuid(company_id)
    if company_id is None or not (account and account.is_authenticated and account.is_active):
        return None
    company = (
        MedicalCompany.objects.filter(
            pk=company_id, account__is_active=True, account__role=AccountRole.MEDICAL_COMPANY
        )
        .only("pk", "account_id")
        .first()
    )
    if company is None:
        return None
    if company.account_id == account.pk:
        return OrgRole.OWNER
    member = OrganizationMember.objects.filter(
        account=account, company_id=company.pk, status=MemberStatus.ACTIVE
    ).first()
    return member.role if member else None


def can_facility(account, facility_id, capability: str) -> bool:
    return role_has(facility_role(account, facility_id), capability)


def can_company(account, company_id, capability: str) -> bool:
    return role_has(company_role(account, company_id), capability)


def own_company_id(account):
    """The business the account owns, re-read from the database (None if none)."""
    return (
        MedicalCompany.objects.filter(account_id=getattr(account, "pk", None))
        .values_list("pk", flat=True)
        .first()
    )
