from django.contrib.auth.base_user import BaseUserManager

from .roles import AccountRole


class AccountManager(BaseUserManager):
    """Email is the canonical identifier. There is no username."""

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        # Lower-case the whole address. Case-sensitive local parts are
        # legal per RFC 5321 but unsupported by every real provider, and a
        # single canonical form is what makes the DB uniqueness constraint
        # meaningful.
        return (email or "").strip().lower()

    def get_by_natural_key(self, username: str | None):
        # Used by ModelBackend on login: look up the canonical (lower-case) form.
        return self.get(**{self.model.USERNAME_FIELD: self.normalize_email(username)})

    def _create(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        account = self.model(email=self.normalize_email(email), **extra_fields)
        if password:
            account.set_password(password)
        else:
            # Firebase/social accounts never get a fake password.
            account.set_unusable_password()
        account.full_clean(exclude=["password"])
        account.save(using=self._db)
        return account

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("role", AccountRole.PATIENT)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        if extra_fields["is_staff"] or extra_fields["is_superuser"]:
            raise ValueError("create_user cannot grant staff or superuser flags.")
        if extra_fields["role"] == AccountRole.ADMIN:
            raise ValueError("create_user cannot create ADMIN accounts.")
        return self._create(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields["role"] = AccountRole.ADMIN
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields.setdefault("is_active", True)
        if not password:
            raise ValueError("Superusers must have a password.")
        return self._create(email, password, **extra_fields)
