import uuid

import pytest
from django.contrib.admin.sites import AdminSite
from django.db import IntegrityError, transaction

from apps.notifications import services
from apps.notifications.admin import NotificationAdmin
from apps.notifications.models import Notification
from apps.notifications.types import NotificationCategory, NotificationEventType


def _make(account, **overrides):
    values = {
        "recipient": account,
        "category": NotificationCategory.RESERVATION,
        "event_type": NotificationEventType.RESERVATION_CREATED,
        "resource_type": "RESERVATION",
        "resource_id": uuid.uuid4(),
        "dedupe_key": f"k:{uuid.uuid4()}",
    }
    values.update(overrides)
    return Notification.objects.create(**values)


@pytest.mark.django_db
def test_dedupe_key_is_unique(account):
    _make(account, dedupe_key="same")
    with pytest.raises(IntegrityError), transaction.atomic():
        _make(account, dedupe_key="same")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resource_type,with_id",
    [("RESERVATION", False), ("", True)],
)
def test_resource_reference_must_be_coherent(account, resource_type, with_id):
    with pytest.raises(IntegrityError), transaction.atomic():
        _make(
            account,
            resource_type=resource_type,
            resource_id=uuid.uuid4() if with_id else None,
        )


@pytest.mark.django_db
def test_empty_resource_reference_is_allowed(account):
    _make(account, resource_type="", resource_id=None)


@pytest.mark.django_db
def test_service_create_is_idempotent_and_filters_payload(account):
    kwargs = {
        "recipient_id": account.pk,
        "category": NotificationCategory.RESERVATION,
        "event_type": NotificationEventType.RESERVATION_CREATED,
        "dedupe_key": "dup",
        "payload": {
            "service_title": "x",
            "patient_note": "secret",
            "phone": "0770",
            "email": "a@b.c",
            "token": "t",
        },
    }
    first, created_first = services.create_notification(**kwargs)
    second, created_second = services.create_notification(**kwargs)
    assert created_first and not created_second
    assert first.pk == second.pk
    assert first.payload == {"service_title": "x"}
    assert Notification.objects.count() == 1


def test_admin_is_inspection_only():
    model_admin = NotificationAdmin(Notification, AdminSite())
    readonly = set(model_admin.get_readonly_fields(None))
    assert {f.name for f in Notification._meta.fields} <= readonly
    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_change_permission(None) is False
    assert model_admin.has_delete_permission(None) is False
