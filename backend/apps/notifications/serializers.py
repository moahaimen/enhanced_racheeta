from django.utils import translation
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.chat.serializers import StrictFieldsSerializer

from . import presentation
from .models import Notification, PushDevice
from .types import NotificationCategory, NotificationEventType, PushPlatform


class NotificationSerializer(serializers.ModelSerializer):
    """Client view of a notification. Never exposes `recipient`, `dedupe_key` or the
    raw `payload`; title/body are rendered for the request language."""

    category = serializers.ChoiceField(choices=NotificationCategory.choices, read_only=True)
    event_type = serializers.ChoiceField(choices=NotificationEventType.choices, read_only=True)
    # Open-ended string on the wire: future resource kinds must not break clients.
    resource_type = serializers.CharField(read_only=True)
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


@extend_schema_serializer(component_name="PushDeviceRegister")
class PushDeviceRegisterSerializer(StrictFieldsSerializer):
    """The only client input: the opaque FCM token and a bounded platform.
    Ownership is always the authenticated caller; there is no account field."""

    token = serializers.CharField(max_length=1024, min_length=1, trim_whitespace=True)
    platform = serializers.ChoiceField(choices=PushPlatform.choices)


@extend_schema_serializer(component_name="PushDeviceUnregister")
class PushDeviceUnregisterSerializer(StrictFieldsSerializer):
    token = serializers.CharField(max_length=1024, min_length=1, trim_whitespace=True)


@extend_schema_serializer(component_name="PushDevice")
class PushDeviceSerializer(serializers.ModelSerializer):
    """Never includes the token or the owner."""

    platform = serializers.ChoiceField(choices=PushPlatform.choices, read_only=True)

    class Meta:
        model = PushDevice
        fields = ("id", "platform", "is_active", "last_registered_at")
        read_only_fields = fields
