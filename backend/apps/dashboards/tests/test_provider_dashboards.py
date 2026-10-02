"""Doctor (practitioner) and facility dashboards."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.dashboards.services import providers as provider_services
from apps.providers.types import MembershipSide, MembershipStatus, ProviderType
from apps.reservations.types import ReservationStatus

from .conftest import DASH, client_for

DOCTOR = f"{DASH}/doctor"
FACILITY = f"{DASH}/facility"


# --- authorization -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_doctor_dashboard_is_for_practitioner_providers_only(
    patient, provider_factory, company_factory, admin
):
    doctor = provider_factory()
    nurse = provider_factory(ProviderType.NURSE)
    therapist = provider_factory(ProviderType.THERAPIST)
    facility = provider_factory(ProviderType.HOSPITAL)
    for profile in (doctor, nurse, therapist):
        assert client_for(profile.account).get(DOCTOR).status_code == 200
    assert client_for(facility.account).get(DOCTOR).status_code == 403
    assert client_for(patient).get(DOCTOR).status_code == 403
    assert client_for(company_factory().account).get(DOCTOR).status_code == 403
    assert client_for(admin).get(DOCTOR).status_code == 403


@pytest.mark.django_db
def test_facility_dashboard_is_for_facility_providers_only(patient, provider_factory):
    for kind in (
        ProviderType.HOSPITAL,
        ProviderType.MEDICAL_CENTER,
        ProviderType.PHARMACY,
        ProviderType.LABORATORY,
        ProviderType.BEAUTY_CENTER,
    ):
        assert client_for(provider_factory(kind).account).get(FACILITY).status_code == 200
    assert client_for(provider_factory().account).get(FACILITY).status_code == 403
    assert client_for(patient).get(FACILITY).status_code == 403


@pytest.mark.django_db
def test_a_provider_account_without_a_profile_has_no_dashboard(account_factory):
    bare = account_factory(role=AccountRole.PROVIDER)
    client = client_for(bare)
    assert client.get(DOCTOR).status_code == 403
    assert client.get(FACILITY).status_code == 403


# --- aggregation: reservations ------------------------------------------------------------------


@pytest.mark.django_db
def test_empty_doctor_dashboard_reports_zeros_and_null_rating(provider_factory):
    doctor = provider_factory()
    body = client_for(doctor.account).get(DOCTOR).json()
    assert body["profile"] == {
        "display_name": doctor.display_name,
        "provider_type": "DOCTOR",
        "verification_status": "VERIFIED",
        "is_visible": True,
    }
    assert body["reservations"]["total"] == 0 and body["upcoming"] == []
    assert body["reviews"] == {
        "average_rating": None,  # no reviews is "unknown", never a fabricated 0
        "review_count": 0,
        "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
    }
    assert body["offers"] == {"total": 0, "running_now": 0, "scheduled": 0}
    assert body["unread"] == {"notifications": 0, "messages": 0}
    assert "practitioners" not in body  # facility-only block


@pytest.mark.django_db
def test_reservation_counts_are_scoped_to_the_callers_own_profile(
    patient, account_factory, provider_factory, reservation_factory
):
    mine, other = provider_factory(), provider_factory()
    for status, n in (
        (ReservationStatus.PENDING, 3),
        (ReservationStatus.CONFIRMED, 2),
        (ReservationStatus.COMPLETED, 4),
        (ReservationStatus.REJECTED, 1),
        (ReservationStatus.NO_SHOW, 1),
    ):
        for _ in range(n):
            reservation_factory(patient, mine, status, starts_in=timedelta(days=-3))
    for _ in range(5):  # a different provider's bookings are invisible here
        reservation_factory(patient, other, ReservationStatus.COMPLETED)

    body = client_for(mine.account).get(DOCTOR).json()["reservations"]
    assert body["total"] == 11
    assert body["by_status"]["COMPLETED"] == 4  # "completed reservations"
    assert body["by_status"]["PENDING"] == 3
    assert body["upcoming"] == 0
    assert client_for(other.account).get(DOCTOR).json()["reservations"]["total"] == 5


@pytest.mark.django_db
def test_upcoming_appointments_show_patient_name_but_never_the_note(
    patient, provider_factory, reservation_factory
):
    doctor = provider_factory()
    reservation_factory(
        patient,
        doctor,
        ReservationStatus.CONFIRMED,
        starts_in=timedelta(hours=5),
        patient_note="SECRET DIAGNOSIS",
    )
    reservation_factory(patient, doctor, ReservationStatus.CANCELLED, starts_in=timedelta(hours=6))
    body = client_for(doctor.account).get(DOCTOR).json()
    assert [row["patient_name"] for row in body["upcoming"]] == ["Patient One"]
    assert body["reservations"]["upcoming"] == 1
    assert "SECRET DIAGNOSIS" not in str(body) and "patient_note" not in str(body)


# --- aggregation: reviews and offers ------------------------------------------------------------


@pytest.mark.django_db
def test_review_aggregates_match_the_stored_ratings(
    account_factory, provider_factory, reservation_factory, review_factory
):
    doctor, other = provider_factory(), provider_factory()
    ratings = [5, 5, 4, 2, 1]
    for rating in ratings:
        patient = account_factory(role=AccountRole.PATIENT)
        review_factory(reservation_factory(patient, doctor, ReservationStatus.COMPLETED), rating)
    review_factory(
        reservation_factory(
            account_factory(role=AccountRole.PATIENT), other, ReservationStatus.COMPLETED
        ),
        1,
    )  # a different provider's review must not move this average

    reviews = client_for(doctor.account).get(DOCTOR).json()["reviews"]
    assert reviews["review_count"] == 5
    assert reviews["average_rating"] == 3.4  # (5+5+4+2+1)/5
    assert reviews["distribution"] == {"1": 1, "2": 1, "3": 0, "4": 1, "5": 2}


@pytest.mark.django_db
def test_offer_windows_and_flags_decide_what_is_running(provider_factory, offer_factory):
    doctor = provider_factory()
    now = timezone.now()
    running = offer_factory(doctor, starts=timedelta(hours=-1), ends=timedelta(hours=1))
    offer_factory(doctor, starts=timedelta(days=1), ends=timedelta(days=2))  # scheduled
    offer_factory(doctor, starts=timedelta(days=-3), ends=timedelta(days=-1))  # ended
    offer_factory(doctor, is_active=False)  # switched off
    switched_off_service = offer_factory(doctor)
    switched_off_service.service.is_active = False
    switched_off_service.service.save(update_fields=["is_active"])

    summary = provider_services.offer_summary(doctor, now=now)
    assert summary == {"total": 5, "running_now": 1, "scheduled": 1}
    assert running.pk  # sanity: created

    # The window end is exclusive: an offer ending exactly now is no longer running.
    edge = offer_factory(doctor, starts=timedelta(hours=-2), ends=timedelta(hours=1))
    from apps.offers.models import Offer

    Offer.objects.filter(pk=edge.pk).update(ends_at=now)
    after = provider_services.offer_summary(doctor, now=now)
    assert after["running_now"] == 1  # edge excluded (ends_at > now is required)
    assert after["total"] == 6


@pytest.mark.django_db
def test_offers_of_other_providers_are_not_counted(provider_factory, offer_factory):
    mine, other = provider_factory(), provider_factory()
    offer_factory(other)
    offer_factory(other)
    assert client_for(mine.account).get(DOCTOR).json()["offers"]["total"] == 0


# --- facility -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_facility_membership_counts_only_use_real_memberships(provider_factory, membership_factory):
    facility, other_facility = (
        provider_factory(ProviderType.HOSPITAL),
        provider_factory(ProviderType.HOSPITAL),
    )
    for _ in range(2):
        membership_factory(provider_factory(), facility, MembershipStatus.ACTIVE)
    membership_factory(
        provider_factory(), facility, MembershipStatus.PENDING, MembershipSide.PRACTITIONER
    )  # waiting for the facility
    membership_factory(
        provider_factory(), facility, MembershipStatus.PENDING, MembershipSide.FACILITY
    )  # waiting for the practitioner
    membership_factory(provider_factory(), facility, MembershipStatus.REJECTED)
    membership_factory(provider_factory(), facility, MembershipStatus.ENDED)
    membership_factory(provider_factory(), other_facility, MembershipStatus.ACTIVE)

    body = client_for(facility.account).get(FACILITY).json()
    assert body["practitioners"] == {"active": 2, "incoming_requests": 1, "outgoing_invitations": 1}


@pytest.mark.django_db
def test_facility_never_aggregates_its_practitioners_reservations(
    patient, provider_factory, membership_factory, reservation_factory
):
    facility = provider_factory(ProviderType.HOSPITAL)
    practitioner = provider_factory()
    membership_factory(practitioner, facility, MembershipStatus.ACTIVE)
    for _ in range(3):
        reservation_factory(patient, practitioner, ReservationStatus.COMPLETED)
    reservation_factory(patient, facility, ReservationStatus.COMPLETED)

    body = client_for(facility.account).get(FACILITY).json()
    assert body["reservations"]["total"] == 1  # only bookings of the facility profile itself
    assert client_for(practitioner.account).get(DOCTOR).json()["reservations"]["total"] == 3


@pytest.mark.django_db
def test_a_practitioner_cannot_see_facility_data_through_a_membership(
    provider_factory, membership_factory
):
    facility = provider_factory(ProviderType.HOSPITAL)
    doctor = provider_factory()
    membership_factory(doctor, facility, MembershipStatus.ACTIVE)
    assert client_for(doctor.account).get(FACILITY).status_code == 403


# --- performance ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind,url", [(ProviderType.DOCTOR, DOCTOR), (ProviderType.HOSPITAL, FACILITY)]
)
def test_provider_dashboards_have_a_constant_query_count(
    kind,
    url,
    patient,
    provider_factory,
    reservation_factory,
    review_factory,
    offer_factory,
    membership_factory,
    account_factory,
):
    profile = provider_factory(kind)
    client = client_for(profile.account)

    def queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(url).status_code == 200
        return len(ctx)

    baseline = queries()
    for i in range(20):
        booking = reservation_factory(
            account_factory(role=AccountRole.PATIENT),
            profile,
            ReservationStatus.CONFIRMED,
            starts_in=timedelta(days=i + 1),
        )
        review_factory(booking, 1 + i % 5)
    offer_factory(profile)
    for _ in range(5):
        membership_factory(provider_factory(), profile, MembershipStatus.ACTIVE)
    assert queries() == baseline
    # doctor 7 / facility 8: profile, counts, upcoming, reviews, offers, 2 unread (+ memberships).
    assert baseline <= (8 if kind == ProviderType.HOSPITAL else 7)


@pytest.mark.django_db
def test_every_list_is_bounded(patient, provider_factory, reservation_factory):
    doctor = provider_factory()
    for i in range(12):
        reservation_factory(
            patient, doctor, ReservationStatus.PENDING, starts_in=timedelta(days=i + 1)
        )
    assert len(client_for(doctor.account).get(DOCTOR).json()["upcoming"]) == 5
