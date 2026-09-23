from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import services
from .firebase import FirebaseNotConfigured, FirebaseTokenInvalid
from .serializers import (
    AccountSerializer,
    AccountUpdateSerializer,
    DetailSerializer,
    EmailVerificationConfirmSerializer,
    FirebaseExchangeResponseSerializer,
    FirebaseExchangeSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    _validate_new_password,
    issue_tokens,
)

# Enumeration-safe wording: identical whether or not the account exists.
RESET_REQUESTED_DETAIL = "If an account exists for this email, a reset link has been sent."
INVALID_LINK = "This link is invalid or has expired. Request a new one."


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "This sign-in method is not enabled."
    default_code = "firebase_not_configured"


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


@extend_schema(tags=["auth"])
class RegisterView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(
        request=RegisterSerializer,
        responses={201: RegisterResponseSerializer},
        summary="Register a new account",
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            account = serializer.save()
        payload = {"account": AccountSerializer(account).data, "tokens": issue_tokens(account)}
        return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(tags=["auth"], summary="Log in with email and password")
class LoginView(AuthThrottleMixin, TokenObtainPairView):
    pass


@extend_schema(tags=["auth"], summary="Rotate a refresh token")
class RefreshView(AuthThrottleMixin, TokenRefreshView):
    pass


@extend_schema(tags=["auth"])
class LogoutView(AuthThrottleMixin, APIView):
    """Blacklists the given refresh token. Access tokens expire naturally."""

    permission_classes = [AllowAny]
    serializer_class = LogoutSerializer

    @extend_schema(
        request=LogoutSerializer,
        responses={204: OpenApiResponse(description="Refresh token revoked.")},
        summary="Log out (revoke refresh token)",
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except TokenError as exc:
            raise ValidationError({"refresh": [str(exc)]}, code="token_invalid") from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["me"])
class MeView(generics.RetrieveUpdateAPIView):
    """Canonical source of the current user's identity, role and permissions."""

    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return AccountUpdateSerializer
        return AccountSerializer

    @extend_schema(responses={200: AccountSerializer}, summary="Current account")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=AccountUpdateSerializer,
        responses={200: AccountSerializer},
        summary="Update current account",
    )
    def patch(self, request, *args, **kwargs):
        serializer = AccountUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AccountSerializer(request.user).data)


@extend_schema(exclude=True)
class ApiNotFoundView(APIView):
    """JSON 404 for unknown /api/v1/ paths (instead of Django's HTML page)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def dispatch(self, request, *args, **kwargs):
        self.headers = self.default_response_headers
        try:
            raise NotFound("No API endpoint matches this path.")
        except NotFound as exc:
            response = self.handle_exception(exc)
        return self.finalize_response(request, response, *args, **kwargs)


# ---- password reset ---------------------------------------------------------


@extend_schema(tags=["auth"])
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={202: DetailSerializer},
        summary="Request a password-reset email",
        description="Always answers 202 with the same message, whether or not the email exists.",
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response({"detail": RESET_REQUESTED_DETAIL}, status=status.HTTP_202_ACCEPTED)


@extend_schema(tags=["auth"])
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: DetailSerializer},
        summary="Set a new password using a reset link",
        description="Revokes every refresh token of the account. Access tokens expire naturally.",
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        account = services.decode_uid(data["uid"])
        if account is None or not services.password_reset_token.check_token(account, data["token"]):
            raise ValidationError({"token": [INVALID_LINK]}, code="invalid_token")
        try:
            _validate_new_password(data["new_password"], account)
        except ValidationError as exc:
            raise ValidationError({"new_password": exc.detail}) from exc
        try:
            services.confirm_password_reset(data["uid"], data["token"], data["new_password"])
        except services.InvalidToken as exc:
            raise ValidationError({"token": [INVALID_LINK]}, code="invalid_token") from exc
        return Response({"detail": "Password updated. Please log in again."})


# ---- email verification -----------------------------------------------------


@extend_schema(tags=["auth"])
class EmailVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"
    serializer_class = None

    @extend_schema(
        request=None,
        responses={202: DetailSerializer},
        summary="Send (or resend) the email-verification link to the current account",
    )
    def post(self, request):
        try:
            services.request_email_verification(request.user)
        except services.AlreadyVerified as exc:
            raise ValidationError(
                {"non_field_errors": ["This email address is already verified."]},
                code="already_verified",
            ) from exc
        return Response({"detail": "Verification email sent."}, status=status.HTTP_202_ACCEPTED)


@extend_schema(tags=["auth"])
class EmailVerificationConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"
    serializer_class = EmailVerificationConfirmSerializer

    @extend_schema(
        request=EmailVerificationConfirmSerializer,
        responses={200: DetailSerializer},
        summary="Confirm an email address using a verification link",
    )
    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            services.confirm_email_verification(data["uid"], data["token"])
        except services.InvalidToken as exc:
            raise ValidationError({"token": [INVALID_LINK]}, code="invalid_token") from exc
        return Response({"detail": "Email address verified."})


# ---- Firebase ---------------------------------------------------------------


@extend_schema(tags=["auth"])
class FirebaseExchangeView(AuthThrottleMixin, APIView):
    """Exchange a Firebase ID token (Google, phone, ...) for Racheeta tokens."""

    permission_classes = [AllowAny]
    serializer_class = FirebaseExchangeSerializer

    @extend_schema(
        request=FirebaseExchangeSerializer,
        responses={
            200: FirebaseExchangeResponseSerializer,
            201: FirebaseExchangeResponseSerializer,
            401: OpenApiResponse(description="Firebase token invalid (firebase_token_invalid)."),
            503: OpenApiResponse(description="Firebase not enabled (firebase_not_configured)."),
        },
        summary="Exchange a Firebase ID token for Racheeta tokens",
    )
    def post(self, request):
        serializer = FirebaseExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            account, created = services.exchange_firebase_token(data["id_token"], data.get("role"))
        except FirebaseNotConfigured as exc:
            raise ServiceUnavailable() from exc
        except FirebaseTokenInvalid as exc:
            raise AuthenticationFailed(
                "Firebase token is invalid.", code="firebase_token_invalid"
            ) from exc
        except services.EmailRequired as exc:
            raise ValidationError(
                {"id_token": ["This Firebase identity has no email address."]},
                code="email_required",
            ) from exc
        except services.EmailNotVerified as exc:
            raise PermissionDenied(
                "Verify the email address with Firebase before signing in.",
                code="email_not_verified",
            ) from exc
        except services.AccountInactive as exc:
            raise AuthenticationFailed(
                "No active account found for this identity.", code="no_active_account"
            ) from exc
        payload = {
            "account": AccountSerializer(account).data,
            "tokens": issue_tokens(account),
            "created": created,
        }
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
