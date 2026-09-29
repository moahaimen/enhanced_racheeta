from django.contrib import admin, messages

from . import services
from .models import ProviderMembership, ProviderProfile, ServiceOffering
from .types import VerificationStatus


class ServiceInline(admin.TabularInline):
    model = ServiceOffering
    extra = 0
    can_delete = False
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
        "verification_status",
        "verification_requested_at",
        "verification_changed_at",
        "verified_at",
        "created_at",
        "updated_at",
    )
    inlines = [ServiceInline]
    actions = ["mark_verified", "mark_rejected", "mark_suspended"]

    # ADR-045: the admin forms cannot bypass verified identity. The status only
    # moves through the guarded actions below (services.set_verification:
    # VERIFIED only from PENDING, on the locked row), and an existing profile's
    # identity (provider type, specialties) is never edited by staff — the owner
    # edits it outside review and requests verification again.
    IDENTITY_READONLY = ("provider_type", "specialties")

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields += self.IDENTITY_READONLY
        return fields

    @admin.action(description="Mark selected providers VERIFIED (pending review only)")
    def mark_verified(self, request, queryset):
        skipped = 0
        for profile in queryset:
            try:
                services.set_verification(profile, VerificationStatus.VERIFIED, by=request.user)
            except services.InvalidTransition:
                skipped += 1  # ADR-045: only PENDING profiles can be verified
        if skipped:
            self.message_user(
                request,
                f"{skipped} profile(s) were not pending review and were left unchanged.",
                level=messages.WARNING,
            )

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

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("provider",)
        return ()

    def has_delete_permission(self, request, obj=None):
        # Service deletion must go through the owner API so reservation-slot
        # protection and conflict handling cannot be bypassed.
        return False
