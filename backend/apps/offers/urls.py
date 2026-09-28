from django.urls import path

from . import views

urlpatterns = [
    path(
        "providers/<uuid:provider_id>/offers",
        views.PublicProviderOfferListView.as_view(),
        name="provider-offers-public",
    ),
    path("offers/provider", views.ProviderOfferListView.as_view(), name="provider-offers"),
    path(
        "offers/provider/<uuid:pk>",
        views.ProviderOfferDetailView.as_view(),
        name="provider-offer-detail",
    ),
]
