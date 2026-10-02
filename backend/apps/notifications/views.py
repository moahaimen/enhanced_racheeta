from collections.abc import Mapping

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from . import push_service, services
from .models import Notification
from .serializers import (
    MarkAllReadSerializer,
    NotificationSerializer,
    PaginatedNotificationSerializer,
    PushDeviceRegisterSerializer,
    PushDeviceSerializer,
    PushDeviceUnregisterSerializer,
    UnreadCountSerializer,
)


def _require_no_body(request) -> None:
    """Read actions take NO client data. Allowed: no body, or an empty JSON object /
    empty form. Anything else (any key, any non-object JSON body) is refused with
    `field_not_allowed` — Mapping semantics, not truthiness."""
    data = request.data
    if isinstance(data, Mapping):
        if len(data) == 0:
            return
        keys = list(data.keys())
    else:
        keys = ["non_field_errors"]
    raise ValidationError(
        {
            key: [ErrorDetail("This field cannot be set by a client.", code="field_not_allowed")]
            for key in keys
        },
        code="field_not_allowed",
    )


@extend_schema(tags=["notifications"])
class NotificationListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(recipient=self.request.user).order_by(
            "-created_at", "-id"
        )

    @extend_schema(
        summary="My notifications",
        # Published explicitly because this generic view paginates by hand; the values
        # come from the pagination class so the contract cannot drift from runtime.
        parameters=[
            OpenApiParameter(
                "page",
                int,
                description=f"Page number ({StandardPagination.page_size} per page by default).",
            ),
            OpenApiParameter(
                "page_size",
                int,
                description=(
                    f"Page size (default {StandardPagination.page_size}, "
                    f"maximum {StandardPagination.max_page_size})."
                ),
            ),
        ],
        responses={200: PaginatedNotificationSerializer},
    )
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        serializer = NotificationSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


@extend_schema(tags=["notifications"])
class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UnreadCountSerializer

    @extend_schema(summary="My unread notification count", responses={200: UnreadCountSerializer})
    def get(self, request):
        return Response({"count": services.unread_count(request.user)})


@extend_schema(tags=["notifications"])
class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    @extend_schema(
        summary="Mark one of my notifications as read",
        request=None,
        responses={200: NotificationSerializer},
    )
    def post(self, request, pk):
        _require_no_body(request)
        notification = services.mark_read(request.user, pk)
        if notification is None:
            raise Http404
        return Response(NotificationSerializer(notification, context={"request": request}).data)


@extend_schema(tags=["notifications"])
class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MarkAllReadSerializer

    @extend_schema(
        summary="Mark all my notifications as read",
        request=None,
        responses={200: MarkAllReadSerializer},
    )
    def post(self, request):
        _require_no_body(request)
        return Response({"updated": services.mark_all_read(request.user)})


@extend_schema(tags=["notifications"])
class PushDeviceRegisterView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PushDeviceRegisterSerializer
    throttle_scope = "push_devices"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    @extend_schema(
        summary="Register or refresh this device's push token",
        description=(
            "Idempotent upsert owned by the authenticated caller. If the token was registered "
            "by another account it is transferred to the caller and the previous owner stops "
            "receiving pushes through it. The token is never returned."
        ),
        request=PushDeviceRegisterSerializer,
        responses={200: PushDeviceSerializer},
    )
    def post(self, request):
        serializer = PushDeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = push_service.register_device(
            request.user,
            token=serializer.validated_data["token"],
            platform=serializer.validated_data["platform"],
        )
        return Response(PushDeviceSerializer(device).data)


@extend_schema(tags=["notifications"])
class PushDeviceUnregisterView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PushDeviceUnregisterSerializer
    throttle_scope = "push_devices"

    def get_throttles(self):
        return [ScopedRateThrottle()]

    @extend_schema(
        summary="Unregister this device's push token (call before logout)",
        description=(
            "Deactivates the caller's own registration of this token. Tokens that are unknown "
            "or owned by someone else change nothing and are answered identically (204)."
        ),
        request=PushDeviceUnregisterSerializer,
        responses={204: None},
    )
    def post(self, request):
        serializer = PushDeviceUnregisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        push_service.unregister_device(request.user, token=serializer.validated_data["token"])
        return Response(status=status.HTTP_204_NO_CONTENT)
