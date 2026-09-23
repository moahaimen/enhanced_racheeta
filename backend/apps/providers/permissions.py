"""Provider permissions. Ownership is never derived from client-supplied ids:
self-management views resolve `request.user.provider_profile`."""

from rest_framework.permissions import BasePermission

from apps.accounts.roles import AccountRole


class IsProviderAccount(BasePermission):
    """Authenticated account whose primary role is PROVIDER."""

    message = "Only provider accounts can do this."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == AccountRole.PROVIDER)


class HasProviderProfile(IsProviderAccount):
    """Provider account that has completed provider onboarding."""

    message = "Create your provider profile first."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, "provider_profile")
