"""Chat domain events. Emitted only after the message transaction commits, so a
rolled-back message never produces a downstream effect. Chat knows nothing about
who subscribes (push delivery lives in the notifications module)."""

from __future__ import annotations

from django.db import transaction
from django.dispatch import Signal

message_sent = Signal()


def emit_message_sent(message) -> None:
    message_id = message.pk
    conversation_id = message.conversation_id
    sender_id = message.sender_id
    transaction.on_commit(
        lambda: message_sent.send(
            sender=message.__class__,
            message_id=message_id,
            conversation_id=conversation_id,
            sender_id=sender_id,
        )
    )
