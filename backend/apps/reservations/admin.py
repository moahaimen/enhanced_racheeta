from django.contrib import admin

from .models import AvailabilitySlot, Reservation, ReservationTransition


class InspectionOnlyAdmin(admin.ModelAdmin):
    """Domain-managed records are visible to staff but never mutated in admin."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(InspectionOnlyAdmin):
    list_display = ("provider", "service", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("provider__display_name", "service__title")


@admin.register(Reservation)
class ReservationAdmin(InspectionOnlyAdmin):
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


@admin.register(ReservationTransition)
class ReservationTransitionAdmin(InspectionOnlyAdmin):
    list_display = ("reservation", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)
