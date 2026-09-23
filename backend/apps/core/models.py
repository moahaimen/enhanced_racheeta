"""Abstract base models shared by every Racheeta module."""

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Adds immutable `created_at` and auto-updated `updated_at`."""

    created_at = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """UUID primary key. Public identifiers are never guessable integers."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """Default base for domain entities: UUID id + timestamps."""

    class Meta:
        abstract = True
