"""Categories and audience rules are administrator reference data (editable
here); companies and products are lifecycle state owned by the services and
are inspection-only."""

from django.contrib import admin

from .models import MedicalCompany, Product, ProductAudience, ProductCategory


class ProductAudienceInline(admin.TabularInline):
    model = ProductAudience
    extra = 0
    autocomplete_fields = ("specialty",)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "slug", "parent", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name_en", "name_ar", "slug")
    inlines = [ProductAudienceInline]


@admin.register(ProductAudience)
class ProductAudienceAdmin(admin.ModelAdmin):
    list_display = ("category", "provider_type", "specialty", "is_active")
    list_filter = ("is_active", "provider_type")
    autocomplete_fields = ("specialty",)


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


@admin.register(MedicalCompany)
class MedicalCompanyAdmin(_InspectionOnly):
    list_display = ("name", "account", "verification_status", "governorate", "created_at")
    list_filter = ("verification_status",)
    search_fields = ("name", "account__email")


@admin.register(Product)
class ProductAdmin(_InspectionOnly):
    list_display = ("title", "company", "category", "price", "currency", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("title", "company__name")
