"""Marketplace permissions. Ownership never comes from client ids: company
views resolve `request.user.medical_company`, provider views resolve
`request.user.provider_profile`, and the backend re-checks everything."""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import AccountRole
from apps.marketplace.models import MedicalCompany, is_store_owner_account, seller_workspace_q
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus


class IsMedicalCompanyAccount(BasePermission):
    """An account that may own a store workspace (capability `marketplace.manage_own_products`):
    a MEDICAL_COMPANY account, or a PROVIDER whose own profile is a pharmacy. A pharmacy keeps its
    healthcare-provider role; its store is linked to its facility (see seller_workspace_q)."""

    message = "Only business and pharmacy accounts can do this."

    def has_permission(self, request, view) -> bool:
        return is_store_owner_account(request.user)


class HasMedicalCompany(IsMedicalCompanyAccount):
    """Store-owner account that has completed onboarding (its store row exists)."""

    message = "Create your company profile first."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return MedicalCompany.objects.filter(seller_workspace_q(), account=request.user).exists()


BROWSE_DENIED = "A verified provider profile is required to browse the marketplace."


def current_verified_provider(account):
    """THE authoritative browsing check (capability
    `marketplace.view_targeted_products`): re-reads the provider profile from
    the database — never a cached `account.provider_profile` — and returns it
    only while the account is an active PROVIDER whose profile is VERIFIED.
    Public visibility (`is_visible`) is NOT required: hiding a provider from
    patient search does not remove its B2B access."""
    if not (account and account.is_authenticated and account.role == AccountRole.PROVIDER):
        return None
    return (
        ProviderProfile.objects.filter(
            account_id=account.pk,
            account__is_active=True,
            verification_status=VerificationStatus.VERIFIED,
        )
        .prefetch_related("specialties")
        .first()
    )


class CanBrowseMarketplace(BasePermission):
    """Early rejection only (UX); the catalogue views re-read the provider
    with `current_verified_provider` when they build the queryset, and the
    targeting queryset re-checks it inside the SQL statement."""

    message = BROWSE_DENIED

    def has_permission(self, request, view) -> bool:
        return current_verified_provider(request.user) is not None
