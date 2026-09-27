from django.urls import path

from . import views

urlpatterns = [
    path(
        "providers/<uuid:provider_id>/availability",
        views.PublicAvailabilityView.as_view(),
        name="provider-availability-public",
    ),
    path(
        "reservations/provider/availability",
        views.ProviderAvailabilityListView.as_view(),
        name="provider-availability",
    ),
    path(
        "reservations/provider/availability/<uuid:pk>",
        views.ProviderAvailabilityDetailView.as_view(),
        name="provider-availability-detail",
    ),
    path(
        "reservations/provider",
        views.ProviderReservationListView.as_view(),
        name="provider-reservations",
    ),
    path(
        "reservations/provider/<uuid:pk>",
        views.ProviderReservationDetailView.as_view(),
        name="provider-reservation-detail",
    ),
    path(
        "reservations/provider/<uuid:pk>/transition",
        views.ProviderReservationTransitionView.as_view(),
        name="provider-reservation-transition",
    ),
    path("reservations", views.ReservationCreateView.as_view(), name="reservation-create"),
    path("reservations/me", views.MyReservationListView.as_view(), name="my-reservations"),
    path(
        "reservations/me/<uuid:pk>",
        views.MyReservationDetailView.as_view(),
        name="my-reservation-detail",
    ),
    path(
        "reservations/me/<uuid:pk>/cancel",
        views.MyReservationCancelView.as_view(),
        name="my-reservation-cancel",
    ),
]
