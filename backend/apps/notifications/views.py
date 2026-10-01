from collections.abc import Mapping

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Notification
from .serializers import (
    MarkAllReadSerializer,
    NotificationSerializer,
    PaginatedNotificationSerializer,
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

    @extend_schema(summary="My notifications", responses={200: PaginatedNotificationSerializer})
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
