"""Marketplace services: every state change is decided on locked rows, raises
typed errors and is audited. Views never derive ownership from client ids."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.geography.models import City

from .models import MedicalCompany, Product, ProductCategory
from .types import (
    ADMIN_VERIFICATION_TARGETS,
    COMPANY_IDENTITY_FIELDS,
    IDENTITY_LOCKED_STATUSES,
    VERIFICATION_REQUESTABLE_FROM,
    CompanyVerificationStatus,
)


class MarketplaceError(Exception):
    code = "marketplace_error"


class InvalidTransition(MarketplaceError):
    code = "invalid_transition"


class AlreadyExists(MarketplaceError):
    code = "already_exists"


class CompanyNotVerified(MarketplaceError):
    code = "company_not_verified"


class CategoryUnavailable(MarketplaceError):
    code = "category_unavailable"


class IdentityLocked(MarketplaceError):
    code = "identity_locked"

    def __init__(self, fields: list[str]):
        super().__init__("Verified company identity cannot be changed: " + ", ".join(fields))
        self.fields = fields


class InvalidProduct(MarketplaceError):
    code = "invalid_product"


class ProductNotFound(MarketplaceError):
    code = "not_found"


COMPANY_FIELDS = (
    "name",
    "description",
    "phone",
    "public_email",
    "website",
    "governorate",
    "city",
    "address",
)
PRODUCT_FIELDS = ("category", "title", "description", "brand", "model_name", "price", "currency")


def _require_city_in_governorate(row) -> None:
    if row.city_id is not None:
        governorate_id = (
            City.objects.filter(pk=row.city_id).values_list("governorate_id", flat=True).first()
        )
        if governorate_id != row.governorate_id:
            raise InvalidProduct("This city does not belong to the selected governorate.")


# ---- company ---------------------------------------------------------------------------------


@transaction.atomic
def create_company(account, fields: dict) -> MedicalCompany:
    company = MedicalCompany(
        account=account, **{k: v for k, v in fields.items() if k in COMPANY_FIELDS}
    )
    _require_city_in_governorate(company)
    try:
        with transaction.atomic():
            company.save()
    except IntegrityError as exc:  # one company per account (OneToOne)
        if "marketplace_company" not in str(exc):
            raise
        raise AlreadyExists("You already have a company profile.") from exc
    audit.record(
        actor=account, action="marketplace.company.created", target=company, summary=company.name
    )
    return company


@transaction.atomic
def update_company(company: MedicalCompany, fields: dict) -> MedicalCompany:
    locked = MedicalCompany.objects.select_for_update().get(pk=company.pk)
    # Identity under review or verified is frozen, decided on the LOCKED row
    # (the row the administrator's decision locks too). Sending the current
    # value is not a change.
    if locked.verification_status in IDENTITY_LOCKED_STATUSES:
        changed = [
            f for f in COMPANY_IDENTITY_FIELDS if f in fields and fields[f] != getattr(locked, f)
        ]
        if changed:
            raise IdentityLocked(changed)
    for key, value in fields.items():
        if key in COMPANY_FIELDS:
            setattr(locked, key, value)
    _require_city_in_governorate(locked)
    locked.save(update_fields=[*[k for k in fields if k in COMPANY_FIELDS], "updated_at"])
    company.__dict__.update({k: v for k, v in locked.__dict__.items() if k != "_state"})
    return company


@transaction.atomic
def request_verification(company: MedicalCompany) -> MedicalCompany:
    locked = MedicalCompany.objects.select_for_update().get(pk=company.pk)
    if locked.verification_status not in VERIFICATION_REQUESTABLE_FROM:
        raise InvalidTransition(
            f"Verification cannot be requested from status {locked.verification_status}."
        )
    now = timezone.now()
    locked.verification_status = CompanyVerificationStatus.PENDING
    locked.verification_requested_at = now
    locked.verification_changed_at = now
    locked.save(
        update_fields=[
            "verification_status",
            "verification_requested_at",
            "verification_changed_at",
            "updated_at",
        ]
    )
    audit.record(
        actor=company.account,
        action="marketplace.company.verification_requested",
        target=locked,
        summary=locked.name,
    )
    company.__dict__.update({k: v for k, v in locked.__dict__.items() if k != "_state"})
    return company


@transaction.atomic
def set_verification(
    company: MedicalCompany, status: str, *, admin, note: str = ""
) -> MedicalCompany:
    """Administrator decision, on the locked row. Products are not touched:
    exposure is derived from the company's current status at read time."""
    if status not in ADMIN_VERIFICATION_TARGETS:
        raise InvalidTransition(f"{status} is not an administrator-settable status.")
    locked = MedicalCompany.objects.select_for_update().get(pk=company.pk)
    now = timezone.now()
    locked.verification_status = status
    locked.verification_note = note
    locked.verification_changed_at = now
    update_fields = [
        "verification_status",
        "verification_note",
        "verification_changed_at",
        "updated_at",
    ]
    if status == CompanyVerificationStatus.VERIFIED:
        locked.verified_at = now
        update_fields.append("verified_at")
    locked.save(update_fields=update_fields)
    audit.record(
        actor=admin,
        action="marketplace.company.verification_set",
        target=locked,
        summary=f"{status}: {note}"[:255],
    )
    company.__dict__.update({k: v for k, v in locked.__dict__.items() if k != "_state"})
    return company


# ---- products --------------------------------------------------------------------------------


def _locked_publishable_category(category_id) -> ProductCategory:
    """A product may be (re)activated only in an active category that has at
    least one active audience rule — otherwise nobody could ever see it."""
    category = (
        ProductCategory.objects.select_for_update(of=("self",))
        .filter(pk=category_id, is_active=True)
        .first()
    )
    if category is None or not category.has_active_audience():
        raise CategoryUnavailable(
            "This category is not available for publication (inactive or without an audience)."
        )
    return category


def _require_publishable(company: MedicalCompany, product: Product) -> None:
    """The activation gate, on locked state: verified company with an active
    account, publishable category. Never decided from stale snapshots."""
    if not company.can_publish:
        raise CompanyNotVerified("The company must be verified before publishing products.")
    _locked_publishable_category(product.category_id)


def _validate_product(product: Product) -> None:
    if product.price is not None and product.price < 0:
        raise InvalidProduct("Price must be zero or more.")
    if not product.title.strip():
        raise InvalidProduct("Title is required.")


@transaction.atomic
def create_product(company: MedicalCompany, fields: dict) -> Product:
    locked_company = (
        MedicalCompany.objects.select_for_update().select_related("account").get(pk=company.pk)
    )
    values = {k: v for k, v in fields.items() if k in PRODUCT_FIELDS}
    category = values.get("category")
    if (
        category is None
        or not ProductCategory.objects.filter(pk=category.pk, is_active=True).exists()
    ):
        raise CategoryUnavailable("Choose an active category.")
    product = Product(company=locked_company, is_active=False, **values)
    for f in ("title", "description", "brand", "model_name"):
        setattr(product, f, getattr(product, f).strip())
    _validate_product(product)
    product.save()
    audit.record(
        actor=locked_company.account,
        action="marketplace.product.created",
        target=product,
        summary=product.title,
        data={"category": str(product.category_id)},
    )
    return product


@transaction.atomic
def update_product(company: MedicalCompany, product_id, changes: dict, *, active=None) -> Product:
    """Owner edit and/or publication switch. Lock order company → product →
    category; an update that results in an ACTIVE product re-runs the full
    publication gate on the locked company and category."""
    locked_company = (
        MedicalCompany.objects.select_for_update().select_related("account").get(pk=company.pk)
    )
    product = (
        Product.objects.select_for_update(of=("self",))
        .filter(pk=product_id, company=locked_company)
        .first()
    )
    if product is None:
        raise ProductNotFound("Product not found.")
    for key, value in changes.items():
        if key in PRODUCT_FIELDS:
            setattr(product, key, value.strip() if isinstance(value, str) else value)
    if active is not None:
        product.is_active = bool(active)
    _validate_product(product)
    if product.is_active:
        _require_publishable(locked_company, product)
    elif (
        "category" in changes
        and not ProductCategory.objects.filter(pk=product.category_id, is_active=True).exists()
    ):
        raise CategoryUnavailable("Choose an active category.")
    product.save()
    audit.record(
        actor=locked_company.account,
        action="marketplace.product.updated",
        target=product,
        summary=product.title,
        data={
            "is_active": product.is_active,
            "fields": sorted(k for k in changes if k in PRODUCT_FIELDS),
        },
    )
    return product


def dashboard_summary(company: MedicalCompany) -> dict:
    """Backend-computed counts (never a client-side aggregation)."""
    rows = Product.objects.filter(company=company)
    total = rows.count()
    active = rows.filter(is_active=True).count()
    exposable = rows.exposable().count() if company.can_publish else 0
    return {
        "verification_status": company.verification_status,
        "can_publish": company.can_publish,
        "products_total": total,
        "products_active": active,
        "products_inactive": total - active,
        "products_exposable": exposable,
    }
