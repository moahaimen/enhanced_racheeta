"""Reference geography: Country → Governorate → City.

Iraq is seeded first (migration 0002) but nothing is Iraq-specific. Clients
always use the stable UUID ids; names are bilingual.
"""

from django.db import models

from apps.core.models import BaseModel


class Country(BaseModel):
    code = models.CharField(max_length=2, unique=True, help_text="ISO 3166-1 alpha-2")
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "geography_country"
        ordering = ["name_en"]
        verbose_name_plural = "countries"

    def __str__(self) -> str:
        return self.name_en


class Governorate(BaseModel):
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="governorates")
    slug = models.SlugField(max_length=60)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "geography_governorate"
        ordering = ["sort_order", "name_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["country", "slug"], name="geography_governorate_slug_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.name_en


class City(BaseModel):
    governorate = models.ForeignKey(Governorate, on_delete=models.PROTECT, related_name="cities")
    slug = models.SlugField(max_length=60)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "geography_city"
        ordering = ["sort_order", "name_en"]
        verbose_name_plural = "cities"
        constraints = [
            models.UniqueConstraint(
                fields=["governorate", "slug"], name="geography_city_slug_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.name_en
