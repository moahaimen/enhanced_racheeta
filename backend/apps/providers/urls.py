from django.urls import path

from . import views

urlpatterns = [
    # public discovery
    path("providers", views.ProviderListView.as_view(), name="providers-list"),
    # self-management (must be declared before the <uuid:pk> route)
    path("providers/me", views.MyProviderView.as_view(), name="providers-me"),
    path(
        "providers/me/verification/request",
        views.MyVerificationRequestView.as_view(),
        name="providers-me-verification-request",
    ),
    path("providers/me/services", views.MyServiceListView.as_view(), name="providers-me-services"),
    path(
        "providers/me/services/<uuid:pk>",
        views.MyServiceDetailView.as_view(),
        name="providers-me-service-detail",
    ),
    path(
        "providers/me/memberships",
        views.MyMembershipListView.as_view(),
        name="providers-me-memberships",
    ),
    path(
        "providers/me/memberships/<uuid:pk>/accept",
        views.MembershipAcceptView.as_view(),
        name="providers-me-membership-accept",
    ),
    path(
        "providers/me/memberships/<uuid:pk>/reject",
        views.MembershipRejectView.as_view(),
        name="providers-me-membership-reject",
    ),
    path(
        "providers/me/memberships/<uuid:pk>/end",
        views.MembershipEndView.as_view(),
        name="providers-me-membership-end",
    ),
    path("providers/<uuid:pk>", views.ProviderDetailView.as_view(), name="providers-detail"),
    # administrators
    path(
        "admin/providers/<uuid:pk>/verification",
        views.AdminVerificationView.as_view(),
        name="admin-provider-verification",
    ),
]
