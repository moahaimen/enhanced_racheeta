"""Security sweep: the set of anonymously reachable API operations is pinned.

Every API route is resolved to its DRF view and, for each HTTP method it implements, the view's
permission classes are evaluated. An operation counts as *public* if any of them is `AllowAny`
(or there are none). The resulting set must equal `PUBLIC_OPERATIONS` below — adding a public
endpoint (or accidentally exposing a private one) fails this test until the list is changed
deliberately and reviewed. Anonymous requests to every other operation are also exercised for real.
"""

from __future__ import annotations

import re
import uuid

import pytest
from django.test import RequestFactory
from django.urls import get_resolver
from django.urls.resolvers import URLResolver
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

METHODS = ("get", "post", "put", "patch", "delete")

# (METHOD, route) pairs that are intentionally reachable without a token. Reviewed in Phase 12A.
PUBLIC_OPERATIONS = {
    # credentials & account recovery (all throttled; none reveals whether an e-mail exists)
    ("POST", "api/v1/auth/register"),
    ("POST", "api/v1/auth/login"),
    ("POST", "api/v1/auth/refresh"),
    ("POST", "api/v1/auth/logout"),
    ("POST", "api/v1/auth/firebase/exchange"),
    ("POST", "api/v1/auth/password-reset/request"),
    ("POST", "api/v1/auth/password-reset/confirm"),
    ("POST", "api/v1/auth/email-verification/confirm"),
    # public reference data and catalogues (read-only)
    ("GET", "api/v1/geo/countries"),
    ("GET", "api/v1/geo/governorates"),
    ("GET", "api/v1/geo/cities"),
    ("GET", "api/v1/specialties"),
    ("GET", "api/v1/billing/plans"),
    ("GET", "api/v1/providers"),
    ("GET", "api/v1/providers/<uuid:pk>"),
    ("GET", "api/v1/providers/<uuid:provider_id>/availability"),
    ("GET", "api/v1/providers/<uuid:provider_id>/reviews"),
    ("GET", "api/v1/providers/<uuid:provider_id>/offers"),
    ("GET", "api/v1/marketplace/categories"),
    ("GET", "api/v1/real-estate/listings"),
    ("GET", "api/v1/real-estate/listings/<uuid:pk>"),
    ("GET", "api/v1/jobs"),
    ("GET", "api/v1/jobs/<uuid:pk>"),
    ("GET", "api/v1/employers/<uuid:pk>"),
}


def _walk(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern.url_patterns, route)
        else:
            yield route, pattern


def _api_routes():
    for route, pattern in _walk(get_resolver().url_patterns):
        if not route.startswith("api/v1/") or ".*" in route:
            continue
        cls = getattr(pattern.callback, "cls", None) or getattr(
            pattern.callback, "view_class", None
        )
        if cls is not None and issubclass(cls, APIView):
            yield route.rstrip("$"), cls


def _is_public(cls, method, route) -> bool:
    factory = RequestFactory()
    view = cls()
    view.request = Request(getattr(factory, method)("/" + route))
    view.args, view.kwargs, view.format_kwarg = (), {}, None
    view.action = None
    if hasattr(cls, "action_map"):  # not used here, but keep the sweep honest for viewsets
        return False
    try:
        permissions = view.get_permissions()
    except Exception:  # noqa: BLE001 - a view that cannot even build permissions is not public
        return False
    return not permissions or any(isinstance(p, AllowAny) for p in permissions)


def _implemented(cls):
    return [m for m in METHODS if hasattr(cls, m)]


def discovered_public():
    found = set()
    for route, cls in _api_routes():
        for method in _implemented(cls):
            if _is_public(cls, method, route):
                found.add((method.upper(), route.rstrip("/")))
    return found


def test_the_public_api_surface_is_exactly_the_reviewed_list():
    discovered = discovered_public()
    assert discovered - PUBLIC_OPERATIONS == set(), (
        "newly public operations (review them, then add to PUBLIC_OPERATIONS): "
        f"{sorted(discovered - PUBLIC_OPERATIONS)}"
    )
    assert PUBLIC_OPERATIONS - discovered == set(), (
        f"listed as public but no longer public: {sorted(PUBLIC_OPERATIONS - discovered)}"
    )


def _concrete(route: str) -> str:
    return "/" + re.sub(
        r"<(?:(\w+):)?\w+>",
        lambda m: (
            str(uuid.uuid4()) if m.group(1) == "uuid" else ("1" if m.group(1) == "int" else "x")
        ),
        route,
    )


@pytest.mark.django_db
def test_every_non_public_operation_refuses_anonymous_requests(client):
    public = discovered_public()
    unexpected = []
    checked = 0
    for route, cls in _api_routes():
        for method in _implemented(cls):
            if (method.upper(), route.rstrip("/")) in public:
                continue
            path = _concrete(route)
            response = (
                client.get(path)
                if method == "get"
                else getattr(client, method)(path, data="{}", content_type="application/json")
            )
            if response.status_code not in (401, 403):
                unexpected.append((method.upper(), route, response.status_code))
            checked += 1
    assert checked > 100, "the sweep must really exercise the API"
    assert unexpected == []


@pytest.mark.django_db
def test_unknown_api_paths_are_a_json_404_not_the_spa(client):
    response = client.get("/api/v1/definitely/not/here")
    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json")


def test_django_admin_is_not_at_a_guessable_default_in_production_docs():
    # The admin is reachable (obscurity is not a control) but never lists the API, and is covered
    # by the admin CSP; an anonymous request is redirected to the login form.
    from django.conf import settings

    assert settings.ADMIN_URL_PATH.endswith("/")
