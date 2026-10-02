from collections.abc import Mapping

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from .models import ConversationParticipant, Message
from .types import ConversationContextType


class StrictFieldsSerializer(serializers.Serializer):
    """Reject undeclared client fields instead of silently ignoring them."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {
                        key: [
                            ErrorDetail(
                                "This field cannot be set by a client.",
                                code="field_not_allowed",
                            )
                        ]
                        for key in sorted(unknown)
                    }
                )
        return super().to_internal_value(data)


class ChatAccountSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)


class ConversationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="conversation.id", read_only=True)
    context_type = serializers.ChoiceField(
        source="conversation.context_type",
        choices=ConversationContextType.choices,
        read_only=True,
    )
    context_id = serializers.UUIDField(source="conversation.context_id", read_only=True)
    last_sequence = serializers.IntegerField(source="conversation.last_sequence", read_only=True)
    last_message_at = serializers.DateTimeField(
        source="conversation.last_message_at", allow_null=True, read_only=True
    )
    created_at = serializers.DateTimeField(source="conversation.created_at", read_only=True)
    other_participant = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ConversationParticipant
        fields = (
            "id",
            "context_type",
            "context_id",
            "other_participant",
            "last_sequence",
            "last_read_sequence",
            "unread_count",
            "last_message_at",
            "created_at",
        )
        read_only_fields = fields

    def get_other_participant(self, obj: ConversationParticipant):
        request = self.context.get("request")
        account_id = getattr(getattr(request, "user", None), "pk", None)
        for participant in obj.conversation.participants.all():
            if participant.account_id != account_id:
                return ChatAccountSerializer(participant.account).data
        return None

    def get_unread_count(self, obj: ConversationParticipant) -> int:
        annotated = getattr(obj, "unread_count", None)
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        account = getattr(request, "user", None)
        if account is None:
            return 0
        return (
            obj.conversation.messages.filter(sequence__gt=obj.last_read_sequence)
            .exclude(sender=account)
            .count()
        )


class MessageSerializer(serializers.ModelSerializer):
    sender = ChatAccountSerializer(read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ("id", "sequence", "sender", "is_mine", "body", "created_at")
        read_only_fields = fields

    def get_is_mine(self, obj: Message) -> bool:
        request = self.context.get("request")
        return obj.sender_id == getattr(getattr(request, "user", None), "pk", None)


class MessageCreateSerializer(StrictFieldsSerializer):
    body = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class ReadRequestSerializer(StrictFieldsSerializer):
    through_sequence = serializers.IntegerField(min_value=0)


class ReadStateSerializer(serializers.Serializer):
    last_read_sequence = serializers.IntegerField()


class PaginatedConversationSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ConversationSerializer(many=True)


class PaginatedMessageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = MessageSerializer(many=True)
