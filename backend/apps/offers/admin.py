from django.contrib import admin

from .models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "offer_price", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "provider__display_name", "service_title_snapshot")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
