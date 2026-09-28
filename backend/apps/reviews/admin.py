from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("provider_name_snapshot", "rating", "patient", "created_at")
    list_filter = ("rating",)
    search_fields = ("provider_name_snapshot", "service_title_snapshot", "patient__email")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
