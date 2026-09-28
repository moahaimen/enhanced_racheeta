"""Marketplace permissions. Ownership never comes from client ids: company
views resolve `request.user.medical_company`, provider views resolve
`request.user.provider_profile`, and the backend re-checks everything."""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import AccountRole
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


class CanBrowseMarketplace(BasePermission):
    """Capability `marketplace.view_targeted_products`: a PROVIDER account with
    a VERIFIED provider profile. Public visibility (`is_visible`) is NOT
    required — hiding a provider from patient search does not remove its B2B
    access. The targeting itself is decided per product by the queryset."""

    message = "A verified provider profile is required to browse the marketplace."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.role == AccountRole.PROVIDER):
            return False
        profile = getattr(user, "provider_profile", None)
        if profile is None or profile.verification_status != VerificationStatus.VERIFIED:
            return False
        request.provider_profile = profile
        return True
