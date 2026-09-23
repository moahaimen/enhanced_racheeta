from django.urls import path

from . import views

urlpatterns = [
    path("billing/plans", views.PlanListView.as_view(), name="billing-plans"),
    path(
        "admin/billing/subscriptions",
        views.AdminSubscriptionListView.as_view(),
        name="admin-billing-subscriptions",
    ),
    path(
        "admin/billing/subscriptions/<uuid:pk>/activate",
        views.AdminSubscriptionActivateView.as_view(),
        name="admin-billing-activate",
    ),
    path(
        "admin/billing/subscriptions/<uuid:pk>/reject",
        views.AdminSubscriptionRejectView.as_view(),
        name="admin-billing-reject",
    ),
    path(
        "admin/billing/subscriptions/<uuid:pk>/suspend",
        views.AdminSubscriptionSuspendView.as_view(),
        name="admin-billing-suspend",
    ),
    path(
        "admin/billing/subscriptions/<uuid:pk>/cancel",
        views.AdminSubscriptionCancelView.as_view(),
        name="admin-billing-cancel",
    ),
    path(
        "admin/billing/credits", views.AdminCreditGrantView.as_view(), name="admin-billing-credits"
    ),
    path(
        "admin/billing/accounts/<uuid:pk>",
        views.AdminBillingAccountView.as_view(),
        name="admin-billing-account",
    ),
]
