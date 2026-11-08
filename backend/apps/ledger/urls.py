from django.urls import path

from . import views

urlpatterns = [
    path("merchant/finance", views.SellerStatementView.as_view(), name="merchant-finance"),
    path(
        "admin/ledger/reconciliation",
        views.ReconciliationView.as_view(),
        name="ledger-reconciliation",
    ),
    path("admin/ledger/entries", views.LedgerEntryListView.as_view(), name="ledger-entries"),
    path("admin/ledger/payables", views.SellerPayableListView.as_view(), name="ledger-payables"),
    path("admin/ledger/policy", views.PolicyListView.as_view(), name="ledger-policy"),
    path(
        "admin/ledger/statements/<uuid:pk>",
        views.AdminStatementView.as_view(),
        name="ledger-statement",
    ),
    path("admin/ledger/settlements", views.SettlementListView.as_view(), name="settlements"),
    path("admin/ledger/recoveries", views.RecoveryListView.as_view(), name="ledger-recoveries"),
    path(
        "admin/ledger/settlements/prepare",
        views.SettlementPrepareView.as_view(),
        name="settlement-prepare",
    ),
    path(
        "admin/ledger/settlements/<uuid:pk>/confirm",
        views.SettlementConfirmView.as_view(),
        name="settlement-confirm",
    ),
    path(
        "admin/ledger/settlements/<uuid:pk>/cancel",
        views.SettlementCancelView.as_view(),
        name="settlement-cancel",
    ),
]
