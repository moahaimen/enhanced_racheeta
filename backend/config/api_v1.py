"""Version 1 API routing. Every business module registers its URLs here."""

from django.urls import include, path, re_path

from apps.accounts.views import ApiNotFoundView

app_name = "v1"

urlpatterns = [
    path("", include("apps.accounts.urls")),
    # Must stay last: JSON 404 for anything unmatched under /api/v1/.
    re_path(r"^.*$", ApiNotFoundView.as_view(), name="api-not-found"),
]
