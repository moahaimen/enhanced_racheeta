from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "target_type", "target_id", "actor", "summary")
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "summary", "actor__email")
    readonly_fields = (
        "id",
        "actor",
        "action",
        "target_type",
        "target_id",
        "summary",
        "data",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
