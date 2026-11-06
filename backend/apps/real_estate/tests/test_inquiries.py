"""Phase E: property inquiries end to end (seeker → owner → answer / close / withdraw).

Covers scoping (BOLA), the public-visibility gate, duplicates, the daily cap and the throttle,
the status lifecycle, contact privacy, notifications (no message or contact in the payload),
audit history, and that unpublishing or expiry hides the listing immediately while the inquiry
history stays readable."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit.models import AuditEvent
from apps.notifications.models import Notification
from apps.real_estate.models import ListingInquiry
from apps.real_estate.types import MAX_INQUIRIES_PER_DAY, InquiryStatus

from .conftest import PUBLIC_LISTINGS, client_for

pytestmark = pytest.mark.django_db

MINE = "/api/v1/real-estate/inquiries/mine"
OWNER_INQ = "/api/v1/real-estate/owner/inquiries"
MESSAGE = "Is the clinic still available from next month?"


def _ask(client, listing, message=MESSAGE, **extra):
    return client.post(
        f"{PUBLIC_LISTINGS}/{listing.pk}/inquiries", {"message": message, **extra}, format="json"
    )


@pytest.fixture
def seeker(account_factory):
    return account_factory(role=AccountRole.PROVIDER, phone_number="07701234567")


def test_seeker_asks_owner_answers_seeker_reads(
    published, seeker, django_capture_on_commit_callbacks
):
    listing = published()
    owner = listing.seller.account
    with django_capture_on_commit_callbacks(execute=True):
        created = _ask(client_for(seeker), listing)
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["status"] == "OPEN" and body["listing_is_public"] is True
    assert body["listing_title_snapshot"] == listing.title

    inbox = client_for(owner).get(OWNER_INQ).json()["results"]
    assert [row["id"] for row in inbox] == [body["id"]]
    # Contact details stay private unless the seeker opted in.
    assert inbox[0]["inquirer"] == {"full_name": seeker.full_name, "email": "", "phone_number": ""}

    with django_capture_on_commit_callbacks(execute=True):
        answered = client_for(owner).post(
            f"{OWNER_INQ}/{body['id']}/respond", {"response": "Yes, from the 1st."}
        )
    assert answered.status_code == 200 and answered.json()["status"] == "ANSWERED"
    mine = client_for(seeker).get(MINE).json()["results"]
    assert mine[0]["owner_response"] == "Yes, from the 1st." and mine[0]["status"] == "ANSWERED"

    # Notifications: owner on receipt, seeker on answer; never the message or contact details.
    received = Notification.objects.get(recipient=owner, event_type="INQUIRY_RECEIVED")
    answered_note = Notification.objects.get(recipient=seeker, event_type="INQUIRY_ANSWERED")
    for note in (received, answered_note):
        assert note.category == "INQUIRY" and note.resource_type == "INQUIRY"
        assert set(note.payload) <= {"listing_title", "status"}
        assert MESSAGE not in str(note.payload)


def test_contact_shared_only_when_the_seeker_opts_in(published, seeker):
    listing = published()
    _ask(client_for(seeker), listing, share_contact=True)
    row = client_for(listing.seller.account).get(OWNER_INQ).json()["results"][0]
    assert row["inquirer"]["email"] == seeker.email
    assert row["inquirer"]["phone_number"] == "07701234567"


@pytest.mark.parametrize(
    "state",
    ["draft", "expired", "seller_inactive"],
)
def test_only_a_public_listing_accepts_an_inquiry(listing_factory, published, seeker, state):
    if state == "draft":
        listing = listing_factory()
    elif state == "expired":
        listing = published(expires_at=timezone.now() - timedelta(minutes=1))
    else:
        listing = published()
        listing.seller.account.is_active = False
        listing.seller.account.save(update_fields=["is_active"])
    response = _ask(client_for(seeker), listing)
    assert response.status_code == 404
    assert not ListingInquiry.objects.exists()


def test_anonymous_cannot_inquire(api_client, published):
    assert _ask(api_client, published()).status_code in (401, 403)


def test_owner_cannot_inquire_about_own_listing(published):
    listing = published()
    response = _ask(client_for(listing.seller.account), listing)
    assert response.status_code == 403 and response.json()["error"]["code"] == "own_listing"


def test_one_live_inquiry_per_listing_then_a_new_one_after_closing(published, seeker):
    listing = published()
    client = client_for(seeker)
    first = _ask(client, listing).json()
    duplicate = _ask(client, listing)
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "duplicate_inquiry"
    assert client.post(f"{MINE}/{first['id']}/withdraw").json()["status"] == "WITHDRAWN"
    assert _ask(client, listing).status_code == 201


def test_daily_cap(published, seeker):
    client = client_for(seeker)
    for _ in range(MAX_INQUIRIES_PER_DAY):
        assert _ask(client, published()).status_code == 201
    capped = _ask(client, published())
    assert capped.status_code == 429 and capped.json()["error"]["code"] == "inquiry_limit_reached"


def test_sending_is_throttled(published, seeker, settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "real_estate_inquiries": "2/hour",
        },
    }
    from rest_framework.throttling import ScopedRateThrottle

    cache.clear()
    ScopedRateThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    try:
        client = client_for(seeker)
        assert _ask(client, published()).status_code == 201
        assert _ask(client, published()).status_code == 201
        assert _ask(client, published()).status_code == 429
        assert client.get(MINE).status_code == 200  # reading never spends the quota
    finally:
        from rest_framework.settings import api_settings

        ScopedRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES


def test_message_is_validated(published, seeker):
    assert _ask(client_for(seeker), published(), message="hi").status_code == 400
    assert _ask(client_for(seeker), published(), message="x" * 1001).status_code == 400


def test_scoping_other_owners_and_other_seekers_get_404(
    published, seeker, seller_factory, account_factory
):
    listing = published()
    inquiry = _ask(client_for(seeker), listing).json()
    other_owner = seller_factory().account
    other_seeker = account_factory(role=AccountRole.PATIENT)
    assert client_for(other_owner).get(OWNER_INQ).json()["results"] == []
    for path in ("respond", "close"):
        refused = client_for(other_owner).post(
            f"{OWNER_INQ}/{inquiry['id']}/{path}", {"response": "no"}
        )
        assert refused.status_code == 404
    assert client_for(other_seeker).get(MINE).json()["results"] == []
    assert client_for(other_seeker).post(f"{MINE}/{inquiry['id']}/withdraw").status_code == 404
    # A non-seller account cannot open the owner inbox at all.
    assert client_for(seeker).get(OWNER_INQ).status_code == 403


def test_lifecycle_final_states(published, seeker):
    listing = published()
    owner = client_for(listing.seller.account)
    inquiry = _ask(client_for(seeker), listing).json()
    assert owner.post(f"{OWNER_INQ}/{inquiry['id']}/close").json()["status"] == "CLOSED"
    again = owner.post(f"{OWNER_INQ}/{inquiry['id']}/respond", {"response": "late"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_transition"
    assert client_for(seeker).post(f"{MINE}/{inquiry['id']}/withdraw").status_code == 400


def test_unpublishing_hides_the_listing_at_once_but_keeps_the_history(published, seeker):
    listing = published()
    owner = client_for(listing.seller.account)
    inquiry = _ask(client_for(seeker), listing).json()
    assert (
        owner.post(f"/api/v1/real-estate/owner/listings/{listing.pk}/unpublish").status_code == 200
    )
    assert client_for(seeker).get(f"{PUBLIC_LISTINGS}/{listing.pk}").status_code == 404
    mine = client_for(seeker).get(MINE).json()["results"][0]
    assert mine["id"] == inquiry["id"] and mine["listing_is_public"] is False
    assert "contact_phone" not in mine and "price" not in mine  # nothing of the listing leaks
    # No new inquiry while it is not public; the owner can still answer the existing one.
    assert _ask(client_for(seeker), listing).status_code == 404
    reply = owner.post(f"{OWNER_INQ}/{inquiry['id']}/respond", {"response": "Rented, sorry."})
    assert reply.status_code == 200


def test_expiry_hides_the_listing_immediately(published, seeker):
    listing = published()
    _ask(client_for(seeker), listing)
    listing.expires_at = timezone.now() - timedelta(seconds=1)
    listing.save(update_fields=["expires_at"])
    assert client_for(seeker).get(f"{PUBLIC_LISTINGS}/{listing.pk}").status_code == 404
    assert client_for(seeker).get(MINE).json()["results"][0]["listing_is_public"] is False


def test_every_change_is_audited(published, seeker):
    listing = published()
    owner = client_for(listing.seller.account)
    inquiry = _ask(client_for(seeker), listing).json()
    owner.post(f"{OWNER_INQ}/{inquiry['id']}/respond", {"response": "Yes."})
    owner.post(f"{OWNER_INQ}/{inquiry['id']}/close")
    actions = list(
        AuditEvent.objects.filter(target_id=str(inquiry["id"]))
        .order_by("created_at")
        .values_list("action", flat=True)
    )
    assert actions == [
        "real_estate.inquiry.created",
        "real_estate.inquiry.answered",
        "real_estate.inquiry.closed",
    ]


def test_owner_filters_by_status_and_listing(published, seeker, account_factory):
    listing_a = published()
    listing_b = published(seller=listing_a.seller)
    first = _ask(client_for(seeker), listing_a).json()
    _ask(client_for(account_factory(role=AccountRole.PATIENT)), listing_b)
    owner = client_for(listing_a.seller.account)
    owner.post(f"{OWNER_INQ}/{first['id']}/respond", {"response": "Yes."})
    by_status = owner.get(OWNER_INQ, {"status": InquiryStatus.ANSWERED}).json()["results"]
    assert [r["id"] for r in by_status] == [first["id"]]
    by_listing = owner.get(OWNER_INQ, {"listing": str(listing_b.pk)}).json()["results"]
    assert len(by_listing) == 1 and by_listing[0]["listing_id"] == str(listing_b.pk)
    assert owner.get(OWNER_INQ, {"listing": "not-a-uuid"}).json()["results"] == []
