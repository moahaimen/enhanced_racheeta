from django.utils import translation
from rest_framework import serializers

from . import presentation
from .models import Notification
from .types import NotificationCategory, NotificationEventType


class NotificationSerializer(serializers.ModelSerializer):
    """Client view of a notification. Never exposes `recipient`, `dedupe_key` or the
    raw `payload`; title/body are rendered for the request language."""

    category = serializers.ChoiceField(choices=NotificationCategory.choices, read_only=True)
    event_type = serializers.ChoiceField(choices=NotificationEventType.choices, read_only=True)
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "category",
            "event_type",
            "title",
            "body",
            "resource_type",
            "resource_id",
            "is_read",
            "read_at",
            "created_at",
        )
        read_only_fields = fields

    def _language(self) -> str:
        request = self.context.get("request")
        return getattr(request, "LANGUAGE_CODE", None) or translation.get_language()

    def get_title(self, obj: Notification) -> str:
        return presentation.render(obj.event_type, obj.payload, self._language())[0]

    def get_body(self, obj: Notification) -> str:
        return presentation.render(obj.event_type, obj.payload, self._language())[1]

    def get_is_read(self, obj: Notification) -> bool:
        return obj.read_at is not None


class PaginatedNotificationSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = NotificationSerializer(many=True)


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class MarkAllReadSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
