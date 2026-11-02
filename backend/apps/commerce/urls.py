from django.urls import path

from . import views

urlpatterns = [
    path("store/products", views.StoreProductListView.as_view(), name="store-products"),
    path("store/products/<uuid:pk>", views.StoreProductDetailView.as_view(), name="store-product"),
    path("store/categories", views.StoreCategoryListView.as_view(), name="store-categories"),
    path("orders", views.MyOrderListView.as_view(), name="orders"),
    path(
        "orders/delivery-defaults",
        views.DeliveryDefaultsView.as_view(),
        name="order-delivery-defaults",
    ),
    path("orders/<uuid:pk>", views.MyOrderDetailView.as_view(), name="order"),
    path("orders/<uuid:pk>/cancel", views.MyOrderCancelView.as_view(), name="order-cancel"),
    path("merchant/orders", views.MerchantOrderListView.as_view(), name="merchant-orders"),
    path(
        "merchant/orders/<uuid:pk>", views.MerchantOrderDetailView.as_view(), name="merchant-order"
    ),
    path(
        "merchant/orders/<uuid:pk>/transition",
        views.MerchantOrderTransitionView.as_view(),
        name="merchant-order-transition",
    ),
    path(
        "merchant/orders/<uuid:pk>/payment-received",
        views.MerchantOrderPaymentView.as_view(),
        name="merchant-order-payment",
    ),
    path("quotes", views.MyQuoteListView.as_view(), name="quotes"),
    path("quotes/<uuid:pk>/close", views.MyQuoteCloseView.as_view(), name="quote-close"),
    path("merchant/quotes", views.MerchantQuoteListView.as_view(), name="merchant-quotes"),
    path(
        "merchant/quotes/<uuid:pk>/respond",
        views.MerchantQuoteRespondView.as_view(),
        name="merchant-quote-respond",
    ),
    path(
        "merchant/quotes/<uuid:pk>/decline",
        views.MerchantQuoteDeclineView.as_view(),
        name="merchant-quote-decline",
    ),
]
