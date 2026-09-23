import pytest

from apps.accounts.roles import AccountRole
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus

pytestmark = pytest.mark.django_db

ME = "/api/v1/providers/me"
REQUEST_VERIFICATION = "/api/v1/providers/me/verification/request"


def payload(baghdad, **overrides):
    return {
        "provider_type": "DOCTOR",
        "display_name": "Dr New",
        "governorate": str(baghdad.id),
        **overrides,
    }


# ---- create ------------------------------------------------------------------


def test_provider_account_can_create_profile(
    api_client, account_factory, baghdad, baghdad_city, cardiology
):
    account = account_factory(role=AccountRole.PROVIDER)
    api_client.force_authenticate(user=account)
    response = api_client.post(
        ME,
        payload(
            baghdad,
            city=str(baghdad_city.id),
            specialty_ids=[str(cardiology.id)],
            about="Hi",
            phone="+9647700000001",
            latitude="33.3",
            longitude="44.4",
        ),
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["display_name"] == "Dr New"
    assert body["kind"] == "PRACTITIONER"
    assert body["verification_status"] == "UNVERIFIED"
    assert body["can_change_type"] is True
    assert body["governorate"]["slug"] == "baghdad"
    assert body["city"]["slug"] == "baghdad"
    assert body["specialties"][0]["slug"] == "cardiology"
    assert ProviderProfile.objects.get(account=account).is_visible is True


def test_second_profile_is_rejected(provider_client, baghdad):
    client, _ = provider_client
    response = client.post(ME, payload(baghdad))
    assert response.status_code == 400
    assert "non_field_errors" in response.json()["error"]["details"]


@pytest.mark.parametrize("role", ["PATIENT", "MEDICAL_COMPANY", "REAL_ESTATE_SELLER"])
def test_non_provider_roles_cannot_create(api_client, account_factory, baghdad, role):
    api_client.force_authenticate(user=account_factory(role=role))
    response = api_client.post(ME, payload(baghdad))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_anonymous_cannot_access_me(api_client):
    assert api_client.get(ME).status_code == 401
    assert api_client.post(ME, {}).status_code == 401


def test_get_me_without_profile_is_404(api_client, account_factory):
    api_client.force_authenticate(user=account_factory(role=AccountRole.PROVIDER))
    response = api_client.get(ME)
    assert response.status_code == 404


# ---- validation --------------------------------------------------------------


def test_create_requires_type_name_governorate(api_client, account_factory):
    api_client.force_authenticate(user=account_factory(role=AccountRole.PROVIDER))
    response = api_client.post(ME, {})
    details = response.json()["error"]["details"]
    assert {"provider_type", "display_name", "governorate"} <= set(details)


def test_invalid_provider_type_rejected(api_client, account_factory, baghdad):
    api_client.force_authenticate(user=account_factory(role=AccountRole.PROVIDER))
    response = api_client.post(ME, payload(baghdad, provider_type="WIZARD"))
    assert response.status_code == 400
    assert "provider_type" in response.json()["error"]["details"]


def test_city_must_belong_to_governorate(api_client, account_factory, basra, baghdad_city):
    api_client.force_authenticate(user=account_factory(role=AccountRole.PROVIDER))
    response = api_client.post(ME, payload(basra, city=str(baghdad_city.id)))
    assert response.status_code == 400
    assert "city" in response.json()["error"]["details"]


def test_coordinates_must_come_together_and_be_in_range(api_client, account_factory, baghdad):
    api_client.force_authenticate(user=account_factory(role=AccountRole.PROVIDER))
    assert api_client.post(ME, payload(baghdad, latitude="33.3")).status_code == 400
    assert api_client.post(ME, payload(baghdad, latitude="99", longitude="44")).status_code == 400


def test_image_url_must_be_https(api_client, account_factory, baghdad):
    api_client.force_authenticate(user=account_factory(role=AccountRole.PROVIDER))
    response = api_client.post(ME, payload(baghdad, image_url="http://x.example/a.png"))
    assert response.status_code == 400
    assert "image_url" in response.json()["error"]["details"]


# ---- update ------------------------------------------------------------------


def test_owner_can_update_allowed_fields(provider_client, basra, dentistry):
    client, profile = provider_client
    response = client.patch(
        ME,
        {
            "display_name": "Renamed",
            "governorate": str(basra.id),
            "city": None,
            "specialty_ids": [str(dentistry.id)],
            "is_visible": False,
        },
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["display_name"] == "Renamed"
    assert body["governorate"]["slug"] == "basra"
    assert body["specialties"][0]["slug"] == "dentistry"
    assert body["is_visible"] is False
    profile.refresh_from_db()
    assert profile.display_name == "Renamed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("verification_status", "VERIFIED"),
        ("verification_note", "x"),
        ("verified_at", "2026-01-01T00:00:00Z"),
        ("account", "00000000-0000-4000-8000-000000000000"),
        ("id", "00000000-0000-4000-8000-000000000000"),
    ],
)
def test_admin_fields_are_rejected_for_owner(provider_client, field, value):
    client, profile = provider_client
    profile.verification_status = VerificationStatus.PENDING
    profile.save()
    response = client.patch(ME, {"display_name": "X", field: value})
    assert response.status_code == 400
    assert field in response.json()["error"]["details"]
    profile.refresh_from_db()
    assert profile.verification_status == VerificationStatus.PENDING
    assert profile.display_name != "X"


def test_verified_provider_cannot_change_type(provider_client):
    client, profile = provider_client  # VERIFIED by fixture
    response = client.patch(ME, {"provider_type": "NURSE"})
    assert response.status_code == 400
    assert "provider_type" in response.json()["error"]["details"]
    assert client.get(ME).json()["can_change_type"] is False


def test_unverified_provider_can_change_type(api_client, provider_factory):
    profile = provider_factory(verification_status=VerificationStatus.UNVERIFIED)
    api_client.force_authenticate(user=profile.account)
    response = api_client.patch(ME, {"provider_type": "NURSE"})
    assert response.status_code == 200
    assert response.json()["provider_type"] == "NURSE"


def test_owner_cannot_edit_another_profile_via_public_id(provider_client, provider_factory):
    client, mine = provider_client
    other = provider_factory(display_name="Other")
    # The only write path is /providers/me — public ids accept no writes at all.
    response = client.patch(f"/api/v1/providers/{other.id}", {"display_name": "Hacked"})
    assert response.status_code == 405
    other.refresh_from_db()
    assert other.display_name == "Other"


# ---- verification request ----------------------------------------------------


def test_request_verification_transitions_to_pending(api_client, provider_factory):
    profile = provider_factory(verification_status=VerificationStatus.UNVERIFIED)
    api_client.force_authenticate(user=profile.account)
    response = api_client.post(REQUEST_VERIFICATION)
    assert response.status_code == 200
    assert response.json()["verification_status"] == "PENDING"
    assert response.json()["verification_requested_at"] is not None
    again = api_client.post(REQUEST_VERIFICATION)
    assert again.status_code == 400  # already pending


def test_request_verification_from_rejected_allowed_from_verified_not(api_client, provider_factory):
    rejected = provider_factory(verification_status=VerificationStatus.REJECTED)
    api_client.force_authenticate(user=rejected.account)
    assert api_client.post(REQUEST_VERIFICATION).status_code == 200
    verified = provider_factory()
    api_client.force_authenticate(user=verified.account)
    assert api_client.post(REQUEST_VERIFICATION).status_code == 400


# ---- admin -------------------------------------------------------------------


def test_admin_can_verify_and_provider_cannot(admin_client, provider_client, provider_factory):
    client, _ = provider_client
    target = provider_factory(verification_status=VerificationStatus.PENDING)
    url = f"/api/v1/admin/providers/{target.id}/verification"
    assert client.post(url, {"status": "VERIFIED"}).status_code == 403
    response = admin_client.post(url, {"status": "VERIFIED", "note": "ok"})
    assert response.status_code == 200, response.content
    target.refresh_from_db()
    assert target.verification_status == VerificationStatus.VERIFIED
    assert target.verified_at is not None
    assert target.verification_note == "ok"
    assert admin_client.post(url, {"status": "PENDING"}).status_code == 400  # not admin-settable
    assert admin_client.post(url, {"status": "SUSPENDED"}).status_code == 200


def test_admin_endpoint_requires_auth(api_client, provider_factory):
    target = provider_factory()
    assert (
        api_client.post(
            f"/api/v1/admin/providers/{target.id}/verification", {"status": "VERIFIED"}
        ).status_code
        == 401
    )
