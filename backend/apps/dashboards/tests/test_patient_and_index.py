"""Patient dashboard and the dashboard index."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.dashboards import access
from apps.dashboards.services import reservations as reservation_services
from apps.reservations.types import ReservationStatus

from .conftest import DASH, client_for

PATIENT = f"{DASH}/patient"
INDEX = f"{DASH}/"


# --- authorization -----------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    ["", "/patient", "/doctor", "/facility", "/company", "/recruiter", "/admin"],
)
def test_every_dashboard_requires_authentication(api_client, path):
    assert api_client.get(f"{DASH}{path}" if path else INDEX).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role",
    [
        AccountRole.PROVIDER,
        AccountRole.MEDICAL_COMPANY,
        AccountRole.REAL_ESTATE_SELLER,
    ],
)
def test_only_patients_open_the_patient_dashboard(account_factory, role):
    account = account_factory(role=role)
    assert client_for(account).get(PATIENT).status_code == 403


@pytest.mark.django_db
def test_an_administrator_is_not_a_patient(admin):
    assert client_for(admin).get(PATIENT).status_code == 403


@pytest.mark.django_db
def test_dashboards_are_read_only_and_parameterless(patient):
    client = client_for(patient)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(PATIENT, {}, format="json").status_code == 405
    # A client-supplied identifier is ignored, never trusted.
    other = patient.__class__.objects.exclude(pk=patient.pk).first()
    response = client.get(PATIENT, {"patient": str(other.pk) if other else "x", "account": "x"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_responses_are_never_cacheable(patient):
    assert client_for(patient).get(PATIENT)["Cache-Control"] == "private, no-store"


# --- aggregation ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_empty_dataset_is_zero_filled_not_missing(patient):
    body = client_for(patient).get(PATIENT).json()
    assert body["reservations"] == {
        "total": 0,
        "by_status": {status: 0 for status in ReservationStatus.values},
        "upcoming": 0,
    }
    assert body["upcoming"] == [] and body["recent"] == []
    assert body["unread"] == {"notifications": 0, "messages": 0}


@pytest.mark.django_db
def test_counts_by_status_are_correct_and_scoped_to_the_patient(
    patient, account_factory, provider_factory, reservation_factory
):
    other_patient = account_factory(role=AccountRole.PATIENT)
    provider = provider_factory()
    for status, n in (
        (ReservationStatus.PENDING, 2),
        (ReservationStatus.CONFIRMED, 1),
        (ReservationStatus.COMPLETED, 3),
        (ReservationStatus.CANCELLED, 1),
        (ReservationStatus.NO_SHOW, 1),
    ):
        for _ in range(n):
            reservation_factory(patient, provider, status, starts_in=timedelta(days=-5))
    for _ in range(4):  # someone else's reservations must never be counted
        reservation_factory(other_patient, provider, ReservationStatus.CONFIRMED)

    body = client_for(patient).get(PATIENT).json()["reservations"]
    assert body["total"] == 8
    assert body["by_status"] == {
        "PENDING": 2,
        "CONFIRMED": 1,
        "COMPLETED": 3,
        "REJECTED": 0,
        "CANCELLED": 1,
        "NO_SHOW": 1,
    }
    assert body["upcoming"] == 0  # everything above started in the past


@pytest.mark.django_db
def test_upcoming_uses_status_and_the_start_time_boundary(
    patient, provider_factory, reservation_factory
):
    provider = provider_factory()
    now = timezone.now()
    live_future = reservation_factory(
        patient, provider, ReservationStatus.CONFIRMED, starts_at=now + timedelta(minutes=1)
    )
    pending_future = reservation_factory(
        patient, provider, ReservationStatus.PENDING, starts_at=now + timedelta(days=3)
    )
    reservation_factory(
        patient, provider, ReservationStatus.CONFIRMED, starts_at=now - timedelta(minutes=1)
    )  # already started
    reservation_factory(
        patient, provider, ReservationStatus.CANCELLED, starts_at=now + timedelta(days=1)
    )  # future but not live
    reservation_factory(
        patient, provider, ReservationStatus.REJECTED, starts_at=now + timedelta(days=1)
    )
    reservation_factory(
        patient, provider, ReservationStatus.COMPLETED, starts_at=now + timedelta(days=1)
    )

    summary = reservation_services.patient_summary(patient, now=now)
    assert summary["reservations"]["upcoming"] == 2
    assert [row["id"] for row in summary["upcoming"]] == [live_future.pk, pending_future.pk]


@pytest.mark.django_db
def test_upcoming_boundary_is_inclusive_at_exactly_now(
    patient, provider_factory, reservation_factory
):
    provider = provider_factory()
    now = timezone.now()
    reservation_factory(patient, provider, ReservationStatus.CONFIRMED, starts_at=now)
    assert reservation_services.patient_summary(patient, now=now)["reservations"]["upcoming"] == 1
    later = now + timedelta(microseconds=1)
    assert reservation_services.patient_summary(patient, now=later)["reservations"]["upcoming"] == 0


@pytest.mark.django_db
def test_lists_are_bounded_ordered_and_never_expose_private_fields(
    patient, provider_factory, reservation_factory
):
    provider = provider_factory()
    for i in range(9):
        reservation_factory(
            patient,
            provider,
            ReservationStatus.CONFIRMED,
            starts_in=timedelta(days=i + 1),
            patient_note="PRIVATE MEDICAL NOTE",
        )
    body = client_for(patient).get(PATIENT).json()
    assert len(body["upcoming"]) == 5 and len(body["recent"]) == 5
    starts = [row["starts_at"] for row in body["upcoming"]]
    assert starts == sorted(starts)  # soonest first
    assert body["reservations"]["total"] == 9  # the totals still count everything
    text = str(body)
    assert "PRIVATE MEDICAL NOTE" not in text and "patient_note" not in text
    assert set(body["upcoming"][0]) == {
        "id",
        "provider_name_snapshot",
        "service_title_snapshot",
        "starts_at",
        "ends_at",
        "status",
    }


@pytest.mark.django_db
def test_unread_counts_come_from_the_existing_domains(patient, account_factory):
    from apps.notifications import services as notification_services

    notification_services.notify_reservation_created(
        recipient_id=patient.pk, reservation_id=__import__("uuid").uuid4(), payload={}
    )
    body = client_for(patient).get(PATIENT).json()
    assert body["unread"]["notifications"] == 1 and body["unread"]["messages"] == 0


@pytest.mark.django_db
def test_no_fabricated_statistics_keys(patient):
    body = client_for(patient).get(PATIENT).json()
    assert set(body) == {"reservations", "upcoming", "recent", "unread"}
    forbidden = {"revenue", "spend", "earnings", "views", "impressions", "clicks", "conversion"}
    assert not (forbidden & set(str(body).lower().replace("'", " ").split()))


@pytest.mark.django_db
def test_patient_dashboard_query_count_is_constant(patient, provider_factory, reservation_factory):
    provider = provider_factory()
    client = client_for(patient)

    def count_queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(PATIENT).status_code == 200
        return len(ctx)

    baseline = count_queries()
    for i in range(30):
        reservation_factory(
            patient, provider, ReservationStatus.CONFIRMED, starts_in=timedelta(days=i + 1)
        )
    assert count_queries() == baseline  # independent of the data volume
    assert baseline <= 5  # counts + upcoming + recent + 2 unread; raise only on purpose


# --- index ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_index_lists_only_what_the_account_can_open(
    account_factory, patient, provider_factory, company_factory, seller_factory, admin
):
    assert client_for(patient).get(INDEX).json() == {"dashboards": ["patient"]}
    doctor = provider_factory()
    assert client_for(doctor.account).get(INDEX).json() == {"dashboards": ["doctor"]}
    from apps.providers.types import ProviderType

    facility = provider_factory(ProviderType.HOSPITAL)
    assert client_for(facility.account).get(INDEX).json() == {"dashboards": ["facility"]}
    company = company_factory()
    assert client_for(company.account).get(INDEX).json() == {"dashboards": ["medical_company"]}
    seller = seller_factory()
    assert client_for(seller.account).get(INDEX).json() == {"dashboards": ["real_estate_owner"]}
    assert client_for(admin).get(INDEX).json() == {"dashboards": ["admin"]}
    # No profile yet: nothing to open (the web app shows onboarding links instead).
    bare = account_factory(role=AccountRole.PROVIDER)
    assert client_for(bare).get(INDEX).json() == {"dashboards": []}


@pytest.mark.django_db
def test_index_matches_what_each_endpoint_allows(
    patient, provider_factory, company_factory, employer_factory, admin
):
    from apps.providers.types import ProviderType

    owner = employer_factory()[1]
    accounts = [
        patient,
        provider_factory().account,
        provider_factory(ProviderType.PHARMACY).account,
        company_factory().account,
        owner,
        admin,
    ]
    endpoints = {
        "patient": "/patient",
        "doctor": "/doctor",
        "facility": "/facility",
        "medical_company": "/company",
        "recruiter": "/recruiter",
        "admin": "/admin",
    }
    for account in accounts:
        client = client_for(account)
        listed = client.get(INDEX).json()["dashboards"]
        for key, path in endpoints.items():
            allowed = client.get(f"{DASH}{path}").status_code == 200
            assert allowed == (key in listed), (account.role, key)


@pytest.mark.django_db
def test_index_and_endpoints_follow_current_state_on_every_request(
    provider_factory, employer_factory, member_factory
):
    from apps.jobs.models import EmployerMembership
    from apps.jobs.types import MemberStatus

    doctor = provider_factory()
    employer, _ = employer_factory()
    member = member_factory(employer)
    # Same account as doctor profile owner AND recruiter member: both dashboards listed.
    EmployerMembership.objects.filter(account=member).update(status=MemberStatus.ENDED)
    EmployerMembership.objects.create(employer=employer, account=doctor.account, role="VIEWER")
    client = client_for(doctor.account)
    assert client.get(INDEX).json()["dashboards"] == ["doctor", "recruiter"]
    assert client.get(f"{DASH}/recruiter").status_code == 200

    # The membership ends: the very next request (same client) loses it, no stale permission.
    EmployerMembership.objects.filter(account=doctor.account).update(status=MemberStatus.ENDED)
    assert client.get(INDEX).json()["dashboards"] == ["doctor"]
    assert client.get(f"{DASH}/recruiter").status_code == 403

    doctor.delete()
    assert client.get(INDEX).json()["dashboards"] == []
    assert client.get(f"{DASH}/doctor").status_code == 403


def test_access_keys_are_unique():
    assert len(set(access.ALL)) == len(access.ALL)
