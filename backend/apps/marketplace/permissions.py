"""Marketplace permissions. Ownership never comes from client ids: company
views resolve `request.user.medical_company`, provider views resolve
`request.user.provider_profile`, and the backend re-checks everything."""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import AccountRole
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus


class IsMedicalCompanyAccount(BasePermission):
    """Authenticated account whose primary role is MEDICAL_COMPANY
    (capability `marketplace.manage_own_products`)."""

    message = "Only medical company accounts can do this."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == AccountRole.MEDICAL_COMPANY)


class HasMedicalCompany(IsMedicalCompanyAccount):
    """Medical company account that has completed company onboarding."""

    message = "Create your company profile first."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "medical_company")


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
