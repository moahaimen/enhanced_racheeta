"""Uniform API error envelope.

Every error response has the shape:

    {
      "error": {
        "code": "validation_error",
        "message": "Human readable summary.",
        "details": {...}            # optional; field errors for validation
      }
    }

Documented in docs/API.md. Unhandled exceptions fall through to Django's
500 handling (never leak stack traces when DEBUG is false).
"""

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

_STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "validation_error",
    status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    status.HTTP_429_TOO_MANY_REQUESTS: "throttled",
}


def _message_for(exc: Exception, response: Response) -> str:
    if isinstance(exc, exceptions.ValidationError):
        return "Validation failed."
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str | exceptions.ErrorDetail):
        return str(detail)
    if isinstance(detail, dict) and "detail" in detail:
        return str(detail["detail"])
    return str(getattr(exc, "default_detail", "Request failed."))


def api_exception_handler(exc: Exception, context: dict) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # Not an API exception; let Django handle it.

    code = _STATUS_CODES.get(response.status_code, "error")
    # Prefer the exception's own machine code when it has one, e.g.
    # AuthenticationFailed(..., code="no_active_account").
    if isinstance(exc, exceptions.APIException) and not isinstance(exc, exceptions.ValidationError):
        codes = exc.get_codes()
        if isinstance(codes, str):
            code = codes
        elif isinstance(codes, dict) and isinstance(codes.get("detail"), str):
            code = codes["detail"]

    payload: dict = {"code": code, "message": _message_for(exc, response)}

    if isinstance(exc, exceptions.ValidationError):
        details = response.data
        if isinstance(details, list):
            details = {"non_field_errors": details}
        payload["details"] = details

    response.data = {"error": payload}
    return response
