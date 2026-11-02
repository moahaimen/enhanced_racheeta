"""Read and write serializers are deliberately separate (docs/SECURITY.md)."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.phone import IraqiPhoneField

from .models import Account
from .roles import (
    ACCOUNT_TYPE_ROLE,
    CLIENT_FORBIDDEN_FIELDS,
    SELF_REGISTRATION_ROLE_CHOICES,
    AccountRole,
    AccountType,
)


class ForbidPrivilegeFieldsMixin:
    """Reject, rather than silently ignore, any privilege field a client sends."""

    extra_forbidden: frozenset[str] = frozenset()

    def _forbidden_errors(self) -> dict:
        sent = set(getattr(self, "initial_data", {}) or {})
        forbidden = sorted(sent & (CLIENT_FORBIDDEN_FIELDS | self.extra_forbidden))
        return {
            f: [ErrorDetail("This field cannot be set by a client.", code="field_not_allowed")]
            for f in forbidden
        }

    def to_internal_value(self, data):
        # A privilege field is always reported, even when other fields are invalid too.
        forbidden = self._forbidden_errors()
        try:
            value = super().to_internal_value(data)
        except serializers.ValidationError as exc:
            if forbidden and isinstance(exc.detail, dict):
                raise serializers.ValidationError({**exc.detail, **forbidden}) from exc
            raise
        if forbidden:
            raise serializers.ValidationError(forbidden)
        return value


class AccountSerializer(serializers.ModelSerializer):
    """Read-only representation. Never includes password or privilege internals."""

    permissions = serializers.ListField(
        child=serializers.CharField(), source="capabilities", read_only=True
    )
    email_verified = serializers.BooleanField(read_only=True)
    has_password = serializers.BooleanField(source="has_usable_password", read_only=True)

    class Meta:
        model = Account
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "role",
            "account_type",
            "preferred_language",
            "email_verified",
            "email_verified_at",
            "has_password",
            "is_staff",
            "permissions",
            "created_at",
            "last_login",
        )
        read_only_fields = fields


def _clean_full_name(value: str) -> str:
    """A person's name: 2-150 characters, containing letters (not only digits or symbols)."""
    value = " ".join((value or "").split())
    if len(value) < 2 or not any(ch.isalpha() for ch in value):
        raise serializers.ValidationError("Enter your full name.", code="invalid_name")
    return value


class AccountUpdateSerializer(ForbidPrivilegeFieldsMixin, serializers.ModelSerializer):
    """Fields the account owner may change on PATCH /me."""

    phone_number = IraqiPhoneField(allow_landline=False, required=False, allow_blank=True)

    extra_forbidden = frozenset({"role", "account_type", "email", "password", "id"})

    class Meta:
        model = Account
        fields = ("full_name", "phone_number", "preferred_language")
        extra_kwargs = {
            "full_name": {"required": False},
            "phone_number": {"required": False},
            "preferred_language": {"required": False},
        }

    def validate_full_name(self, value: str) -> str:
        return _clean_full_name(value)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class RegisterSerializer(ForbidPrivilegeFieldsMixin, serializers.ModelSerializer):
    phone_number = IraqiPhoneField(allow_landline=False, required=False, allow_blank=True)

    password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, trim_whitespace=False
    )
    role = serializers.ChoiceField(
        choices=SELF_REGISTRATION_ROLE_CHOICES, default=AccountRole.PATIENT
    )
    # The onboarding choice. When given, the server derives `role` from it (ACCOUNT_TYPE_ROLE); a
    # contradicting `role` is rejected rather than silently overridden. ADMIN is never reachable.
    account_type = serializers.ChoiceField(choices=AccountType.choices, required=False)

    class Meta:
        model = Account
        fields = (
            "email",
            "password",
            "full_name",
            "phone_number",
            "role",
            "account_type",
            "preferred_language",
        )
        extra_kwargs = {
            "phone_number": {"required": False},
            "preferred_language": {"required": False},
        }

    def validate_full_name(self, value: str) -> str:
        return _clean_full_name(value)

    def validate_email(self, value: str) -> str:
        value = Account.objects.normalize_email(value)
        if Account.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists.", code="email_taken"
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        account_type = attrs.get("account_type")
        if account_type:
            derived = ACCOUNT_TYPE_ROLE[account_type]
            if "role" in self.initial_data and attrs.get("role") != derived:
                raise serializers.ValidationError(
                    {"role": "Does not match the chosen account type."}, code="role_mismatch"
                )
            attrs["role"] = derived
        candidate = Account(**{k: v for k, v in attrs.items() if k != "password"})
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return Account.objects.create_user(password=password, **validated_data)


class RegisterResponseSerializer(serializers.Serializer):
    account = AccountSerializer(read_only=True)
    tokens = TokenPairSerializer(read_only=True)


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField(read_only=True)


def _validate_new_password(password: str, account: Account | None) -> str:
    try:
        validate_password(password, user=account)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc
    return password


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=64)
    new_password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, trim_whitespace=False
    )


class EmailVerificationConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=64)


class FirebaseExchangeSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True, max_length=4096, trim_whitespace=True)
    role = serializers.ChoiceField(
        choices=SELF_REGISTRATION_ROLE_CHOICES,
        required=False,
        help_text="Role for a newly created account. Ignored for existing accounts.",
    )


class FirebaseExchangeResponseSerializer(serializers.Serializer):
    account = AccountSerializer(read_only=True)
    tokens = TokenPairSerializer(read_only=True)
    created = serializers.BooleanField(read_only=True)


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password -> access/refresh pair. Registered via SIMPLE_JWT."""


class RefreshSerializer(TokenRefreshSerializer):
    """Rotation with a defined answer for a token whose account no longer exists."""

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except Account.DoesNotExist as exc:
            # SimpleJWT looks the user up for rotation; a deleted account must
            # be an ordinary 401, never a 500.
            raise InvalidToken("Token is not valid for any account.") from exc


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)

    def save(self, **kwargs) -> None:
        RefreshToken(self.validated_data["refresh"]).blacklist()


def issue_tokens(account: Account) -> dict[str, str]:
    refresh = RefreshToken.for_user(account)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
