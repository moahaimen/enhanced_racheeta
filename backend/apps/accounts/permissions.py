"""Reusable DRF permission classes. Business modules compose these."""

from rest_framework.permissions import BasePermission

from .roles import AccountRole


class IsAdminAccount(BasePermission):
    """Racheeta administrators only (staff flag, not merely the ADMIN role)."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


def has_role(*roles: AccountRole) -> type[BasePermission]:
    """Factory: `permission_classes = [IsAuthenticated, has_role(Role.PROVIDER)]`."""

    allowed = frozenset(str(r) for r in roles)

    class _HasRole(BasePermission):
        message = "Your account role does not allow this action."

        def has_permission(self, request, view) -> bool:
            user = request.user
            return bool(user and user.is_authenticated and user.role in allowed)

    _HasRole.__name__ = f"HasRole[{','.join(sorted(allowed))}]"
    return _HasRole
