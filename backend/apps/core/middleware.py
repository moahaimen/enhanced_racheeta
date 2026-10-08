"""Request correlation id and response security headers (CSP, Permissions-Policy)."""

from __future__ import annotations

import contextvars
import re
import uuid

from django.conf import settings

# A client may supply X-Request-ID; only a short, boring value is ever accepted (it ends up in
# logs and in the response header), anything else is replaced by a server-generated id.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def current_request_id() -> str:
    return request_id_var.get()


class RequestIdMiddleware:
    """Gives every request an id: a validated client value or a fresh UUID.

    The id is exposed to log records (`apps.core.logging.JsonFormatter`) and echoed in the
    response so an operator can correlate a user report with a log line. It carries no user data.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.META.get("HTTP_X_REQUEST_ID", "")
        request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response


def _join(*directives: str) -> str:
    return "; ".join(directives)


def build_app_policy(*, connect_extra: tuple[str, ...] = (), upgrade: bool = False) -> str:
    """CSP for the React single-page app (the production document policy).

    * scripts: same-origin only (Vite emits one module script; no inline script, no eval);
    * styles: same-origin plus the Google Fonts stylesheet the app links; React's `style={}`
      props are applied through the CSSOM, which CSP does not restrict, so `'unsafe-inline'` is
      NOT needed;
    * fonts: gstatic (the IBM Plex Sans Arabic files); images: self + data: URIs;
    * connections: same-origin API (extend with CSP_CONNECT_SRC if the API lives elsewhere);
    * no plugins, no framing, restricted base/form targets.
    """
    connect = " ".join(("'self'", *connect_extra))
    directives = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        f"connect-src {connect}",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    if upgrade:
        directives.append("upgrade-insecure-requests")
    return _join(*directives)


# JSON API responses: they are never rendered as documents, so forbid everything.
API_POLICY = _join("default-src 'none'", "frame-ancestors 'none'", "base-uri 'none'")

# Django admin: first-party scripts only; it uses a few inline style attributes/blocks.
ADMIN_POLICY = _join(
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
)

PERMISSIONS_POLICY = ", ".join(
    f"{feature}=()"
    for feature in (
        "accelerometer",
        "camera",
        "geolocation",
        "gyroscope",
        "magnetometer",
        "microphone",
        "payment",
        "usb",
        "interest-cohort",
    )
)


class SecurityHeadersMiddleware:
    """Adds Content-Security-Policy and Permissions-Policy when DEBUG is off.

    Django's SecurityMiddleware already sets X-Content-Type-Options, Referrer-Policy and
    Cross-Origin-Opener-Policy and XFrameOptionsMiddleware sets X-Frame-Options; this only adds what
    they do not, and never overwrites a header a view set itself. The interactive API docs (served
    only when enabled, never in production by default) pull Swagger UI from a CDN with an inline
    bootstrap script, so they are deliberately left without a CSP.
    """

    DOCS_PREFIXES = ("/api/docs/", "/api/schema/")

    def __init__(self, get_response):
        self.get_response = get_response
        self.app_policy = build_app_policy(
            connect_extra=tuple(getattr(settings, "CSP_CONNECT_SRC", ())),
            upgrade=bool(getattr(settings, "SECURE_PROXY_SSL", False)),
        )

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG:
            return response
        path = request.path
        if "Content-Security-Policy" not in response and not path.startswith(self.DOCS_PREFIXES):
            if path.startswith("/api/"):
                policy = API_POLICY
            elif path.startswith("/" + settings.ADMIN_URL_PATH):
                policy = ADMIN_POLICY
            else:
                policy = self.app_policy
            response["Content-Security-Policy"] = policy
        if "Permissions-Policy" not in response:
            response["Permissions-Policy"] = PERMISSIONS_POLICY
        return response
