"""Race safety, proven with real second connections (Phase 6 style): the service
decides on locked, CURRENT rows, never on what the request loaded."""

import threading

import pytest
from django.db import connection, transaction
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.real_estate import services, views
from apps.real_estate.models import ListingSuitableUse, PropertyListing, RealEstateSeller
from apps.real_estate.types import PublicationStatus

from .conftest import OWNER_LISTINGS, PUBLIC_LISTINGS

pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def _in_thread(fn):
    """Runs fn on its own connection; returns (thread, outcome dict)."""
    outcome: dict = {}

    def run():
        try:
            outcome["result"] = fn()
        except Exception as exc:  # noqa: BLE001 - reported to the test
            outcome["error"] = exc
        finally:
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    return thread, outcome


def test_publishing_with_a_stale_seller_role_fails_and_leaves_the_draft(
    listing_factory, monkeypatch
):
    """The view loaded the seller while it was REAL_ESTATE_SELLER; another
    connection then changes the role; the service must decide on the current row."""
    listing = listing_factory()
    account_id = listing.seller.account_id
    original = views._own_seller

    def own_seller_then_role_changes(request):
        snapshot = original(request)  # role REAL_ESTATE_SELLER, in memory
        thread, outcome = _in_thread(
            lambda: Account.objects.filter(pk=account_id).update(role=AccountRole.PATIENT)
        )
        thread.join(timeout=10)
        assert not thread.is_alive() and "error" not in outcome
        assert (
            snapshot.account.role == AccountRole.REAL_ESTATE_SELLER
        )  # stale, as a request holds it
        return snapshot

    monkeypatch.setattr(views, "_own_seller", own_seller_then_role_changes)
    client = APIClient()
    client.force_authenticate(user=Account.objects.get(pk=account_id))  # still a seller here
    resp = client.post(f"{OWNER_LISTINGS}/{listing.pk}/publish")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "seller_not_eligible"
    listing.refresh_from_db()
    assert listing.publication_status == PublicationStatus.DRAFT and listing.published_at is None
    assert APIClient().get(PUBLIC_LISTINGS).json()["count"] == 0


def test_editing_a_published_listing_with_a_stale_seller_role_is_refused(published, monkeypatch):
    listing = published()
    account_id = listing.seller.account_id
    original = views._own_seller

    def own_seller_then_role_changes(request):
        snapshot = original(request)
        thread, _ = _in_thread(
            lambda: Account.objects.filter(pk=account_id).update(role=AccountRole.PROVIDER)
        )
        thread.join(timeout=10)
        return snapshot

    monkeypatch.setattr(views, "_own_seller", own_seller_then_role_changes)
    client = APIClient()
    client.force_authenticate(user=Account.objects.get(pk=account_id))
    resp = client.patch(f"{OWNER_LISTINGS}/{listing.pk}", {"title": "Sneaky"}, format="json")
    assert resp.status_code == 403
    listing.refresh_from_db()
    assert listing.title != "Sneaky"


@pytest.mark.parametrize(
    "operation",
    [
        lambda listing: services.update_listing(listing.seller, listing.pk, {}, []),
        lambda listing: services.update_listing(listing.seller, listing.pk, {}, ["CLINIC"]),
        lambda listing: services.publish_listing(listing.seller, listing.pk),
    ],
    ids=["replace-uses-empty", "replace-uses", "publish"],
)
def test_child_writes_and_publication_wait_for_the_listing_lock(listing_factory, operation):
    """While another transaction holds the parent listing's row lock, use
    replacement and publication must block — they take that lock first — and
    complete once it is released."""
    listing = listing_factory()
    seller = RealEstateSeller.objects.get(pk=listing.seller_id)
    holder_has_lock = threading.Event()
    release = threading.Event()

    def hold_lock():
        with transaction.atomic():
            PropertyListing.objects.select_for_update().get(pk=listing.pk)
            holder_has_lock.set()
            assert release.wait(timeout=15)

    holder, holder_outcome = _in_thread(hold_lock)
    assert holder_has_lock.wait(timeout=10)
    listing.seller = seller
    worker, outcome = _in_thread(lambda: operation(listing))
    worker.join(timeout=0.7)
    assert worker.is_alive(), "the write did not wait for the listing lock"
    release.set()
    worker.join(timeout=15)
    holder.join(timeout=15)
    assert not worker.is_alive() and "error" not in outcome, outcome
    assert "error" not in holder_outcome


def test_publication_racing_use_removal_never_leaves_a_published_listing_without_uses(
    listing_factory,
):
    """Whichever wins the listing lock, the end state respects the gate."""
    listing = listing_factory(uses=("CLINIC",))
    seller = RealEstateSeller.objects.get(pk=listing.seller_id)
    barrier = threading.Barrier(2)

    def publish():
        barrier.wait(timeout=10)
        return services.publish_listing(seller, listing.pk)

    def clear_uses():
        barrier.wait(timeout=10)
        return services.update_listing(seller, listing.pk, {}, [])

    t1, o1 = _in_thread(publish)
    t2, o2 = _in_thread(clear_uses)
    t1.join(timeout=20)
    t2.join(timeout=20)
    assert not t1.is_alive() and not t2.is_alive()
    for outcome in (o1, o2):
        if "error" in outcome:
            assert isinstance(outcome["error"], services.ListingProblems), outcome["error"]
    final = PropertyListing.objects.get(pk=listing.pk)
    uses = ListingSuitableUse.objects.filter(listing=final).count()
    if final.publication_status == PublicationStatus.PUBLISHED:
        assert uses >= 1
    else:
        assert final.published_at is None


def test_publication_reads_the_suitable_uses_committed_under_the_listing_lock(listing_factory):
    """A transaction holding the listing lock removes every use but has not
    committed yet. A concurrent publish must wait for that lock and then decide
    on what was committed — no uses — instead of on the uses it could see
    before the lock (which would publish an unsuitable listing)."""
    listing = listing_factory(uses=("CLINIC",))
    seller = RealEstateSeller.objects.get(pk=listing.seller_id)
    holder_has_lock = threading.Event()
    release = threading.Event()

    def remove_uses_then_commit():
        with transaction.atomic():
            PropertyListing.objects.select_for_update().get(pk=listing.pk)
            ListingSuitableUse.objects.filter(listing_id=listing.pk).delete()
            holder_has_lock.set()
            assert release.wait(timeout=15)

    holder, holder_outcome = _in_thread(remove_uses_then_commit)
    assert holder_has_lock.wait(timeout=10)
    worker, outcome = _in_thread(lambda: services.publish_listing(seller, listing.pk))
    worker.join(timeout=0.7)
    assert worker.is_alive(), "publish did not wait for the listing lock"
    release.set()
    worker.join(timeout=15)
    holder.join(timeout=15)
    assert "error" not in holder_outcome
    error = outcome.get("error")
    assert isinstance(error, services.ListingProblems), outcome
    assert error.problems["suitable_uses"] == "suitable_use_required"
    final = PropertyListing.objects.get(pk=listing.pk)
    assert final.publication_status == PublicationStatus.DRAFT


# ---- every ordinary seller mutation re-checks the CURRENT account state -------------------------


def _role_changes_elsewhere(account_id, role=AccountRole.PATIENT):
    """Another connection changes the role and commits; returns when it is done."""
    thread, outcome = _in_thread(lambda: Account.objects.filter(pk=account_id).update(role=role))
    thread.join(timeout=10)
    assert not thread.is_alive() and "error" not in outcome, outcome


def _stale_seller(seller_pk):
    """The seller as a request loaded it: role REAL_ESTATE_SELLER, in memory."""
    seller = RealEstateSeller.objects.select_related("account").get(pk=seller_pk)
    assert seller.account.role == AccountRole.REAL_ESTATE_SELLER
    return seller


def test_seller_profile_update_with_a_stale_role_fails_and_changes_nothing(seller_factory):
    seller = seller_factory(display_name="Original", about="Bio")
    stale = _stale_seller(seller.pk)
    _role_changes_elsewhere(seller.account_id)
    assert stale.account.role == AccountRole.REAL_ESTATE_SELLER  # what the request still believes
    with pytest.raises(services.SellerNotEligible):
        services.update_seller(stale, {"display_name": "Hijacked", "about": "New"})
    fresh = RealEstateSeller.objects.get(pk=seller.pk)
    assert (fresh.display_name, fresh.about) == ("Original", "Bio")


def test_draft_creation_with_a_stale_role_fails_and_creates_nothing(seller_factory, baghdad):
    seller = seller_factory()
    stale = _stale_seller(seller.pk)
    _role_changes_elsewhere(seller.account_id)
    with pytest.raises(services.SellerNotEligible):
        services.create_listing(
            stale,
            {
                "title": "Ghost",
                "property_type": "CLINIC",
                "transaction_type": "RENT",
                "governorate": baghdad,
            },
        )
    assert not PropertyListing.objects.filter(seller_id=seller.pk).exists()


def test_draft_edit_with_a_stale_role_fails_and_leaves_the_draft_unchanged(listing_factory):
    listing = listing_factory(title="Original title", uses=("CLINIC",))
    stale = _stale_seller(listing.seller_id)
    _role_changes_elsewhere(listing.seller.account_id, AccountRole.PROVIDER)
    with pytest.raises(services.SellerNotEligible):
        services.update_listing(
            stale, listing.pk, {"title": "Hijacked", "district": "Elsewhere"}, ["PHARMACY"]
        )
    fresh = PropertyListing.objects.get(pk=listing.pk)
    assert (fresh.title, fresh.district) == ("Original title", "Karrada")
    assert list(fresh.suitable_uses.values_list("use", flat=True)) == ["CLINIC"]


def test_http_draft_creation_with_a_stale_role_is_refused(seller_factory, baghdad, monkeypatch):
    seller = seller_factory()
    account_id = seller.account_id
    original = views._own_seller

    def own_seller_then_role_changes(request):
        snapshot = original(request)
        _role_changes_elsewhere(account_id)
        return snapshot

    monkeypatch.setattr(views, "_own_seller", own_seller_then_role_changes)
    client = APIClient()
    client.force_authenticate(user=Account.objects.get(pk=account_id))
    resp = client.post(
        OWNER_LISTINGS,
        {
            "title": "Ghost",
            "property_type": "CLINIC",
            "transaction_type": "RENT",
            "governorate": str(baghdad.pk),
        },
        format="json",
    )
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "seller_not_eligible"
    assert not PropertyListing.objects.filter(seller_id=seller.pk).exists()


def test_unpublish_stays_possible_for_a_stale_role_at_the_service_level(published):
    listing = published()
    stale = _stale_seller(listing.seller_id)
    _role_changes_elsewhere(listing.seller.account_id)
    services.unpublish_listing(stale, listing.pk)  # withdrawal only reduces exposure
    assert PropertyListing.objects.get(pk=listing.pk).publication_status == PublicationStatus.DRAFT
