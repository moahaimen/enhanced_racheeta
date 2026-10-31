from django.urls import path

from . import views

urlpatterns = [
    path("workspaces", views.WorkspaceListView.as_view(), name="workspaces"),
    path(
        "workspaces/dashboard", views.WorkspaceDashboardView.as_view(), name="workspace-dashboard"
    ),
    path(
        "workspaces/facility/<uuid:pk>",
        views.FacilityWorkspaceView.as_view(),
        name="workspace-facility",
    ),
    path(
        "workspaces/facility/<uuid:pk>/reservations",
        views.FacilityReservationListView.as_view(),
        name="workspace-facility-reservations",
    ),
    path(
        "workspaces/facility/<uuid:pk>/reservations/<uuid:reservation_id>/transition",
        views.FacilityReservationTransitionView.as_view(),
        name="workspace-facility-reservation-transition",
    ),
    path(
        "workspaces/company/<uuid:pk>",
        views.CompanyWorkspaceView.as_view(),
        name="workspace-company",
    ),
    path(
        "workspaces/facility/<uuid:pk>/members",
        views.MemberListView.as_view(),
        {"kind": "facility"},
        name="workspace-facility-members",
    ),
    path(
        "workspaces/facility/<uuid:pk>/members/<uuid:member_id>/end",
        views.MemberEndView.as_view(),
        {"kind": "facility"},
        name="workspace-facility-member-end",
    ),
    path(
        "workspaces/company/<uuid:pk>/members",
        views.MemberListView.as_view(),
        {"kind": "company"},
        name="workspace-company-members",
    ),
    path(
        "workspaces/company/<uuid:pk>/members/<uuid:member_id>/end",
        views.MemberEndView.as_view(),
        {"kind": "company"},
        name="workspace-company-member-end",
    ),
]
