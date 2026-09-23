from django.contrib import admin

from . import services
from .models import ProviderMembership, ProviderProfile, ServiceOffering
from .types import VerificationStatus


class ServiceInline(admin.TabularInline):
    model = ServiceOffering
    extra = 0
    fields = ("title", "specialty", "price", "currency", "duration_minutes", "is_active")


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "provider_type",
        "verification_status",
        "is_visible",
        "governorate",
        "city",
        "account",
        "created_at",
    )
    list_filter = ("provider_type", "verification_status", "is_visible", "governorate")
    search_fields = ("display_name", "account__email", "phone")
    autocomplete_fields = ("account", "governorate", "city")
    filter_horizontal = ("specialties",)
    readonly_fields = (
        "id",
        "verification_requested_at",
        "verification_changed_at",
        "verified_at",
        "created_at",
        "updated_at",
    )
    inlines = [ServiceInline]
    actions = ["mark_verified", "mark_rejected", "mark_suspended"]

    @admin.action(description="Mark selected providers VERIFIED")
    def mark_verified(self, request, queryset):
        for profile in queryset:
            services.set_verification(profile, VerificationStatus.VERIFIED, by=request.user)

    @admin.action(description="Mark selected providers REJECTED")
    def mark_rejected(self, request, queryset):
        for profile in queryset:
            services.set_verification(profile, VerificationStatus.REJECTED, by=request.user)

    @admin.action(description="Mark selected providers SUSPENDED")
    def mark_suspended(self, request, queryset):
        for profile in queryset:
            services.set_verification(profile, VerificationStatus.SUSPENDED, by=request.user)


@admin.register(ProviderMembership)
class ProviderMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "practitioner",
        "facility",
        "status",
        "initiated_by",
        "role_title",
        "created_at",
    )
    list_filter = ("status", "initiated_by")
    search_fields = ("practitioner__display_name", "facility__display_name")
    autocomplete_fields = ("practitioner", "facility")


@admin.register(ServiceOffering)
class ServiceOfferingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "provider",
        "specialty",
        "price",
        "currency",
        "duration_minutes",
        "is_active",
    )
    list_filter = ("is_active", "currency")
    search_fields = ("title", "provider__display_name")
    autocomplete_fields = ("provider", "specialty")
