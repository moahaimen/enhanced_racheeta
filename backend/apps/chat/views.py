from collections.abc import Mapping

from django.db.models import Count, F, Prefetch, Q
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination

from . import services
from .models import ConversationParticipant, Message
from .serializers import (
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    PaginatedConversationSerializer,
    PaginatedMessageSerializer,
    ReadStateSerializer,
    UnreadCountSerializer,
)


def _require_no_body(request) -> None:
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


def _participant_queryset(account):
    other_participants = ConversationParticipant.objects.select_related("account")
    return (
        ConversationParticipant.objects.filter(account=account)
        .select_related("conversation")
        .prefetch_related(Prefetch("conversation__participants", queryset=other_participants))
        .annotate(
            unread_count=Count(
                "conversation__messages",
                filter=Q(
                    conversation__messages__sequence__gt=F("last_read_sequence")
                )
                & ~Q(conversation__messages__sender=account),
            )
        )
        .order_by(\n            F("conversation__last_message_at").desc(nulls_last=True),\n            "-conversation__created_at",\n            "-conversation__id",\n        )
    )


def _participant_or_404(account, conversation_id):
    participant = _participant_queryset(account).filter(conversation_id=conversation_id).first()
    if participant is None:
        raise Http404
    return participant


@extend_schema(tags=["chat"])
class ReservationConversationView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    @extend_schema(
        summary="Open the conversation for one of my reservations",
        request=None,
        responses={200: ConversationSerializer, 201: ConversationSerializer},
    )
    def post(self, request, reservation_id):
        _require_no_body(request)
        try:
            conversation, created = services.get_or_create_reservation_conversation(
                reservation_id, actor=request.user
            )
        except services.ConversationNotFound as exc:
            raise Http404 from exc
        participant = _participant_or_404(request.user, conversation.pk)
        return Response(
            ConversationSerializer(participant, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema(tags=["chat"])
class ConversationListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ConversationParticipant.objects.none()
        return _participant_queryset(self.request.user)

    @extend_schema(
        summary="My conversations",
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
        responses={200: PaginatedConversationSerializer},
    )
    def get(self, request):
        page = self.paginate_queryset(self.get_queryset())
        data = ConversationSerializer(page, many=True, context={"request": request}).data
        return self.get_paginated_response(data)


@extend_schema(tags=["chat"])
class ConversationMessagesView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "chat_messages"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @extend_schema(
        summary="Messages in one of my conversations",
        parameters=[
            OpenApiParameter(
                "page",
                int,
                description="Latest page is page 1; messages inside each page are chronological.",
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
        responses={200: PaginatedMessageSerializer},
    )
    def get(self, request, pk):
        participant = _participant_or_404(request.user, pk)
        queryset = Message.objects.filter(conversation=participant.conversation).select_related(
            "sender"
        ).order_by("-sequence")
        page = self.paginate_queryset(queryset)
        page = list(reversed(list(page)))
        data = MessageSerializer(page, many=True, context={"request": request}).data
        return self.get_paginated_response(data)

    @extend_schema(
        summary="Send an immutable text message",
        request=MessageCreateSerializer,
        responses={201: MessageSerializer},
    )
    def post(self, request, pk):
        _participant_or_404(request.user, pk)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = services.send_message(
                pk, sender=request.user, body=serializer.validated_data["body"]
            )
        except services.ConversationNotFound as exc:
            raise Http404 from exc
        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["chat"])
class ConversationReadView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReadStateSerializer

    @extend_schema(
        summary="Mark currently visible conversation messages as read",
        request=None,
        responses={200: ReadStateSerializer},
    )
    def post(self, request, pk):
        _require_no_body(request)
        try:
            participant = services.mark_read(pk, account=request.user)
        except services.ConversationNotFound as exc:
            raise Http404 from exc
        return Response({"last_read_sequence": participant.last_read_sequence})


@extend_schema(tags=["chat"])
class ChatUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UnreadCountSerializer

    @extend_schema(summary="My unread chat message count", responses={200: UnreadCountSerializer})
    def get(self, request):
        return Response({"count": services.unread_count(request.user)})
