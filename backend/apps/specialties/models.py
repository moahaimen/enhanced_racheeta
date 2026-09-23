"""Medical specialties: database-backed, bilingual, stable slugs.

`parent` allows a shallow hierarchy (e.g. dentistry → orthodontics) without
extra machinery. Clients filter by slug or id; names are never hard-coded.
"""

from django.db import models

from apps.core.models import BaseModel


class Specialty(BaseModel):
    slug = models.SlugField(max_length=60, unique=True)
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "specialties_specialty"
        ordering = ["sort_order", "name_en"]
        verbose_name_plural = "specialties"

    def __str__(self) -> str:
        return self.name_en
