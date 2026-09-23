"""The single canonical Account model.

Every human or organisation on Racheeta authenticates through one Account.
Roles and profiles hang underneath it (docs/ARCHITECTURE.md §Accounts).
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel

from .managers import AccountManager
from .roles import AccountRole


class Account(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    class Language(models.TextChoices):
        ARABIC = "ar", "Arabic"
        ENGLISH = "en", "English"

    Role = AccountRole

    email = models.EmailField("email address", max_length=254, unique=True)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=32, blank=True, default="")
    role = models.CharField(max_length=32, choices=AccountRole.choices, default=AccountRole.PATIENT)
    preferred_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ARABIC
    )
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False, help_text="Grants access to the Django admin site."
    )

    objects = AccountManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "accounts_account"
        verbose_name = "account"
        verbose_name_plural = "accounts"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_account_email_ci_unique"),
            models.UniqueConstraint(
                fields=["phone_number"],
                condition=~Q(phone_number=""),
                name="accounts_account_phone_unique_when_set",
            ),
            models.CheckConstraint(
                condition=~Q(role=AccountRole.ADMIN) | Q(is_staff=True),
                name="accounts_account_admin_role_requires_staff",
            ),
        ]
        indexes = [models.Index(fields=["role"], name="accounts_account_role_idx")]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = AccountManager.normalize_email(self.email)

    @property
    def capabilities(self) -> list[str]:
        from .roles import capabilities_for

        return capabilities_for(self)
