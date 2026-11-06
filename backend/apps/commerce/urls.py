from django.urls import path

from . import views as v

urlpatterns = [
    path("store/products", v.StoreProductListView.as_view(), name="store-products"),
    path("store/products/<uuid:pk>", v.StoreProductDetailView.as_view(), name="store-product"),
    path("store/categories", v.StoreCategoryListView.as_view(), name="store-categories"),
    # buyer
    path("checkouts", v.CheckoutListView.as_view(), name="checkouts"),
    path("checkouts/preview", v.CheckoutPreviewView.as_view(), name="checkout-preview"),
    path("orders", v.MyOrderListView.as_view(), name="orders"),
    path(
        "orders/delivery-defaults", v.DeliveryDefaultsView.as_view(), name="order-delivery-defaults"
    ),
    path("orders/<uuid:pk>", v.MyOrderDetailView.as_view(), name="order"),
    path("orders/<uuid:pk>/cancel", v.MyOrderCancelView.as_view(), name="order-cancel"),
    path(
        "orders/<uuid:pk>/confirm-delivery",
        v.MyOrderConfirmDeliveryView.as_view(),
        name="order-confirm-delivery",
    ),
    path("orders/<uuid:pk>/returns", v.MyOrderReturnView.as_view(), name="order-return"),
    path("orders/<uuid:pk>/disputes", v.MyOrderDisputeView.as_view(), name="order-dispute"),
    path("orders/<uuid:pk>/invoices", v.MyOrderInvoiceListView.as_view(), name="order-invoices"),
    path(
        "orders/<uuid:pk>/invoices/<uuid:invoice_id>",
        v.MyOrderInvoiceDetailView.as_view(),
        name="order-invoice",
    ),
    # seller
    path("merchant/orders", v.MerchantOrderListView.as_view(), name="merchant-orders"),
    path("merchant/orders/<uuid:pk>", v.MerchantOrderDetailView.as_view(), name="merchant-order"),
    path(
        "merchant/orders/<uuid:pk>/transition",
        v.MerchantOrderTransitionView.as_view(),
        name="merchant-order-transition",
    ),
    path(
        "merchant/orders/<uuid:pk>/tracking",
        v.MerchantTrackingView.as_view(),
        name="merchant-order-tracking",
    ),
    path(
        "merchant/orders/<uuid:pk>/invoices",
        v.MerchantOrderInvoiceListView.as_view(),
        name="merchant-order-invoices",
    ),
    path(
        "merchant/orders/<uuid:pk>/invoices/<uuid:invoice_id>",
        v.MerchantOrderInvoiceDetailView.as_view(),
        name="merchant-order-invoice",
    ),
    path("merchant/reports/sales", v.MerchantSalesReportView.as_view(), name="merchant-report"),
    path(
        "admin/commerce/reports/marketplace",
        v.AdminMarketplaceReportView.as_view(),
        name="admin-marketplace-report",
    ),
    path("merchant/returns", v.MerchantReturnListView.as_view(), name="merchant-returns"),
    path(
        "merchant/returns/<uuid:pk>/decide",
        v.MerchantReturnDecideView.as_view(),
        name="merchant-return-decide",
    ),
    path(
        "merchant/returns/<uuid:pk>/received",
        v.MerchantReturnReceivedView.as_view(),
        name="merchant-return-received",
    ),
    path("merchant/inventory", v.MerchantInventoryView.as_view(), name="merchant-inventory"),
    path(
        "merchant/inventory/<uuid:pk>/adjust",
        v.MerchantStockAdjustView.as_view(),
        name="merchant-stock-adjust",
    ),
    path(
        "merchant/inventory/<uuid:pk>/threshold",
        v.MerchantStockThresholdView.as_view(),
        name="merchant-stock-threshold",
    ),
    path(
        "merchant/inventory/<uuid:pk>/movements",
        v.MerchantStockMovementListView.as_view(),
        name="merchant-stock-movements",
    ),
    path("merchant/coupons", v.MerchantCouponListView.as_view(), name="merchant-coupons"),
    path(
        "merchant/coupons/<uuid:pk>/deactivate",
        v.MerchantCouponDeactivateView.as_view(),
        name="merchant-coupon-deactivate",
    ),
    path("merchant/offers", v.MerchantOfferListView.as_view(), name="merchant-offers"),
    path(
        "merchant/offers/<uuid:pk>/deactivate",
        v.MerchantOfferDeactivateView.as_view(),
        name="merchant-offer-deactivate",
    ),
    # Racheeta finance
    path("admin/commerce/orders", v.AdminOrderListView.as_view(), name="admin-orders"),
    path("admin/commerce/orders/<uuid:pk>", v.AdminOrderDetailView.as_view(), name="admin-order"),
    path(
        "admin/commerce/orders/<uuid:pk>/verify-payment",
        v.AdminVerifyPaymentView.as_view(),
        name="admin-order-verify-payment",
    ),
    path(
        "admin/commerce/orders/<uuid:pk>/confirm-delivery",
        v.AdminConfirmDeliveryView.as_view(),
        name="admin-order-confirm-delivery",
    ),
    path(
        "admin/commerce/orders/<uuid:pk>/complete",
        v.AdminCompleteOrderView.as_view(),
        name="admin-order-complete",
    ),
    path(
        "admin/commerce/orders/<uuid:pk>/refund-cancelled",
        v.AdminRefundCancelledView.as_view(),
        name="admin-order-refund-cancelled",
    ),
    path("admin/commerce/returns", v.AdminReturnListView.as_view(), name="admin-returns"),
    path(
        "admin/commerce/returns/<uuid:pk>/refund",
        v.AdminReturnRefundView.as_view(),
        name="admin-return-refund",
    ),
    path("admin/commerce/disputes", v.AdminDisputeListView.as_view(), name="admin-disputes"),
    path(
        "admin/commerce/disputes/<uuid:pk>/resolve",
        v.AdminDisputeResolveView.as_view(),
        name="admin-dispute-resolve",
    ),
    path("admin/commerce/coupons", v.AdminCouponListView.as_view(), name="admin-coupons"),
    path(
        "admin/commerce/coupons/<uuid:pk>/deactivate",
        v.AdminCouponDeactivateView.as_view(),
        name="admin-coupon-deactivate",
    ),
    # quotes
    path("quotes", v.MyQuoteListView.as_view(), name="quotes"),
    path("quotes/<uuid:pk>/close", v.MyQuoteCloseView.as_view(), name="quote-close"),
    path("quotes/<uuid:pk>/order", v.MyQuoteOrderView.as_view(), name="quote-order"),
    path("merchant/quotes", v.MerchantQuoteListView.as_view(), name="merchant-quotes"),
    path(
        "merchant/quotes/<uuid:pk>/respond",
        v.MerchantQuoteRespondView.as_view(),
        name="merchant-quote-respond",
    ),
    path(
        "merchant/quotes/<uuid:pk>/decline",
        v.MerchantQuoteDeclineView.as_view(),
        name="merchant-quote-decline",
    ),
]
