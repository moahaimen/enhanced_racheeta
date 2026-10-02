from django.contrib import admin

from .models import Notification, PushDevice


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Inspection only: staff can look, never fabricate or alter notifications."""

    list_display = ("id", "recipient", "event_type", "resource_type", "read_at", "created_at")
    list_filter = ("category", "event_type")
    search_fields = ("recipient__email", "resource_id")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    """Inspection only. The registration token is never shown in full and there is no
    way to create, reassign or send through a device from the admin."""

    list_display = ("id", "account", "platform", "is_active", "masked", "last_registered_at")
    list_filter = ("platform", "is_active")
    search_fields = ("account__email",)
    exclude = ("token",)

    @admin.display(description="Token")
    def masked(self, obj):
        return obj.masked_token

    def get_readonly_fields(self, request, obj=None):
        return (*(f.name for f in self.model._meta.fields if f.name != "token"), "masked")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
