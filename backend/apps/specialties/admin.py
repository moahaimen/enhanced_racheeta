from django.contrib import admin

from .models import Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "slug", "parent", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name_en", "name_ar", "slug")
