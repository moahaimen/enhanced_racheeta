from django.urls import path

from . import views

urlpatterns = [
    # public catalogue
    path(
        "real-estate/listings",
        views.PublicListingListView.as_view(),
        name="real-estate-listings",
    ),
    path(
        "real-estate/listings/<uuid:pk>",
        views.PublicListingDetailView.as_view(),
        name="real-estate-listing-detail",
    ),
    # seller self-service
    path("real-estate/owner", views.MySellerView.as_view(), name="real-estate-owner"),
    path(
        "real-estate/owner/dashboard",
        views.MyDashboardView.as_view(),
        name="real-estate-owner-dashboard",
    ),
    path(
        "real-estate/owner/listings",
        views.MyListingListView.as_view(),
        name="real-estate-owner-listings",
    ),
    path(
        "real-estate/owner/listings/<uuid:pk>",
        views.MyListingDetailView.as_view(),
        name="real-estate-owner-listing",
    ),
    path(
        "real-estate/owner/listings/<uuid:pk>/publish",
        views.MyListingPublishView.as_view(),
        name="real-estate-owner-listing-publish",
    ),
    path(
        "real-estate/owner/listings/<uuid:pk>/unpublish",
        views.MyListingUnpublishView.as_view(),
        name="real-estate-owner-listing-unpublish",
    ),
]
