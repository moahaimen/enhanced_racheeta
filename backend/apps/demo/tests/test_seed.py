"""seed_demo_data: guards, completeness, valid relationships, idempotency, no leaked secrets."""

import pytest
from django.apps import apps
from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.chat.models import Conversation, Message
from apps.demo.content import common
from apps.demo.models import DemoRecord
from apps.demo.tests.conftest import DEMO_PASSWORD, seed
from apps.jobs.models import Employer, JobApplication, JobPost
from apps.marketplace.models import MedicalCompany, Product
from apps.notifications.models import Notification
from apps.offers.models import Offer
from apps.providers.models import ProviderProfile
from apps.real_estate.models import PropertyListing
from apps.reservations.models import AvailabilitySlot, Reservation
from apps.reservations.types import ReservationStatus
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def _counts():
    return {m._meta.label: m.objects.count() for m in apps.get_models()}


# ---- guards -----------------------------------------------------------------------------------


def test_refuses_without_the_staging_switch(monkeypatch):
    monkeypatch.delenv("DEMO_DATA_ENABLED")
    with pytest.raises(CommandError, match="DEMO_DATA_ENABLED"):
        seed()
    monkeypatch.setenv("DEMO_DATA_ENABLED", "false")
    with pytest.raises(CommandError, match="DEMO_DATA_ENABLED"):
        seed()
    assert not Account.objects.filter(email__endswith=common.EMAIL_DOMAIN).exists()


def test_requires_a_real_password_and_never_hardcodes_one(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD")
    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        seed()
    monkeypatch.setenv("DEMO_PASSWORD", "short")
    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        seed()
    assert DemoRecord.objects.count() == 0


def test_generate_password_prints_it_once_and_it_works(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_PASSWORD")
    seed(generate_password=True)
    out = capsys.readouterr().out
    line = next(item for item in out.splitlines() if "Shared demo password" in item)
    generated = line.rsplit(": ", 1)[1].strip().replace("\x1b[0m", "").replace("\x1b[33;1m", "")
    account = Account.objects.get(email=common.email("patient-sara"))
    assert check_password(generated, account.password)


def test_password_is_never_printed_when_taken_from_the_environment(capsys):
    seed()
    assert DEMO_PASSWORD not in capsys.readouterr().out


def test_dry_run_writes_nothing(capsys):
    before = _counts()
    seed(dry_run=True)
    assert _counts() == before
    out = capsys.readouterr().out
    assert "dry-run" in out and "Marketplace products" in out


# ---- completeness and validity ---------------------------------------------------------------


def test_seed_creates_every_major_entity_type(seeded):
    assert ProviderProfile.objects.count() == 36  # 27 practitioners + 9 facilities
    assert (
        ProviderProfile.objects.filter(
            provider_type__in=["HOSPITAL", "MEDICAL_CENTER", "LABORATORY", "PHARMACY"]
        ).count()
        == 9
    )
    assert MedicalCompany.objects.count() == 13
    assert Product.objects.count() == 49
    assert JobPost.objects.filter(status="PUBLISHED").count() >= 15
    assert Employer.objects.count() == 10
    assert PropertyListing.objects.count() == 19
    assert AvailabilitySlot.objects.count() > 100
    assert Reservation.objects.count() > 50
    assert Review.objects.count() > 40
    assert Offer.objects.count() == 5
    assert Notification.objects.count() > 20
    assert Conversation.objects.count() == 5 and Message.objects.count() >= 15
    assert JobApplication.objects.count() >= 15


def test_accounts_are_all_fictional_and_log_in_with_the_chosen_password(seeded):
    emails = Account.objects.values_list("email", flat=True)
    assert all(e.endswith("@" + common.EMAIL_DOMAIN) for e in emails)
    assert not Account.objects.filter(is_staff=True).exists()  # the seeder never creates admins
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login", {"email": common.email("patient-sara"), "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200 and "access" in response.json()
    roles = set(Account.objects.values_list("role", flat=True))
    assert roles == {"PATIENT", "PROVIDER", "MEDICAL_COMPANY", "REAL_ESTATE_SELLER"}


def test_everything_is_publicly_visible_where_the_product_says_it_should_be(seeded):
    client = APIClient()
    assert client.get("/api/v1/providers").json()["count"] == 36
    assert client.get("/api/v1/jobs").json()["count"] >= 15
    assert client.get("/api/v1/real-estate/listings").json()["count"] == 19
    for employer in Employer.objects.all():
        assert employer.is_public
    for provider in ProviderProfile.objects.all():
        assert provider.is_discoverable
    for company in MedicalCompany.objects.all():
        assert company.can_publish


def test_marketplace_products_are_visible_to_demo_providers(seeded):
    client = APIClient()
    client.force_authenticate(Account.objects.get(email=common.email("dr-karim-saadi")))
    assert client.get("/api/v1/marketplace/products").json()["count"] > 10
    pharmacy = Account.objects.get(email=common.email("amal-pharmacy"))
    client.force_authenticate(pharmacy)
    assert client.get("/api/v1/marketplace/products").json()["count"] > 10


def test_relationships_are_valid_and_ownership_is_consistent(seeded):
    for reservation in Reservation.objects.select_related("provider", "patient"):
        assert reservation.patient.role == "PATIENT"
        assert reservation.provider is not None
        assert reservation.ends_at > reservation.starts_at
    for review in Review.objects.select_related("reservation"):
        assert review.reservation.status == ReservationStatus.COMPLETED
        assert review.reservation.patient_id == review.patient_id
    for product in Product.objects.select_related("company__account"):
        assert product.company.account.role == "MEDICAL_COMPANY"
    for job in JobPost.objects.select_related("employer"):
        assert job.employer.created_by_id is not None
        if job.city_id:
            assert job.city.governorate_id == job.governorate_id
    for conversation in Conversation.objects.all():
        assert conversation.participants.count() == 2


def test_ratings_vary_and_reviews_back_the_dashboard_numbers(seeded):
    client = APIClient()
    karim = Account.objects.get(email=common.email("dr-karim-saadi"))
    client.force_authenticate(karim)
    body = client.get("/api/v1/dashboards/doctor").json()
    assert body["reviews"]["review_count"] == 4
    assert 4.0 <= body["reviews"]["average_rating"] <= 5.0
    ratings = set(Review.objects.values_list("rating", flat=True))
    assert {3, 4, 5} <= ratings
    patient = Account.objects.get(email=common.email("patient-sara"))
    client.force_authenticate(patient)
    dashboard = client.get("/api/v1/dashboards/patient").json()
    assert dashboard["reservations"]["total"] == Reservation.objects.filter(patient=patient).count()


def test_notifications_include_read_and_unread_and_only_existing_types(seeded):
    from apps.notifications.types import NotificationEventType

    assert Notification.objects.filter(read_at__isnull=True).exists()
    assert Notification.objects.filter(read_at__isnull=False).exists()
    assert set(Notification.objects.values_list("event_type", flat=True)) <= set(
        NotificationEventType.values
    )


def test_reservation_statuses_are_ones_the_platform_implements(seeded):
    seen = set(Reservation.objects.values_list("status", flat=True))
    assert {"COMPLETED", "CONFIRMED", "CANCELLED", "PENDING"} <= seen
    assert seen <= set(ReservationStatus.values)


def test_slots_are_in_the_future_and_bookable(seeded):
    from django.utils import timezone

    assert AvailabilitySlot.objects.filter(starts_at__gt=timezone.now()).count() > 100
    client = APIClient()
    provider = ProviderProfile.objects.get(account__email=common.email("dr-dalia-tamimi"))
    response = client.get(f"/api/v1/providers/{provider.pk}/availability")
    assert response.status_code == 200


# ---- idempotency -----------------------------------------------------------------------------


def test_second_run_creates_nothing(seeded):
    first = _counts()
    registry = DemoRecord.objects.count()
    call_command("seed_demo_data")
    assert _counts() == first
    assert DemoRecord.objects.count() == registry


# ---- portraits ----------------------------------------------------------------------------------

PRACTITIONER_TYPES = ("DOCTOR", "NURSE", "THERAPIST")


def test_every_demo_practitioner_gets_a_shipped_portrait_and_facilities_none(seeded, settings):
    from pathlib import Path

    from apps.demo.content import providers as content

    public = Path(__file__).resolve().parents[4] / "web" / "public"
    origin = settings.RACHEETA["FRONTEND_URL"]
    assert set(content.PORTRAITS) == {row[0] for row in content.PRACTITIONERS}
    practitioners = ProviderProfile.objects.filter(provider_type__in=PRACTITIONER_TYPES)
    assert practitioners.count() == len(content.PRACTITIONERS)
    for profile in practitioners:
        assert profile.image_url.startswith(f"{origin}{content.PORTRAIT_PATH}")
        assert (public / profile.image_url.removeprefix(origin).lstrip("/")).is_file()
    facilities = ProviderProfile.objects.exclude(provider_type__in=PRACTITIONER_TYPES)
    assert facilities.exists() and not facilities.exclude(image_url="").exists()


def test_a_rerun_adds_missing_portraits_but_never_replaces_a_set_image(seeded):
    practitioners = ProviderProfile.objects.filter(provider_type__in=PRACTITIONER_TYPES)
    practitioners.update(image_url="")
    custom = practitioners.first()
    custom.image_url = "https://images.example.test/own-photo.webp"
    custom.save(update_fields=["image_url"])
    registry = DemoRecord.objects.count()
    seed()
    assert DemoRecord.objects.count() == registry  # updates only, nothing new created
    assert not practitioners.filter(image_url="").exists()
    custom.refresh_from_db()
    assert custom.image_url == "https://images.example.test/own-photo.webp"
