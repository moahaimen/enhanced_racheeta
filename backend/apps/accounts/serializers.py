"""Read and write serializers are deliberately separate (docs/SECURITY.md)."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Account
from .roles import CLIENT_FORBIDDEN_FIELDS, AccountRole


class ForbidPrivilegeFieldsMixin:
    """Reject, rather than silently ignore, any privilege field a client sends."""

    extra_forbidden: frozenset[str] = frozenset()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        sent = set(getattr(self, "initial_data", {}) or {})
        forbidden = sorted(sent & (CLIENT_FORBIDDEN_FIELDS | self.extra_forbidden))
        if forbidden:
            raise serializers.ValidationError(
                {f: ["This field cannot be set by a client."] for f in forbidden},
                code="field_not_allowed",
            )
        return attrs


class AccountSerializer(serializers.ModelSerializer):
    """Read-only representation. Never includes password or privilege internals."""

    permissions = serializers.ListField(
        child=serializers.CharField(), source="capabilities", read_only=True
    )

    class Meta:
        model = Account
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "role",
            "preferred_language",
            "email_verified",
            "is_staff",
            "permissions",
            "created_at",
            "last_login",
        )
        read_only_fields = fields


class AccountUpdateSerializer(ForbidPrivilegeFieldsMixin, serializers.ModelSerializer):
    """Fields the account owner may change on PATCH /me."""

    extra_forbidden = frozenset({"role", "email", "password", "id"})

    class Meta:
        model = Account
        fields = ("full_name", "phone_number", "preferred_language")
        extra_kwargs = {
            "full_name": {"required": False},
            "phone_number": {"required": False},
            "preferred_language": {"required": False},
        }


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class RegisterSerializer(ForbidPrivilegeFieldsMixin, serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, max_length=128, trim_whitespace=False
    )
    role = serializers.ChoiceField(
        choices=[(r, AccountRole(r).label) for r in settings.RACHEETA["SELF_REGISTRATION_ROLES"]],
        default=AccountRole.PATIENT,
    )

    class Meta:
        model = Account
        fields = ("email", "password", "full_name", "phone_number", "role", "preferred_language")
        extra_kwargs = {
            "phone_number": {"required": False},
            "preferred_language": {"required": False},
        }

    def validate_email(self, value: str) -> str:
        value = Account.objects.normalize_email(value)
        if Account.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists.", code="email_taken"
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
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


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password -> access/refresh pair. Registered via SIMPLE_JWT."""


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)

    def save(self, **kwargs) -> None:
        RefreshToken(self.validated_data["refresh"]).blacklist()


def issue_tokens(account: Account) -> dict[str, str]:
    refresh = RefreshToken.for_user(account)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
