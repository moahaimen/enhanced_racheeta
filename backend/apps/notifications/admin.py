from django.contrib import admin

from .models import Notification


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
