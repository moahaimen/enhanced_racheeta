from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.db.models import F

from apps.reservations.models import Reservation

from .models import Conversation, ConversationParticipant, Message
from .types import ConversationContextType


class ChatError(Exception):
    code = "chat_error"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


class ConversationNotFound(ChatError):
    code = "not_found"


class InvalidReadCursor(ChatError):
    code = "invalid_read_cursor"


def participant_for(account, conversation_id: UUID) -> ConversationParticipant | None:
    if not getattr(account, "is_authenticated", False):
        return None
    return (
        ConversationParticipant.objects.select_related("conversation", "account")
        .filter(account=account, conversation_id=conversation_id)
        .first()
    )


def _reservation_participant_ids(reservation: Reservation) -> tuple[UUID, UUID] | None:
    if reservation.provider_id is None or reservation.provider is None:
        return None
    return reservation.patient_id, reservation.provider.account_id


@transaction.atomic
def get_or_create_reservation_conversation(
    reservation_id: UUID, *, actor
) -> tuple[Conversation, bool]:
    """Open exactly one conversation for a reservation.

    Client input never chooses participants. The locked Reservation is the
    authority for patient/provider account ids, and the unique context
    constraint plus that lock serialise concurrent opens.
    """

    reservation = (
        Reservation.objects.select_for_update()
        .select_related("provider")
        .filter(pk=reservation_id)
        .first()
    )
    if reservation is None:
        raise ConversationNotFound("Conversation context was not found.")

    participant_ids = _reservation_participant_ids(reservation)
    if participant_ids is None or actor.pk not in participant_ids:
        raise ConversationNotFound("Conversation context was not found.")

    conversation, created = Conversation.objects.get_or_create(
        context_type=ConversationContextType.RESERVATION,
        context_id=reservation.pk,
    )
    if created:
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(conversation=conversation, account_id=account_id)
                for account_id in participant_ids
            ]
        )
    elif not ConversationParticipant.objects.filter(
        conversation=conversation, account=actor
    ).exists():
        raise ConversationNotFound("Conversation was not found.")
    return conversation, created


@transaction.atomic
def send_message(conversation_id: UUID, *, sender, body: str) -> Message:
    conversation = Conversation.objects.select_for_update().filter(pk=conversation_id).first()
    if conversation is None:
        raise ConversationNotFound("Conversation was not found.")

    participant = (
        ConversationParticipant.objects.select_for_update()
        .filter(conversation=conversation, account=sender)
        .first()
    )
    if participant is None:
        raise ConversationNotFound("Conversation was not found.")

    body = body.strip()
    if not body:
        raise ChatError("Message cannot be blank.", code="blank")
    if len(body) > 2000:
        raise ChatError("Message is too long.", code="max_length")

    sequence = conversation.last_sequence + 1
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        sequence=sequence,
        body=body,
    )
    conversation.last_sequence = sequence
    conversation.last_message_at = message.created_at
    conversation.save(update_fields=["last_sequence", "last_message_at", "updated_at"])
    return message


@transaction.atomic
def mark_read(conversation_id: UUID, *, account, through_sequence: int) -> ConversationParticipant:
    """Advance only through the highest sequence the client actually observed.

    The conversation row is locked while the cursor is validated. A message
    committed after the client loaded its page has a greater sequence and
    therefore cannot be accidentally marked read by this call.
    """

    conversation = Conversation.objects.select_for_update().filter(pk=conversation_id).first()
    if conversation is None:
        raise ConversationNotFound("Conversation was not found.")

    participant = (
        ConversationParticipant.objects.select_for_update()
        .filter(conversation=conversation, account=account)
        .first()
    )
    if participant is None:
        raise ConversationNotFound("Conversation was not found.")
    if through_sequence > conversation.last_sequence:
        raise InvalidReadCursor("Read cursor is beyond the conversation.")

    if participant.last_read_sequence < through_sequence:
        participant.last_read_sequence = through_sequence
        participant.save(update_fields=["last_read_sequence", "updated_at"])
    return participant


def unread_count(account) -> int:
    """Count other-party messages after each conversation's persisted cursor."""

    return (
        Message.objects.filter(
            conversation__participants__account=account,
            sequence__gt=F("conversation__participants__last_read_sequence"),
        )
        .exclude(sender=account)
        .count()
    )
