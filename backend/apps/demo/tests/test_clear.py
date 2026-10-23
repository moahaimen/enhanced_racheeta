"""clear_demo_data: removes exactly the demo data, keeps everything else, refuses if unsure."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Account
from apps.chat import services as chat_services
from apps.chat.models import Conversation
from apps.demo import cleaner
from apps.demo.content import common
from apps.demo.models import DemoRecord
from apps.demo.tests.conftest import DEMO_PASSWORD, clear, seed
from apps.geography.models import City, Governorate
from apps.jobs import services as jobs_services
from apps.jobs.models import JobApplication, JobPost, JobSeekerProfile
from apps.marketplace.models import MedicalCompany, Product, ProductCategory
from apps.notifications.models import Notification
from apps.providers.models import ProviderProfile, ServiceOffering
from apps.providers.types import VerificationStatus
from apps.real_estate.models import PropertyListing, RealEstateSeller
from apps.real_estate.types import PublicationStatus
from apps.reservations import services as reservation_services
from apps.reservations.models import AvailabilitySlot, Reservation
from apps.specialties.models import Specialty

pytestmark = pytest.mark.django_db

REFERENCE_MODELS = (Governorate, City, Specialty)


def _snapshot():
    return {m._meta.label: m.objects.count() for m in apps.get_models() if m is not DemoRecord}


def _reference_counts():
    return {m._meta.label: m.objects.count() for m in REFERENCE_MODELS}


@pytest.fixture
def real(account_factory):
    """Pre-existing, NON-demo data of every kind the cleanup could be tempted to touch."""
    baghdad = Governorate.objects.get(slug="baghdad")
    admin = Account.objects.create_superuser(
        email="owner-admin@example.com", password="Str0ng-Passw0rd!", full_name="Real Admin"
    )
    patient = account_factory(full_name="Real Patient")
    provider_account = account_factory(role="PROVIDER", full_name="Real Provider")
    profile = ProviderProfile.objects.create(
        account=provider_account,
        provider_type="DOCTOR",
        display_name="Real Provider Clinic",
        governorate=baghdad,
        verification_status=VerificationStatus.VERIFIED,
    )
    service = ServiceOffering.objects.create(
        provider=profile, title="Real consult", price=Decimal("10000"), duration_minutes=30
    )
    slot = reservation_services.create_availability_slot(
        profile, service_id=service.pk, starts_at=timezone.now() + timedelta(days=3)
    )
    reservation = reservation_services.create_reservation(patient=patient, slot_id=slot.pk)
    company_account = account_factory(role="MEDICAL_COMPANY", full_name="Real Company")
    company = MedicalCompany.objects.create(
        account=company_account, name="Real Supplies", governorate=baghdad,
        verification_status="VERIFIED",
    )  # fmt: skip
    category = ProductCategory.objects.create(slug="real-category", name_ar="حقيقي", name_en="Real")
    product = Product.objects.create(
        company=company, category=category, title="Real item", is_active=True
    )
    employer = jobs_services.create_employer(
        account_factory(role="PROVIDER"), name="Real Hospital", organization_type="HOSPITAL",
        governorate=baghdad,
    )  # fmt: skip
    job = JobPost.objects.create(
        employer=employer, created_by=employer.created_by, title="Real job", profession="NURSE",
        description="d", governorate=baghdad, employment_type="FULL_TIME", status="PUBLISHED",
        published_at=timezone.now(),
    )  # fmt: skip
    seller_account = account_factory(role="REAL_ESTATE_SELLER")
    seller = RealEstateSeller.objects.create(
        account=seller_account, seller_type="OWNER", display_name="Real Seller"
    )
    listing = PropertyListing.objects.create(
        seller=seller, title="Real clinic", property_type="CLINIC", transaction_type="RENT",
        governorate=baghdad, area_sqm=Decimal("50"), publication_status=PublicationStatus.PUBLISHED,
        published_at=timezone.now(), expires_at=timezone.now() + timedelta(days=10),
    )  # fmt: skip
    conversation, _ = chat_services.get_or_create_reservation_conversation(
        reservation.pk, actor=patient
    )
    notification = Notification.objects.create(
        recipient=patient, category="RESERVATION", event_type="RESERVATION_CREATED",
        dedupe_key="real:notification:1", payload={"status": "PENDING"},
    )  # fmt: skip
    lookalike = Account.objects.create_user(
        f"real-person@{common.EMAIL_DOMAIN}",
        password="Str0ng-Passw0rd!",
        full_name="Looks like demo",
    )
    return {
        "admin": admin, "patient": patient, "profile": profile, "reservation": reservation,
        "company": company, "product": product, "category": category, "employer": employer,
        "job": job, "listing": listing, "conversation": conversation, "lookalike": lookalike,
        "slot": slot, "notification": notification,
    }  # fmt: skip


# ---- the guarantee ----------------------------------------------------------------------------


def test_clear_removes_demo_data_and_preserves_everything_else(real):
    before_demo = _snapshot()
    reference = _reference_counts()
    seed()
    assert Account.objects.count() > before_demo["accounts.Account"]
    clear(yes=True)

    assert _snapshot() == before_demo  # every table is back to exactly its pre-demo size
    assert _reference_counts() == reference  # governorates, cities, specialties untouched
    assert DemoRecord.objects.count() == 0
    for obj in (
        real["admin"], real["patient"], real["profile"], real["reservation"], real["company"],
        real["product"], real["category"], real["employer"], real["job"], real["listing"],
        real["conversation"], real["lookalike"], real["slot"], real["notification"],
    ):  # fmt: skip
        assert type(obj).objects.filter(pk=obj.pk).exists(), obj
    assert Account.objects.filter(is_superuser=True).count() == 1


def test_an_unregistered_account_with_a_demo_looking_email_is_never_deleted(real):
    seed()
    clear(yes=True)
    survivor = Account.objects.get(pk=real["lookalike"].pk)
    assert survivor.email.endswith(common.EMAIL_DOMAIN)


def test_a_real_category_with_a_colliding_slug_is_reused_and_survives(real, db):
    ProductCategory.objects.create(
        slug="demo-consumables", name_ar="حقيقية", name_en="Real consumables"
    )
    seed()
    clear(yes=True)
    survivor = ProductCategory.objects.get(slug="demo-consumables")
    assert survivor.name_en == "Real consumables"


def test_seed_clear_seed_lifecycle(db):
    seed()
    first_registry = DemoRecord.objects.count()
    first = _snapshot()
    clear(yes=True)
    assert Account.objects.count() == 0 and DemoRecord.objects.count() == 0
    seed()
    assert DemoRecord.objects.count() == first_registry
    assert _snapshot() == first
    clear(yes=True)
    assert Account.objects.count() == 0


def test_clear_on_an_empty_registry_is_a_noop(real, capsys):
    before = _snapshot()
    clear(yes=True)
    assert _snapshot() == before
    assert "nothing" in capsys.readouterr().out.lower()


# ---- confirmation and dry run -----------------------------------------------------------------


def test_clear_needs_explicit_confirmation(seeded):
    count = Account.objects.count()
    with pytest.raises(CommandError, match="--yes"):
        clear()
    assert Account.objects.count() == count


def test_dry_run_reports_and_deletes_nothing(seeded, capsys):
    before = _snapshot()
    registry = DemoRecord.objects.count()
    clear(dry_run=True)
    assert _snapshot() == before and DemoRecord.objects.count() == registry
    out = capsys.readouterr().out
    assert "accounts.Account: 70" in out and "nothing was deleted" in out


# ---- activity among demo objects is removed too -----------------------------------------------


def test_activity_performed_as_demo_accounts_is_removed(seeded):
    patient = Account.objects.get(email=common.email("patient-hassan"))
    provider = ProviderProfile.objects.get(account__email=common.email("dr-reem-ani"))
    slot = (
        AvailabilitySlot.objects.filter(
            provider=provider, starts_at__gt=timezone.now() + timedelta(days=2)
        )
        .exclude(reservations__status__in=["PENDING", "CONFIRMED"])
        .first()
    )
    live = reservation_services.create_reservation(patient=patient, slot_id=slot.pk)
    conversation, _ = chat_services.get_or_create_reservation_conversation(live.pk, actor=patient)
    chat_services.send_message(conversation.pk, sender=patient, body="رسالة أثناء العرض")
    RefreshToken.for_user(patient)  # a login while demonstrating
    assert not DemoRecord.objects.filter(
        model_label="reservations.Reservation", object_pk=str(live.pk)
    ).exists()

    clear(yes=True)

    assert not Reservation.objects.filter(pk=live.pk).exists()
    assert not Conversation.objects.filter(pk=conversation.pk).exists()
    assert OutstandingToken.objects.count() == 0
    assert Account.objects.count() == 0 and Notification.objects.count() == 0


# ---- fail closed ------------------------------------------------------------------------------


def _assert_refused_and_unchanged(match="not demo data"):
    before = _snapshot()
    registry = DemoRecord.objects.count()
    with pytest.raises(CommandError, match=match):
        clear(yes=True)
    assert _snapshot() == before and DemoRecord.objects.count() == registry


def test_refuses_when_a_real_user_booked_a_demo_provider(seeded, real):
    provider = ProviderProfile.objects.get(account__email=common.email("dr-reem-ani"))
    slot = (
        AvailabilitySlot.objects.filter(
            provider=provider, starts_at__gt=timezone.now() + timedelta(days=2)
        )
        .exclude(reservations__status__in=["PENDING", "CONFIRMED"])
        .first()
    )
    booking = reservation_services.create_reservation(patient=real["patient"], slot_id=slot.pk)
    _assert_refused_and_unchanged()
    assert Reservation.objects.filter(pk=booking.pk, provider=provider).exists()  # untouched


def test_refuses_when_a_real_candidate_applied_to_a_demo_job(seeded, account_factory):
    seeker = JobSeekerProfile.objects.create(
        account=account_factory(), professional_title="Real nurse", profession="NURSE",
        degree="BACHELOR",
        governorate=Governorate.objects.get(slug="baghdad"),
    )  # fmt: skip
    job = JobPost.objects.filter(status="PUBLISHED").first()
    application = JobApplication.objects.create(job=job, job_seeker=seeker, snapshot={})
    _assert_refused_and_unchanged()
    assert JobApplication.objects.filter(pk=application.pk).exists()


def test_refuses_when_a_real_review_points_at_a_demo_provider(seeded, real):
    from apps.reviews.models import Review

    provider = ProviderProfile.objects.get(account__email=common.email("dr-reem-ani"))
    service = provider.services.first()
    past = Reservation.objects.create(
        patient=real["patient"], provider=provider, service=service,
        provider_name_snapshot=provider.display_name, service_title_snapshot=service.title,
        price_snapshot=service.price, currency_snapshot="IQD", duration_minutes_snapshot=30,
        starts_at=timezone.now() - timedelta(days=9),
        ends_at=timezone.now() - timedelta(days=9, minutes=-30),
        status="COMPLETED",
    )  # fmt: skip
    Review.objects.create(
        reservation=past, patient=real["patient"], provider=provider,
        provider_name_snapshot="x", service_title_snapshot="y", rating=4,
    )  # fmt: skip
    _assert_refused_and_unchanged()


def test_a_manually_deleted_demo_object_does_not_block_cleanup(seeded):
    listing = PropertyListing.objects.first()
    listing.delete()
    clear(yes=True)
    assert Account.objects.count() == 0 and DemoRecord.objects.count() == 0


def test_planner_never_roots_reference_data(seeded):
    labels = set(DemoRecord.objects.values_list("model_label", flat=True))
    reference = {m._meta.label for m in REFERENCE_MODELS}
    assert not labels & reference
    assert not labels & {"accounts.Account"} - {"accounts.Account"}
    assert cleaner.REFERENCE_LABELS >= reference | {"billing.Plan"}


def test_the_registry_records_only_rows_inserted_during_the_seed(real):
    before = {(m._meta.label, str(pk)) for m in apps.get_models() if m is not DemoRecord
              for pk in m.objects.values_list("pk", flat=True)}  # fmt: skip
    seed()
    for record in DemoRecord.objects.all():
        assert (record.model_label, record.object_pk) not in before, record
    assert DEMO_PASSWORD  # the registry holds ids only; no credential anywhere
    assert not any(
        DEMO_PASSWORD in f"{r.model_label}{r.object_pk}{r.key}" for r in DemoRecord.objects.all()
    )


def test_call_command_signature_roundtrip(db):
    call_command("seed_demo_data")
    call_command("clear_demo_data", "--yes")
    assert DemoRecord.objects.count() == 0
