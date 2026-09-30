from django.urls import path

from . import views

urlpatterns = [
    # reference data
    path(
        "marketplace/categories",
        views.ProductCategoryListView.as_view(),
        name="marketplace-categories",
    ),
    # targeted provider catalogue
    path(
        "marketplace/products", views.TargetedProductListView.as_view(), name="marketplace-products"
    ),
    path(
        "marketplace/products/<uuid:pk>",
        views.TargetedProductDetailView.as_view(),
        name="marketplace-product-detail",
    ),
    # company self-service
    path("marketplace/company", views.MyCompanyView.as_view(), name="marketplace-company"),
    path(
        "marketplace/company/verification/request",
        views.MyCompanyVerificationRequestView.as_view(),
        name="marketplace-company-verification-request",
    ),
    path(
        "marketplace/company/dashboard",
        views.MyCompanyDashboardView.as_view(),
        name="marketplace-company-dashboard",
    ),
    path(
        "marketplace/company/products",
        views.MyProductListView.as_view(),
        name="marketplace-company-products",
    ),
    path(
        "marketplace/company/products/<uuid:pk>",
        views.MyProductDetailView.as_view(),
        name="marketplace-company-product",
    ),
    path(
        "marketplace/company/products/<uuid:pk>/activate",
        views.MyProductActivateView.as_view(),
        name="marketplace-company-product-activate",
    ),
    path(
        "marketplace/company/products/<uuid:pk>/deactivate",
        views.MyProductDeactivateView.as_view(),
        name="marketplace-company-product-deactivate",
    ),
    # administrators
    path(
        "admin/marketplace/companies",
        views.AdminCompanyListView.as_view(),
        name="admin-marketplace-companies",
    ),
    path(
        "admin/marketplace/companies/<uuid:pk>/verification",
        views.AdminCompanyVerificationView.as_view(),
        name="admin-marketplace-company-verification",
    ),
]
