from django.db import models


class ConversationContextType(models.TextChoices):
    RESERVATION = "RESERVATION", "Reservation"
