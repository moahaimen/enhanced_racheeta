"""Sellers, listings and suitable uses are lifecycle state owned by the services
(which lock, validate and audit): the admin only INSPECTS them, so it can never
become a second, uncontrolled path for ownership or publication."""

from django.contrib import admin

from .models import ListingSuitableUse, PropertyListing, RealEstateSeller


class _InspectionOnly(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.concrete_fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RealEstateSeller)
class RealEstateSellerAdmin(_InspectionOnly):
    list_display = ("display_name", "seller_type", "account", "created_at")
    list_filter = ("seller_type",)
    search_fields = ("display_name", "account__email")


@admin.register(PropertyListing)
class PropertyListingAdmin(_InspectionOnly):
    list_display = (
        "title",
        "seller",
        "property_type",
        "transaction_type",
        "governorate",
        "publication_status",
        "expires_at",
        "created_at",
    )
    list_filter = ("publication_status", "transaction_type", "property_type")
    search_fields = ("title", "seller__display_name", "district")


@admin.register(ListingSuitableUse)
class ListingSuitableUseAdmin(_InspectionOnly):
    list_display = ("listing", "use", "created_at")
    list_filter = ("use",)
