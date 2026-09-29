"""Phase 6 acceptance reviews (commits 84ab580, a9a20aa), ADR-045: the Django
admin provider form cannot bypass verified identity or ownership. Verification
moves only through the guarded actions (services.set_verification: VERIFIED
only from PENDING); an existing profile's account, provider type, specialties
and verification note are read-only for staff."""

import pytest
from django.conf import settings
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus

pytestmark = pytest.mark.django_db
CHANGELIST = f"/{settings.ADMIN_URL_PATH}providers/providerprofile/"


@pytest.fixture
def staff():
    client = Client()
    client.force_login(
        Account.objects.create_superuser(
            email="staff@example.com", password="Str0ng-Passw0rd!", full_name="Staff"
        )
    )
    return client


def _change_url(profile):
    return f"{CHANGELIST}{profile.pk}/change/"


def _form(profile, **overrides):
    data = {
        "account": str(profile.account_id),
        "display_name": profile.display_name,
        "about": profile.about,
        "phone": profile.phone,
        "public_email": profile.public_email,
        "website": profile.website,
        "governorate": str(profile.governorate_id),
        "address": profile.address,
        "image_url": profile.image_url,
        "verification_note": profile.verification_note,
        "is_visible": "on" if profile.is_visible else "",
        "services-TOTAL_FORMS": "0",
        "services-INITIAL_FORMS": "0",
        "services-MIN_NUM_FORMS": "0",
        "services-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v != ""}


def test_change_form_shows_status_and_identity_as_read_only(staff, provider_factory, cardiology):
    profile = provider_factory(specialties=[cardiology])
    html = staff.get(_change_url(profile)).content.decode()
    for field in (
        "verification_status",
        "verification_note",
        "account",
        "provider_type",
        "specialties",
    ):
        assert f'name="{field}"' not in html, field
    assert 'name="display_name"' in html  # ordinary fields stay editable


@pytest.mark.parametrize(
    "status",
    [VerificationStatus.UNVERIFIED, VerificationStatus.REJECTED, VerificationStatus.SUSPENDED],
)
def test_form_post_cannot_verify_a_non_pending_profile(staff, provider_factory, status):
    profile = provider_factory(verification_status=status)
    resp = staff.post(
        _change_url(profile), _form(profile, verification_status="VERIFIED", display_name="Renamed")
    )
    assert resp.status_code == 302, resp.content.decode()[:500]
    profile.refresh_from_db()
    assert profile.verification_status == status  # ignored: not a form field
    assert profile.display_name == "Renamed"  # the rest of the form still saves


@pytest.mark.parametrize("status", [VerificationStatus.PENDING, VerificationStatus.VERIFIED])
def test_form_post_cannot_change_identity(staff, provider_factory, cardiology, dentistry, status):
    profile = provider_factory(
        provider_type=ProviderType.DOCTOR, specialties=[cardiology], verification_status=status
    )
    resp = staff.post(
        _change_url(profile),
        _form(profile, provider_type=ProviderType.LABORATORY, specialties=[str(dentistry.pk)]),
    )
    assert resp.status_code == 302
    profile = ProviderProfile.objects.get(pk=profile.pk)
    assert profile.provider_type == ProviderType.DOCTOR
    assert set(profile.specialties.values_list("slug", flat=True)) == {"cardiology"}
    assert profile.verification_status == status


def _action(staff, action, *profiles):
    return staff.post(
        CHANGELIST,
        {"action": action, "_selected_action": [str(p.pk) for p in profiles]},
        follow=True,
    )


def test_mark_verified_verifies_pending_and_skips_the_rest(staff, provider_factory):
    pending = provider_factory(verification_status=VerificationStatus.PENDING)
    suspended = provider_factory(verification_status=VerificationStatus.SUSPENDED)
    resp = _action(staff, "mark_verified", pending, suspended)
    assert resp.status_code == 200
    assert "not pending review" in resp.content.decode()
    pending.refresh_from_db()
    suspended.refresh_from_db()
    assert pending.verification_status == VerificationStatus.VERIFIED
    assert suspended.verification_status == VerificationStatus.SUSPENDED


@pytest.mark.parametrize(
    "action,expected",
    [
        ("mark_rejected", VerificationStatus.REJECTED),
        ("mark_suspended", VerificationStatus.SUSPENDED),
    ],
)
def test_reject_and_suspend_actions_still_work(staff, provider_factory, action, expected):
    profile = provider_factory(verification_status=VerificationStatus.VERIFIED)
    _action(staff, action, profile)
    profile.refresh_from_db()
    assert profile.verification_status == expected


def test_form_post_cannot_transfer_a_profile_to_another_account(
    staff, provider_factory, account_factory, cardiology
):
    profile = provider_factory(specialties=[cardiology])  # VERIFIED
    owner_id = profile.account_id
    target = account_factory(role=AccountRole.PROVIDER)
    resp = staff.post(_change_url(profile), _form(profile, account=str(target.pk)))
    assert resp.status_code == 302
    profile.refresh_from_db()
    assert profile.account_id == owner_id
    assert profile.verification_status == VerificationStatus.VERIFIED
    assert not ProviderProfile.objects.filter(account=target).exists()
    client = APIClient()
    client.force_authenticate(user=Account.objects.get(pk=target.pk))
    assert client.get("/api/v1/marketplace/products").status_code == 403
