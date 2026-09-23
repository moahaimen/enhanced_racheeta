import pytest
from django.db import IntegrityError

from apps.providers.models import ProviderMembership
from apps.providers.types import MembershipStatus, ProviderType, VerificationStatus

pytestmark = pytest.mark.django_db

MEMBERSHIPS = "/api/v1/providers/me/memberships"


def _client_for(api_client, profile):
    api_client.force_authenticate(user=profile.account)
    return api_client


def test_practitioner_requests_and_facility_accepts(api_client, provider_factory):
    doctor = provider_factory(display_name="Doc")
    hospital = provider_factory(display_name="Hosp", provider_type=ProviderType.HOSPITAL)

    c = _client_for(api_client, doctor)
    created = c.post(MEMBERSHIPS, {"counterpart": str(hospital.id), "role_title": "Cardiologist"})
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["status"] == "PENDING"
    assert body["initiated_by"] == "PRACTITIONER"
    assert body["my_side"] == "PRACTITIONER"
    assert body["can_accept"] is False
    assert body["facility"]["display_name"] == "Hosp"
    mid = body["id"]

    # initiator cannot accept its own request
    assert c.post(f"{MEMBERSHIPS}/{mid}/accept").status_code == 400

    h = _client_for(api_client, hospital)
    listed = h.get(MEMBERSHIPS).json()
    assert listed[0]["my_side"] == "FACILITY" and listed[0]["can_accept"] is True
    accepted = h.post(f"{MEMBERSHIPS}/{mid}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACTIVE"
    assert accepted.json()["joined_at"]

    # end from either side
    ended = _client_for(api_client, doctor).post(f"{MEMBERSHIPS}/{mid}/end")
    assert ended.status_code == 200 and ended.json()["status"] == "ENDED"


def test_facility_invites_and_practitioner_rejects(api_client, provider_factory):
    doctor = provider_factory()
    center = provider_factory(provider_type=ProviderType.MEDICAL_CENTER)
    created = _client_for(api_client, center).post(MEMBERSHIPS, {"counterpart": str(doctor.id)})
    assert created.status_code == 201
    assert created.json()["initiated_by"] == "FACILITY"
    mid = created.json()["id"]
    rejected = _client_for(api_client, doctor).post(f"{MEMBERSHIPS}/{mid}/reject")
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    # a new request is allowed after rejection
    assert (
        _client_for(api_client, center)
        .post(MEMBERSHIPS, {"counterpart": str(doctor.id)})
        .status_code
        == 201
    )


def test_initiator_may_withdraw_pending(api_client, provider_factory):
    doctor = provider_factory()
    hospital = provider_factory(provider_type=ProviderType.HOSPITAL)
    mid = (
        _client_for(api_client, doctor)
        .post(MEMBERSHIPS, {"counterpart": str(hospital.id)})
        .json()["id"]
    )
    assert api_client.post(f"{MEMBERSHIPS}/{mid}/reject").status_code == 200


def test_duplicate_live_membership_rejected(api_client, provider_factory):
    doctor = provider_factory()
    hospital = provider_factory(provider_type=ProviderType.HOSPITAL)
    c = _client_for(api_client, doctor)
    assert c.post(MEMBERSHIPS, {"counterpart": str(hospital.id)}).status_code == 201
    dup = c.post(MEMBERSHIPS, {"counterpart": str(hospital.id)})
    assert dup.status_code == 400
    assert "counterpart" in dup.json()["error"]["details"]
    # and from the other side too
    assert (
        _client_for(api_client, hospital)
        .post(MEMBERSHIPS, {"counterpart": str(doctor.id)})
        .status_code
        == 400
    )


def test_db_constraint_blocks_duplicate_live_rows(provider_factory):
    doctor = provider_factory()
    hospital = provider_factory(provider_type=ProviderType.HOSPITAL)
    ProviderMembership.objects.create(
        practitioner=doctor, facility=hospital, initiated_by="PRACTITIONER"
    )
    with pytest.raises(IntegrityError):
        ProviderMembership.objects.create(
            practitioner=doctor,
            facility=hospital,
            initiated_by="FACILITY",
            status=MembershipStatus.ACTIVE,
        )


def test_db_constraint_blocks_self_membership(provider_factory):
    doctor = provider_factory()
    with pytest.raises(IntegrityError):
        ProviderMembership.objects.create(
            practitioner=doctor, facility=doctor, initiated_by="PRACTITIONER"
        )


@pytest.mark.parametrize(
    "a,b",
    [(ProviderType.DOCTOR, ProviderType.NURSE), (ProviderType.HOSPITAL, ProviderType.PHARMACY)],
)
def test_same_kind_cannot_link(api_client, provider_factory, a, b):
    one = provider_factory(provider_type=a)
    two = provider_factory(provider_type=b)
    response = _client_for(api_client, one).post(MEMBERSHIPS, {"counterpart": str(two.id)})
    assert response.status_code == 400
    assert "counterpart" in response.json()["error"]["details"]


def test_counterpart_must_be_discoverable(api_client, provider_factory):
    doctor = provider_factory()
    hidden = provider_factory(
        provider_type=ProviderType.HOSPITAL, verification_status=VerificationStatus.PENDING
    )
    response = _client_for(api_client, doctor).post(MEMBERSHIPS, {"counterpart": str(hidden.id)})
    assert response.status_code == 400
    assert "counterpart" in response.json()["error"]["details"]


def test_third_party_cannot_act_on_membership(api_client, provider_factory):
    doctor = provider_factory()
    hospital = provider_factory(provider_type=ProviderType.HOSPITAL)
    stranger = provider_factory(provider_type=ProviderType.PHARMACY)
    mid = (
        _client_for(api_client, doctor)
        .post(MEMBERSHIPS, {"counterpart": str(hospital.id)})
        .json()["id"]
    )
    s = _client_for(api_client, stranger)
    assert s.post(f"{MEMBERSHIPS}/{mid}/accept").status_code == 404
    assert s.post(f"{MEMBERSHIPS}/{mid}/reject").status_code == 404
    assert s.get(MEMBERSHIPS).json() == []
    assert ProviderMembership.objects.get(pk=mid).status == MembershipStatus.PENDING


def test_end_requires_active(api_client, provider_factory):
    doctor = provider_factory()
    hospital = provider_factory(provider_type=ProviderType.HOSPITAL)
    mid = (
        _client_for(api_client, doctor)
        .post(MEMBERSHIPS, {"counterpart": str(hospital.id)})
        .json()["id"]
    )
    assert api_client.post(f"{MEMBERSHIPS}/{mid}/end").status_code == 400
