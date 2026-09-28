from django.urls import path

from . import views

urlpatterns = [
    path(
        "providers/<uuid:provider_id>/reviews",
        views.PublicProviderReviewListView.as_view(),
        name="provider-reviews-public",
    ),
    path("reviews", views.ReviewCreateView.as_view(), name="review-create"),
    path("reviews/me", views.MyReviewListView.as_view(), name="my-reviews"),
]
