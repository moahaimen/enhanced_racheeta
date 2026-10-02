from django.contrib import admin

from .models import Conversation, ConversationParticipant, Message


class InspectionOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(InspectionOnlyAdmin):
    list_display = ("id", "context_type", "context_id", "last_sequence", "last_message_at")
    list_filter = ("context_type",)
    readonly_fields = (
        "id",
        "context_type",
        "context_id",
        "last_sequence",
        "last_message_at",
        "created_at",
        "updated_at",
    )


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(InspectionOnlyAdmin):
    list_display = ("conversation", "account", "last_read_sequence", "created_at")
    readonly_fields = (
        "id",
        "conversation",
        "account",
        "last_read_sequence",
        "created_at",
        "updated_at",
    )


@admin.register(Message)
class MessageAdmin(InspectionOnlyAdmin):
    list_display = ("conversation", "sequence", "sender", "created_at")
    readonly_fields = (
        "id",
        "conversation",
        "sender",
        "sequence",
        "body",
        "created_at",
        "updated_at",
    )
