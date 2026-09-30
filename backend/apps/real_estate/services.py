"""Real-estate services: every state change is decided on locked, current rows,
raises typed errors and is audited. Views never derive ownership or lifecycle
from client input.

Lock order everywhere: RealEstateSeller (with its account) -> PropertyListing ->
suitable-use rows. Suitable uses are only ever written while the parent listing
is locked, so publication and use replacement cannot interleave.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.geography.models import City, Governorate

from .models import ListingSuitableUse, PropertyListing, RealEstateSeller
from .types import (
    EMAIL_METHODS,
    PHONE_METHODS,
    ContactMethod,
    PropertyType,
    PublicationStatus,
    SellerType,
    SuitableUse,
    TransactionType,
)


class RealEstateError(Exception):
    code = "real_estate_error"


class AlreadyExists(RealEstateError):
    code = "already_exists"


class SellerNotEligible(RealEstateError):
    code = "seller_not_eligible"


class ListingNotFound(RealEstateError):
    code = "not_found"


class InvalidTransition(RealEstateError):
    code = "invalid_transition"


class ListingProblems(RealEstateError):
    """Field-level problems (`{field: typed code}`) with a listing's state.
    Raised for invalid structure on any write and for a failed publication gate;
    the API renders both as a validation error with per-field codes."""

    code = "validation_error"

    def __init__(self, problems: dict[str, str]):
        super().__init__("; ".join(f"{field}: {code}" for field, code in problems.items()))
        self.problems = problems


PROBLEM_MESSAGES = {
    "title_required": "A title is required.",
    "invalid_choice": "This value is not allowed.",
    "geography_inactive": "This governorate is no longer available.",
    "city_inactive": "This city is no longer available.",
    "city_mismatch": "This city does not belong to the selected governorate.",
    "area_required": "The area must be given and greater than zero.",
    "area_invalid": "The area must be greater than zero.",
    "coordinates_invalid": "Latitude and longitude must be given together and in range.",
    "suitable_use_required": "Choose at least one suitable medical use.",
    "contact_phone_required": "A contact phone is required for this contact method.",
    "contact_email_required": "A contact email is required for this contact method.",
    "contact_email_invalid": "Enter a valid contact email.",
    "expiry_required": "An expiration date is required.",
    "expiry_in_past": "The expiration date must be in the future.",
    "price_invalid": "The price must be zero or more.",
    "currency_unsupported": "Unsupported currency.",
}

SELLER_FIELDS = ("seller_type", "display_name", "about", "phone", "public_email")
LISTING_FIELDS = (
    "title",
    "description",
    "property_type",
    "transaction_type",
    "governorate",
    "city",
    "district",
    "latitude",
    "longitude",
    "area_sqm",
    "price",
    "currency",
    "facilities",
    "contact_method",
    "contact_phone",
    "contact_email",
    "expires_at",
)

_email = EmailValidator()


def _lock_seller(seller: RealEstateSeller) -> RealEstateSeller:
    """Seller row and its account, read fresh under lock: the role and active
    flag are decided here, never from the request's snapshot."""
    return RealEstateSeller.objects.select_for_update().select_related("account").get(pk=seller.pk)


def _require_eligible(seller: RealEstateSeller) -> None:
    if not seller.is_eligible:
        raise SellerNotEligible(
            "Your account must be an active real-estate seller account to do this."
        )


def _lock_listing(seller: RealEstateSeller, listing_id) -> PropertyListing:
    listing = (
        PropertyListing.objects.select_for_update(of=("self",))
        .filter(pk=listing_id, seller=seller)
        .first()
    )
    if listing is None:
        raise ListingNotFound("Listing not found.")
    return listing


def _coordinates_problem(listing: PropertyListing) -> bool:
    lat, lng = listing.latitude, listing.longitude
    if (lat is None) != (lng is None):
        return True
    if lat is None:
        return False
    return not (Decimal(-90) <= lat <= Decimal(90) and Decimal(-180) <= lng <= Decimal(180))


def structural_problems(listing: PropertyListing) -> dict[str, str]:
    """What must hold for ANY stored listing, draft included."""
    problems: dict[str, str] = {}
    if listing.property_type not in PropertyType.values:
        problems["property_type"] = "invalid_choice"
    if listing.transaction_type not in TransactionType.values:
        problems["transaction_type"] = "invalid_choice"
    if listing.contact_method not in ContactMethod.values:
        problems["contact_method"] = "invalid_choice"
    if listing.currency not in settings.RACHEETA["CURRENCIES"]:
        problems["currency"] = "currency_unsupported"
    if listing.price is not None and listing.price < 0:
        problems["price"] = "price_invalid"
    if listing.area_sqm is not None and listing.area_sqm <= 0:
        problems["area_sqm"] = "area_invalid"
    if _coordinates_problem(listing):
        problems["latitude"] = "coordinates_invalid"
    if listing.contact_email:
        try:
            _email(listing.contact_email)
        except DjangoValidationError:
            problems["contact_email"] = "contact_email_invalid"
    if listing.city_id is not None:
        governorate_id = (
            City.objects.filter(pk=listing.city_id).values_list("governorate_id", flat=True).first()
        )
        if governorate_id != listing.governorate_id:
            problems["city"] = "city_mismatch"
    return problems


def publication_problems(
    listing: PropertyListing, use_codes: list[str], now=None
) -> dict[str, str]:
    """THE publication gate (structure plus everything a public listing needs),
    evaluated on the resulting state — used to publish and to accept any edit of
    a PUBLISHED listing. The seller's eligibility is checked separately
    (SellerNotEligible) on the locked seller/account."""
    now = now or timezone.now()
    problems = structural_problems(listing)
    if not listing.title.strip():
        problems["title"] = "title_required"
    if not Governorate.objects.filter(pk=listing.governorate_id, is_active=True).exists():
        problems["governorate"] = "geography_inactive"
    if listing.city_id is not None and "city" not in problems:
        if not City.objects.filter(pk=listing.city_id, is_active=True).exists():
            problems["city"] = "city_inactive"
    if listing.area_sqm is None:
        problems["area_sqm"] = "area_required"
    if not use_codes:
        problems["suitable_uses"] = "suitable_use_required"
    if listing.contact_method in PHONE_METHODS and not listing.contact_phone.strip():
        problems["contact_phone"] = "contact_phone_required"
    if listing.contact_method in EMAIL_METHODS and not listing.contact_email.strip():
        problems["contact_email"] = "contact_email_required"
    if listing.expires_at is None:
        problems["expires_at"] = "expiry_required"
    elif listing.expires_at <= now:
        problems["expires_at"] = "expiry_in_past"
    return problems


def _replace_suitable_uses(listing: PropertyListing, codes: list[str]) -> None:
    """Caller holds the listing lock."""
    wanted = set(codes)
    ListingSuitableUse.objects.filter(listing=listing).exclude(use__in=wanted).delete()
    have = set(ListingSuitableUse.objects.filter(listing=listing).values_list("use", flat=True))
    ListingSuitableUse.objects.bulk_create(
        [ListingSuitableUse(listing=listing, use=use) for use in sorted(wanted - have)]
    )


def _current_use_codes(listing: PropertyListing) -> list[str]:
    return list(ListingSuitableUse.objects.filter(listing=listing).values_list("use", flat=True))


def _validated_use_codes(codes) -> list[str]:
    if any(code not in SuitableUse.values for code in codes):
        raise ListingProblems({"suitable_uses": "invalid_choice"})
    if len(set(codes)) != len(codes):
        raise ListingProblems({"suitable_uses": "duplicate_suitable_use"})
    return list(codes)


# ---- seller --------------------------------------------------------------------------------


@transaction.atomic
def create_seller(account, fields: dict) -> RealEstateSeller:
    locked_account = Account.objects.select_for_update().get(pk=account.pk)
    if not locked_account.is_active or locked_account.role != AccountRole.REAL_ESTATE_SELLER:
        raise SellerNotEligible("Only active real-estate seller accounts can create a profile.")
    seller = RealEstateSeller(
        account=locked_account, **{k: v for k, v in fields.items() if k in SELLER_FIELDS}
    )
    if seller.seller_type not in SellerType.values:
        raise ListingProblems({"seller_type": "invalid_choice"})
    try:
        with transaction.atomic():
            seller.save()
    except IntegrityError as exc:  # one profile per account (OneToOne)
        if "real_estate_seller" not in str(exc):
            raise
        raise AlreadyExists("You already have a seller profile.") from exc
    audit.record(
        actor=locked_account,
        action="real_estate.seller.created",
        target=seller,
        summary=seller.display_name,
    )
    return seller


@transaction.atomic
def update_seller(seller: RealEstateSeller, fields: dict) -> RealEstateSeller:
    locked = _lock_seller(seller)
    changed = [k for k in fields if k in SELLER_FIELDS]
    for key in changed:
        setattr(locked, key, fields[key])
    if locked.seller_type not in SellerType.values:
        raise ListingProblems({"seller_type": "invalid_choice"})
    if changed:
        locked.save(update_fields=[*changed, "updated_at"])
    audit.record(
        actor=locked.account,
        action="real_estate.seller.updated",
        target=locked,
        summary=locked.display_name,
        data={"fields": sorted(changed)},
    )
    return locked


# ---- listings ------------------------------------------------------------------------------


@transaction.atomic
def create_listing(
    seller: RealEstateSeller, fields: dict, suitable_uses: list[str] | None = None
) -> PropertyListing:
    """Creates a DRAFT (possibly incomplete); publication is a separate action."""
    locked_seller = _lock_seller(seller)
    values = {k: v for k, v in fields.items() if k in LISTING_FIELDS}
    listing = PropertyListing(seller=locked_seller, **values)
    codes = _validated_use_codes(suitable_uses or [])
    problems = structural_problems(listing)
    if problems:
        raise ListingProblems(problems)
    listing.save()
    _replace_suitable_uses(listing, codes)
    audit.record(
        actor=locked_seller.account,
        action="real_estate.listing.created",
        target=listing,
        summary=listing.title,
        data={"transaction_type": listing.transaction_type, "property_type": listing.property_type},
    )
    return listing


@transaction.atomic
def update_listing(
    seller: RealEstateSeller, listing_id, changes: dict, suitable_uses: list[str] | None = None
) -> PropertyListing:
    """Owner edit on locked, current rows. Only the sent fields are written
    (never lifecycle state). An edit that leaves the listing PUBLISHED re-runs
    the whole publication gate on the resulting state, since it changes live
    public data."""
    locked_seller = _lock_seller(seller)
    listing = _lock_listing(locked_seller, listing_id)
    changed = [k for k in changes if k in LISTING_FIELDS]
    for key in changed:
        setattr(listing, key, changes[key])
    codes = _validated_use_codes(suitable_uses) if suitable_uses is not None else None
    problems = structural_problems(listing)
    if problems:
        raise ListingProblems(problems)
    if listing.publication_status == PublicationStatus.PUBLISHED:
        _require_eligible(locked_seller)
        problems = publication_problems(
            listing, codes if codes is not None else _current_use_codes(listing)
        )
        if problems:
            raise ListingProblems(problems)
    if changed:
        listing.save(update_fields=[*changed, "updated_at"])
    if codes is not None:
        _replace_suitable_uses(listing, codes)
    audit.record(
        actor=locked_seller.account,
        action="real_estate.listing.updated",
        target=listing,
        summary=listing.title,
        data={
            "fields": sorted([*changed, *(["suitable_uses"] if codes is not None else [])]),
            "publication_status": listing.publication_status,
        },
    )
    return listing


@transaction.atomic
def publish_listing(seller: RealEstateSeller, listing_id) -> PropertyListing:
    locked_seller = _lock_seller(seller)
    _require_eligible(locked_seller)  # the CURRENT role/active flag, not the request's
    listing = _lock_listing(locked_seller, listing_id)
    if listing.publication_status == PublicationStatus.PUBLISHED:
        raise InvalidTransition("This listing is already published.")
    problems = publication_problems(listing, _current_use_codes(listing))
    if problems:
        raise ListingProblems(problems)
    listing.publication_status = PublicationStatus.PUBLISHED
    listing.published_at = timezone.now()  # server-owned
    listing.save(update_fields=["publication_status", "published_at", "updated_at"])
    audit.record(
        actor=locked_seller.account,
        action="real_estate.listing.published",
        target=listing,
        summary=listing.title,
        data={"expires_at": listing.expires_at.isoformat()},
    )
    return listing


@transaction.atomic
def unpublish_listing(seller: RealEstateSeller, listing_id) -> PropertyListing:
    """Always possible (the owner can always withdraw), whatever the account's state."""
    locked_seller = _lock_seller(seller)
    listing = _lock_listing(locked_seller, listing_id)
    if listing.publication_status != PublicationStatus.PUBLISHED:
        raise InvalidTransition("This listing is not published.")
    listing.publication_status = PublicationStatus.DRAFT
    listing.save(update_fields=["publication_status", "updated_at"])
    audit.record(
        actor=locked_seller.account,
        action="real_estate.listing.unpublished",
        target=listing,
        summary=listing.title,
    )
    return listing


def dashboard_summary(seller: RealEstateSeller) -> dict:
    """Backend-computed counts (never a client-side aggregation). `published` is
    the stored status; `visible` passes the full public rule right now;
    `expired` is PUBLISHED past its expiry."""
    now = timezone.now()
    rows = PropertyListing.objects.filter(seller=seller)
    counts = rows.aggregate(
        listings_total=Count("pk"),
        listings_draft=Count("pk", filter=Q(publication_status=PublicationStatus.DRAFT)),
        listings_published=Count("pk", filter=Q(publication_status=PublicationStatus.PUBLISHED)),
        listings_expired=Count(
            "pk", filter=Q(publication_status=PublicationStatus.PUBLISHED, expires_at__lte=now)
        ),
        listings_sale=Count("pk", filter=Q(transaction_type=TransactionType.SALE)),
        listings_rent=Count("pk", filter=Q(transaction_type=TransactionType.RENT)),
    )
    counts["listings_visible"] = rows.publicly_visible(now).count()
    return counts
