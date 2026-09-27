from rest_framework import status
from rest_framework.exceptions import APIException


class EntitlementError(APIException):
    """Base for typed commercial errors; rendered through the uniform envelope."""

    status_code = status.HTTP_403_FORBIDDEN
    default_code = "entitlement_required"
    default_detail = "Your current plan does not include this feature."

    def __init__(
        self,
        detail=None,
        code=None,
        *,
        key: str | None = None,
        limit: int | None = None,
        used: int | None = None,
    ):
        super().__init__(detail, code)
        self.key = key
        self.limit = limit
        self.used = used


class SubscriptionRequired(EntitlementError):
    default_code = "subscription_required"
    default_detail = "An active subscription is required for this action."


class UsageLimitReached(EntitlementError):
    default_code = "usage_limit_reached"
    default_detail = "You have reached the limit of your current plan."
