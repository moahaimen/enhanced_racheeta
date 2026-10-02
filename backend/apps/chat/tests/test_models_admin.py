import uuid

import pytest
from django.contrib import admin
from django.db import IntegrityError, transaction
from django.test import RequestFactory

from apps.chat.models import Conversation, ConversationParticipant, Message
from apps.chat.types import ConversationContextType


@pytest.mark.django_db
def test_one_conversation_per_context(account_factory):
    context_id = uuid.uuid4()
    Conversation.objects.create(
        context_type=ConversationContextType.RESERVATION,
        context_id=context_id,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Conversation.objects.create(
            context_type=ConversationContextType.RESERVATION,
            context_id=context_id,
        )


@pytest.mark.django_db
def test_message_sequence_is_unique_per_conversation(account_factory):
    sender = account_factory()
    conversation = Conversation.objects.create(
        context_type=ConversationContextType.RESERVATION,
        context_id=uuid.uuid4(),
    )
    ConversationParticipant.objects.create(conversation=conversation, account=sender)
    Message.objects.create(conversation=conversation, sender=sender, sequence=1, body="a")
    with pytest.raises(IntegrityError), transaction.atomic():
        Message.objects.create(
            conversation=conversation,
            sender=sender,
            sequence=1,
            body="b",
        )


@pytest.mark.django_db
def test_chat_admin_is_inspection_only(account_factory):
    staff = account_factory(is_staff=True)
    request = RequestFactory().get("/admin/")
    request.user = staff
    for model in (Conversation, ConversationParticipant, Message):
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is False
        assert model_admin.has_delete_permission(request) is False
