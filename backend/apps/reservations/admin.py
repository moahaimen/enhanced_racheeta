from django.contrib import admin

from .models import AvailabilitySlot, Reservation, ReservationTransition


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("provider", "service", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("provider__display_name", "service__title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "provider_name_snapshot",
        "service_title_snapshot",
        "starts_at",
        "status",
    )
    list_filter = ("status",)
    search_fields = (
        "patient__email",
        "provider_name_snapshot",
        "service_title_snapshot",
    )
    readonly_fields = ("status_changed_at", "created_at", "updated_at")


@admin.register(ReservationTransition)
class ReservationTransitionAdmin(admin.ModelAdmin):
    list_display = ("reservation", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)
    readonly_fields = ("created_at", "updated_at")
