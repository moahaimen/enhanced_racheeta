from django.urls import path

from . import views

urlpatterns = [
    # providers
    path(
        "advertising/marketplace",
        views.SponsoredCampaignListView.as_view(),
        name="advertising-marketplace",
    ),
    # company self-service
    path(
        "advertising/company/dashboard",
        views.DashboardView.as_view(),
        name="advertising-company-dashboard",
    ),
    path("advertising/company/quote", views.QuoteView.as_view(), name="advertising-company-quote"),
    path(
        "advertising/company/campaigns",
        views.CampaignListView.as_view(),
        name="advertising-company-campaigns",
    ),
    path(
        "advertising/company/campaigns/<uuid:pk>",
        views.CampaignDetailView.as_view(),
        name="advertising-company-campaign",
    ),
    path(
        "advertising/company/campaigns/<uuid:pk>/submit",
        views.CampaignSubmitView.as_view(),
        name="advertising-company-campaign-submit",
    ),
    path(
        "advertising/company/campaigns/<uuid:pk>/cancel",
        views.CampaignCancelView.as_view(),
        name="advertising-company-campaign-cancel",
    ),
    # administrators
    path(
        "admin/advertising/campaigns",
        views.AdminCampaignListView.as_view(),
        name="admin-advertising-campaigns",
    ),
    path(
        "admin/advertising/campaigns/<uuid:pk>",
        views.AdminCampaignDetailView.as_view(),
        name="admin-advertising-campaign",
    ),
    path(
        "admin/advertising/campaigns/<uuid:pk>/verify-payment",
        views.AdminVerifyPaymentView.as_view(),
        name="admin-advertising-verify-payment",
    ),
    path(
        "admin/advertising/campaigns/<uuid:pk>/reject-payment",
        views.AdminRejectPaymentView.as_view(),
        name="admin-advertising-reject-payment",
    ),
]
