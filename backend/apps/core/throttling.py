"""Throttles added in Phase 12A."""

from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import UserRateThrottle


class UserWritesThrottle(UserRateThrottle):
    """Caps *state-changing* requests (POST/PUT/PATCH/DELETE) per authenticated account.

    Reads are not throttled (no evidence they need it) and anonymous traffic is untouched (public
    endpoints are read-only; the credential endpoints have their own scopes). It is the default
    class, so views that declare their own `throttle_classes` / scope keep exactly that behaviour.
    The counters live in the per-process cache, so with N gunicorn workers the effective ceiling is
    N × the rate (see docs/OPERATIONS.md); it is a spam/abuse brake, not an exact quota.
    """

    scope = "user_writes"

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return True
        return super().allow_request(request, view)
