from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def health(_request: HttpRequest) -> JsonResponse:
    """Liveness probe for Railway. Intentionally does not touch the database:
    a DB outage should surface as API errors, not as the platform restarting
    a perfectly healthy process."""
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def ready(_request: HttpRequest) -> JsonResponse:
    """Readiness probe: can this instance safely take traffic? (PostgreSQL answers.)

    Distinct from `/health/` (liveness, no dependencies): a database outage must make a *new*
    deployment fail its readiness check instead of replacing a working one, without making the
    platform restart a healthy process. The body is deliberately minimal — no host, SQL or
    exception text ever leaves this function.
    """
    try:
        # A database that accepts the connection but never answers must not hang the worker:
        # bound the probe query itself (SET LOCAL needs the surrounding transaction).
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = 2000")
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


@require_GET
@never_cache
def spa_index(_request: HttpRequest, *_args, **_kwargs):
    """Serve the React build's index.html for client-side routes.

    Only active when SPA_DIST_DIR points at an existing build; otherwise
    non-API paths are a 404 so the API-only deployment stays honest.
    """
    dist = settings.SPA_DIST_DIR
    if dist is None:
        raise Http404("Web application build is not configured.")
    index = dist / "index.html"
    if not index.is_file():
        raise Http404("Web application build is missing index.html.")
    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
