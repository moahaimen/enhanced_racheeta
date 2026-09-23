from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    AccountSerializer,
    AccountUpdateSerializer,
    LogoutSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    issue_tokens,
)


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
