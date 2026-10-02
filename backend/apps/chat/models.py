from django.conf import settings
from django.db import models

from apps.core.models import BaseModel

from .types import ConversationContextType


class Conversation(BaseModel):
    """Generic conversation shell.

    Phase 9B allows backend-owned reservation contexts only. The context fields
    deliberately avoid a GenericForeignKey: authorization is resolved by the
    chat service, not by client supplied model labels.
    """

    context_type = models.CharField(max_length=32, choices=ConversationContextType.choices)
    context_id = models.UUIDField()
    last_sequence = models.PositiveBigIntegerField(default=0, editable=False)
    last_message_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        db_table = "chat_conversation"
        ordering = ["-last_message_at", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["context_type", "context_id"],
                name="chat_conversation_context_unique",
            )
        ]
        indexes = [
            models.Index(fields=["context_type", "context_id"], name="chat_context_lookup_idx"),
            models.Index(fields=["-last_message_at"], name="chat_last_message_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.context_type}:{self.context_id}"


class ConversationParticipant(BaseModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_participations",
    )
    # Sequence cursor, not a timestamp. Mark-read locks the conversation before
    # copying last_sequence, so a concurrent later message can never be skipped.
    last_read_sequence = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = "chat_conversation_participant"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "account"],
                name="chat_participant_unique",
            )
        ]
        indexes = [
            models.Index(fields=["account", "conversation"], name="chat_participant_account_idx")
        ]

    def __str__(self) -> str:
        return f"{self.account_id} in {self.conversation_id}"


class Message(BaseModel):
    """Immutable, text-only message. There is no update/delete application API."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_chat_messages",
    )
    sequence = models.PositiveBigIntegerField(editable=False)
    body = models.TextField(max_length=2000)

    class Meta:
        db_table = "chat_message"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sequence"],
                name="chat_message_sequence_unique",
            )
        ]
        indexes = [
            models.Index(fields=["conversation", "-sequence"], name="chat_message_thread_idx")
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id} #{self.sequence}"
