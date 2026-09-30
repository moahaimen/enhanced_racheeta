"""Real-estate permissions. Ownership never comes from client ids: owner views
resolve `request.user.real_estate_seller`, and the services re-check the
account's role and active flag on locked, current rows."""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import AccountRole


class IsRealEstateSellerAccount(BasePermission):
    """Authenticated account whose primary role is REAL_ESTATE_SELLER
    (capability `real_estate.manage_own_listings`)."""

    message = "Only real-estate seller accounts can do this."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == AccountRole.REAL_ESTATE_SELLER)


class HasRealEstateSeller(IsRealEstateSellerAccount):
    """Seller account that has completed onboarding."""

    message = "Create your seller profile first."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "real_estate_seller")
