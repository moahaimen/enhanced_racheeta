"""Cross-account and cross-organisation isolation: every caller sees only its own aggregates,
and no client-supplied identifier can change that."""

from datetime import timedelta

import pytest

from apps.accounts.roles import AccountRole
from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.jobs.types import JobStatus
from apps.providers.types import ProviderType
from apps.reservations.types import ReservationStatus

from .conftest import DASH, client_for


@pytest.mark.django_db
def test_patients_see_only_their_own_reservations(
    account_factory, provider_factory, reservation_factory
):
    a, b = (account_factory(role=AccountRole.PATIENT) for _ in range(2))
    doctor = provider_factory()
    for _ in range(3):
        reservation_factory(a, doctor, ReservationStatus.CONFIRMED)
    reservation_factory(b, doctor, ReservationStatus.PENDING)

    assert client_for(a).get(f"{DASH}/patient").json()["reservations"]["total"] == 3
    assert client_for(b).get(f"{DASH}/patient").json()["reservations"]["total"] == 1
    # Names of other patients' bookings never appear.
    assert all(
        row["status"] == "CONFIRMED"
        for row in client_for(a).get(f"{DASH}/patient").json()["upcoming"]
    )


@pytest.mark.django_db
def test_providers_see_only_their_own_reviews_offers_and_bookings(
    account_factory, provider_factory, reservation_factory, review_factory, offer_factory
):
    d1, d2 = provider_factory(), provider_factory()
    patient = account_factory(role=AccountRole.PATIENT)
    review_factory(reservation_factory(patient, d1, ReservationStatus.COMPLETED), 5)
    offer_factory(d2)
    one = client_for(d1.account).get(f"{DASH}/doctor").json()
    two = client_for(d2.account).get(f"{DASH}/doctor").json()
    assert one["reviews"]["review_count"] == 1 and two["reviews"]["review_count"] == 0
    assert one["offers"]["total"] == 0 and two["offers"]["total"] == 1
    assert one["reservations"]["total"] == 1 and two["reservations"]["total"] == 0


@pytest.mark.django_db
def test_companies_are_isolated(company_factory, product_factory, campaign_factory):
    c1, c2 = company_factory(), company_factory()
    product_factory(c1)
    campaign_factory(c2, product_factory(c2), CampaignStatus.PENDING_PAYMENT, PaymentStatus.PENDING)
    one = client_for(c1.account).get(f"{DASH}/company").json()
    two = client_for(c2.account).get(f"{DASH}/company").json()
    assert (one["products"]["total"], one["campaigns"]["total"]) == (1, 0)
    assert (two["products"]["total"], two["campaigns"]["total"]) == (1, 1)


@pytest.mark.django_db
def test_organisations_are_isolated_even_for_a_member_who_knows_the_other_ids(
    employer_factory, job_factory, application_factory, member_factory
):
    e1, owner1 = employer_factory()
    e2, owner2 = employer_factory()
    viewer1 = member_factory(e1)
    job2 = job_factory(e2, owner2, JobStatus.PUBLISHED)
    application_factory(job2, "SUBMITTED")
    job_factory(e1, owner1, JobStatus.DRAFT)

    for caller in (owner1, viewer1):
        body = (
            client_for(caller)
            .get(
                f"{DASH}/recruiter",
                {"employer": str(e2.pk), "organization": str(e2.pk), "id": str(e2.pk)},
                HTTP_X_EMPLOYER_ID=str(e2.pk),
            )
            .json()
        )
        assert body["organization"]["id"] == str(e1.pk)
        assert body["jobs"]["total"] == 1 and body["applications"]["total"] == 0
    other = client_for(owner2).get(f"{DASH}/recruiter").json()
    assert other["applications"]["total"] == 1


@pytest.mark.django_db
def test_client_supplied_ownership_hints_are_ignored_everywhere(
    patient, account_factory, provider_factory, company_factory, reservation_factory
):
    other_patient = account_factory(role=AccountRole.PATIENT)
    doctor, other_doctor = provider_factory(), provider_factory()
    reservation_factory(
        other_patient, other_doctor, ReservationStatus.CONFIRMED, starts_in=timedelta(days=1)
    )
    hints = {
        "account": str(other_patient.pk),
        "patient": str(other_patient.pk),
        "provider": str(other_doctor.pk),
        "company": "x",
        "user": str(other_patient.pk),
    }
    assert client_for(patient).get(f"{DASH}/patient", hints).json()["reservations"]["total"] == 0
    assert (
        client_for(doctor.account).get(f"{DASH}/doctor", hints).json()["reservations"]["total"] == 0
    )


@pytest.mark.django_db
def test_real_estate_owner_dashboard_reuses_the_existing_isolated_endpoint(
    seller_factory, listing_factory
):
    from apps.real_estate.types import PublicationStatus

    s1, s2 = seller_factory(), seller_factory()
    listing_factory(s1, PublicationStatus.PUBLISHED)
    listing_factory(s2, PublicationStatus.DRAFT)
    listing_factory(s2, PublicationStatus.DRAFT)
    first = client_for(s1.account).get("/api/v1/real-estate/owner/dashboard").json()
    second = client_for(s2.account).get("/api/v1/real-estate/owner/dashboard").json()
    assert (first["listings_total"], first["listings_published"]) == (1, 1)
    assert (second["listings_total"], second["listings_draft"]) == (2, 2)
    assert client_for(s1.account).get(f"{DASH}/").json() == {"dashboards": ["real_estate_owner"]}


@pytest.mark.django_db
def test_two_accounts_with_the_same_role_but_different_kinds_get_different_dashboards(
    provider_factory,
):
    doctor, hospital = provider_factory(), provider_factory(ProviderType.HOSPITAL)
    assert client_for(doctor.account).get(f"{DASH}/").json()["dashboards"] == ["doctor"]
    assert client_for(hospital.account).get(f"{DASH}/").json()["dashboards"] == ["facility"]
