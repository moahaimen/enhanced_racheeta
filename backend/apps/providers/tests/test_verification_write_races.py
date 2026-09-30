"""Phase 6 acceptance review (commit a9a20aa), ADR-045: an ordinary write that
loaded the profile before a concurrent verification decision committed — the
Django admin change form or the owner's PATCH — lands on the locked current
row with only its own fields, so it never writes back a stale verification
status, note or timestamps.

Each test commits the decision from another connection in the window between
the write loading the profile and saving it."""

import threading
from datetime import timedelta

import pytest
from django.conf import settings
from django.db import connection
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.providers import services
from apps.providers.admin import ProviderProfileAdmin
from apps.providers.models import ProviderProfile
from apps.providers.serializers import ProviderWriteSerializer
from apps.providers.types import ProviderType, VerificationStatus

pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)
CHANGELIST = f"/{settings.ADMIN_URL_PATH}providers/providerprofile/"
PROVIDER_ME = "/api/v1/providers/me"
EARLIER = timezone.now() - timedelta(days=30)


def _in_other_connection(fn):
    """Runs fn on its own connection and waits for its commit."""
    errors = []

    def run():
        try:
            fn()
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=15)
    assert not thread.is_alive() and not errors, errors


def _profile(account_factory, baghdad, status, **fields):
    return ProviderProfile.objects.create(
        account=account_factory(role=AccountRole.PROVIDER),
        provider_type=ProviderType.DOCTOR,
        display_name="Before",
        governorate=baghdad,
        verification_status=status,
        verification_requested_at=EARLIER,
        verification_changed_at=EARLIER,
        verified_at=EARLIER if status == VerificationStatus.VERIFIED else None,
        **fields,
    )


def _decide(pk, status, note):
    services.set_verification(ProviderProfile.objects.get(pk=pk), status, note, by=None)


def _admin_mark_suspended(pk):
    admin = Account.objects.get(email="racer@example.com")
    client = Client()
    client.force_login(admin)
    resp = client.post(CHANGELIST, {"action": "mark_suspended", "_selected_action": [str(pk)]})
    assert resp.status_code == 302


# ---- Django admin change form ----------------------------------------------


@pytest.mark.parametrize(
    "start,decision",
    [
        (VerificationStatus.VERIFIED, "mark_suspended"),  # the reviewed race
        (VerificationStatus.VERIFIED, VerificationStatus.REJECTED),
        (VerificationStatus.PENDING, VerificationStatus.VERIFIED),
    ],
)
def test_admin_form_save_never_undoes_a_concurrent_verification_decision(
    account_factory, baghdad, monkeypatch, start, decision
):
    profile = _profile(account_factory, baghdad, start)
    staff = Account.objects.create_superuser(
        email="racer@example.com", password="Str0ng-Passw0rd!", full_name="Staff"
    )
    original_get_object = ProviderProfileAdmin.get_object

    def get_object_then_decide(self, request, object_id, from_field=None):
        obj = original_get_object(self, request, object_id, from_field)
        if request.method == "POST":  # the form now holds the pre-decision state
            if decision == "mark_suspended":
                _in_other_connection(lambda: _admin_mark_suspended(profile.pk))
            else:
                _in_other_connection(lambda: _decide(profile.pk, decision, "Reviewed again"))
        return obj

    monkeypatch.setattr(ProviderProfileAdmin, "get_object", get_object_then_decide)
    client = Client()
    client.force_login(staff)
    resp = client.post(
        f"{CHANGELIST}{profile.pk}/change/",
        {
            "display_name": "Edited by staff",
            "governorate": str(baghdad.pk),
            "is_visible": "on",
            "services-TOTAL_FORMS": "0",
            "services-INITIAL_FORMS": "0",
            "services-MIN_NUM_FORMS": "0",
            "services-MAX_NUM_FORMS": "1000",
        },
    )
    assert resp.status_code == 302, resp.content.decode()[:500]

    final = ProviderProfile.objects.get(pk=profile.pk)
    expected = VerificationStatus.SUSPENDED if decision == "mark_suspended" else decision
    assert final.verification_status == expected
    assert final.verification_changed_at > EARLIER  # the decision's timestamp
    assert final.verification_note == ("" if decision == "mark_suspended" else "Reviewed again")
    if expected == VerificationStatus.VERIFIED:
        assert final.verified_at == final.verification_changed_at
    else:
        assert final.verified_at == EARLIER  # not rolled back or cleared
    assert final.display_name == "Edited by staff"  # the ordinary edit still lands


# ---- owner PATCH -----------------------------------------------------------


def _patch_racing(monkeypatch, profile, payload, decide):
    original_validate = ProviderWriteSerializer.validate

    def validate_then_decide(self, attrs):
        attrs = original_validate(self, attrs)
        _in_other_connection(decide)  # the view already loaded the profile
        return attrs

    monkeypatch.setattr(ProviderWriteSerializer, "validate", validate_then_decide)
    client = APIClient()
    client.force_authenticate(user=Account.objects.get(pk=profile.account_id))
    return client.patch(PROVIDER_ME, payload, format="json")


@pytest.mark.parametrize(
    "start,decision",
    [
        (VerificationStatus.PENDING, VerificationStatus.VERIFIED),  # the reviewed race
        (VerificationStatus.VERIFIED, VerificationStatus.SUSPENDED),
        (VerificationStatus.VERIFIED, VerificationStatus.REJECTED),
    ],
)
def test_owner_patch_never_overwrites_concurrent_verification_metadata(
    account_factory, baghdad, monkeypatch, start, decision
):
    profile = _profile(account_factory, baghdad, start)
    resp = _patch_racing(
        monkeypatch,
        profile,
        {"display_name": "Edited by owner", "about": "New bio"},
        lambda: _decide(profile.pk, decision, "Admin note"),
    )
    assert resp.status_code == 200, resp.json()
    assert resp.json()["verification_status"] == decision

    final = ProviderProfile.objects.get(pk=profile.pk)
    assert final.verification_status == decision
    assert final.verification_note == "Admin note"
    assert final.verification_changed_at > EARLIER
    assert final.verification_requested_at == EARLIER
    if decision == VerificationStatus.VERIFIED:
        assert final.verified_at == final.verification_changed_at
    else:
        assert final.verified_at == EARLIER
    assert (final.display_name, final.about) == ("Edited by owner", "New bio")


def test_owner_specialty_patch_is_refused_when_review_starts_concurrently(
    account_factory, baghdad, cardiology, dentistry, monkeypatch
):
    profile = _profile(account_factory, baghdad, VerificationStatus.UNVERIFIED)
    profile.specialties.set([cardiology])

    def owner_requests_review():
        services.request_verification(ProviderProfile.objects.get(pk=profile.pk))

    resp = _patch_racing(
        monkeypatch, profile, {"specialty_ids": [str(dentistry.pk)]}, owner_requests_review
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["codes"]["specialty_ids"] == ["identity_locked"]
    final = ProviderProfile.objects.get(pk=profile.pk)
    assert final.verification_status == VerificationStatus.PENDING
    assert set(final.specialties.values_list("slug", flat=True)) == {"cardiology"}
