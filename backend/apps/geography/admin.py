from django.contrib import admin

from .models import City, Country, Governorate


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "name_ar", "is_active")
    search_fields = ("code", "name_en", "name_ar")


@admin.register(Governorate)
class GovernorateAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "slug", "country", "sort_order", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("name_en", "name_ar", "slug")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "slug", "governorate", "sort_order", "is_active")
    list_filter = ("governorate__country", "governorate", "is_active")
    search_fields = ("name_en", "name_ar", "slug")
