"""Root URL configuration.

Public application APIs live exclusively under /api/v1/ (config/api_v1.py).
"""

import re

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import health, spa_index

urlpatterns = [
    path("health/", health, name="health"),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path("api/v1/", include("config.api_v1")),
    path("api/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="openapi-schema"),
        name="openapi-docs",
    ),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Catch-all for the React SPA (only when a build is configured). Must be last.
_reserved = "|".join(
    re.escape(p) for p in ("api/", settings.ADMIN_URL_PATH, "health/", "static/", "media/")
)
urlpatterns += [re_path(rf"^(?!{_reserved}).*$", spa_index, name="spa")]
