"""Advertising services: every lifecycle change is decided on locked, CURRENT
rows, raises typed errors and is audited. Views validate input; nothing commercial
(price, payment state, ownership, status) ever comes from a client.

Lock order for every campaign state change (one order, so transitions cannot
deadlock or interleave):

    MedicalCompany + its account  ->  AdvertisingCampaign  ->  CampaignPayment
        ->  Product (and, at submission, the active AdvertisingRate)

Target child rows are only written while the parent campaign is locked.

`verify_campaign_payment` is THE payment-verification boundary. Today an
administrator calls it after confirming an off-platform payment. A future
gateway integration will authenticate the provider's callback, resolve the
CampaignPayment, verify amount/currency/reference, and then call this same
function — a browser-supplied "payment succeeded" can never activate a campaign.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.geography.models import Governorate
from apps.marketplace.models import MedicalCompany, Product
from apps.providers.types import ProviderType
from apps.specialties.models import Specialty

from .models import (
    AdvertisingCampaign,
    AdvertisingRate,
    CampaignGovernorate,
    CampaignPayment,
    CampaignProviderType,
    CampaignSpecialty,
)
from .types import CampaignStatus, PaymentMethod, PaymentStatus


class AdvertisingError(Exception):
    code = "advertising_error"


class CampaignNotFound(AdvertisingError):
    code = "not_found"


class PricingUnavailable(AdvertisingError):
    code = "pricing_unavailable"


class CampaignNotEditable(AdvertisingError):
    code = "campaign_not_editable"


class CampaignNotSubmittable(AdvertisingError):
    code = "campaign_not_submittable"


class CompanyNotEligible(AdvertisingError):
    code = "company_not_eligible"


class ProductUnavailable(AdvertisingError):
    code = "product_unavailable"


class InvalidTransition(AdvertisingError):
    code = "invalid_transition"


class PaymentNotPending(AdvertisingError):
    code = "payment_not_pending"


class CampaignEnded(AdvertisingError):
    code = "campaign_ended"


class CampaignProblems(AdvertisingError):
    """Field-level problems (`{field: typed code}`); rendered as a validation error."""

    code = "validation_error"

    def __init__(self, problems: dict[str, str]):
        super().__init__("; ".join(f"{field}: {code}" for field, code in problems.items()))
        self.problems = problems


PROBLEM_MESSAGES = {
    "name_required": "A campaign name is required.",
    "product_not_found": "Choose one of your own products.",
    "dates_required": "Both dates are required.",
    "dates_invalid": "The end date cannot be before the start date.",
    "start_in_past": "The start date cannot be in the past.",
    "end_in_past": "The end date cannot be in the past.",
    "governorate_inactive": "A selected governorate is no longer available.",
    "specialty_inactive": "A selected specialty is no longer available.",
    "invalid_choice": "This value is not allowed.",
    "reason_required": "A reason is required.",
}

CAMPAIGN_FIELDS = ("name", "product", "starts_on", "ends_on")
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Quote:
    days: int
    daily_rate: Decimal
    total: Decimal
    currency: str
    rate: AdvertisingRate


# ---- helpers -----------------------------------------------------------------------------


def _lock_company(company_id) -> MedicalCompany:
    """Company and its account, read fresh under lock (role/active flag are decided
    here, never from the request's snapshot)."""
    return MedicalCompany.objects.select_for_update().select_related("account").get(pk=company_id)


def _require_company_account(company: MedicalCompany) -> None:
    """Drafts need an active MEDICAL_COMPANY account (not yet a verified company)."""
    if not (company.account.is_active and company.account.role == AccountRole.MEDICAL_COMPANY):
        raise CompanyNotEligible("Your account must be an active medical company account.")


def _require_company_eligible(company: MedicalCompany) -> None:
    """Submission and payment verification need the marketplace's own publisher
    eligibility (VERIFIED, active account, role MEDICAL_COMPANY): one definition."""
    if not company.can_publish:
        raise CompanyNotEligible(
            "The company must be verified, on an active medical company account."
        )


def _lock_campaign(company: MedicalCompany, campaign_id) -> AdvertisingCampaign:
    campaign = (
        AdvertisingCampaign.objects.select_for_update(of=("self",))
        .filter(pk=campaign_id, company=company)
        .first()
    )
    if campaign is None:
        raise CampaignNotFound("Campaign not found.")
    return campaign


def _require_exposable_product(company: MedicalCompany, product_id) -> Product:
    """The Phase 6 rule, on the locked product row: the company's own product must
    currently be exposable (active, verified company, active category with an
    active audience rule). Payment never overrides marketplace safety."""
    product = (
        Product.objects.select_for_update(of=("self",))
        .filter(pk=product_id, company=company)
        .first()
    )
    if product is None or not Product.objects.exposable().filter(pk=product.pk).exists():
        raise ProductUnavailable("The product is not currently available for advertising.")
    return product


def _target_ids(campaign: AdvertisingCampaign) -> dict[str, list]:
    return {
        "provider_types": list(
            CampaignProviderType.objects.filter(campaign=campaign).values_list(
                "provider_type", flat=True
            )
        ),
        "specialties": list(
            CampaignSpecialty.objects.filter(campaign=campaign).values_list(
                "specialty_id", flat=True
            )
        ),
        "governorates": list(
            CampaignGovernorate.objects.filter(campaign=campaign).values_list(
                "governorate_id", flat=True
            )
        ),
    }


def _reference_problems(campaign: AdvertisingCampaign) -> dict[str, str]:
    """Targeted references must still exist and be active (checked at submission
    and again at payment verification)."""
    problems: dict[str, str] = {}
    if (
        CampaignGovernorate.objects.filter(campaign=campaign, governorate__is_active=False)
        .only("pk")
        .exists()
    ):
        problems["governorates"] = "governorate_inactive"
    if (
        CampaignSpecialty.objects.filter(campaign=campaign, specialty__is_active=False)
        .only("pk")
        .exists()
    ):
        problems["specialties"] = "specialty_inactive"
    return problems


def _replace_targets(
    campaign: AdvertisingCampaign, *, provider_types=None, specialties=None, governorates=None
) -> None:
    """Caller holds the campaign lock. `None` leaves a dimension untouched."""
    if provider_types is not None:
        wanted = set(provider_types)
        CampaignProviderType.objects.filter(campaign=campaign).exclude(
            provider_type__in=wanted
        ).delete()
        have = set(
            CampaignProviderType.objects.filter(campaign=campaign).values_list(
                "provider_type", flat=True
            )
        )
        CampaignProviderType.objects.bulk_create(
            [
                CampaignProviderType(campaign=campaign, provider_type=t)
                for t in sorted(wanted - have)
            ]
        )
    if specialties is not None:
        wanted_ids = {s.pk for s in specialties}
        CampaignSpecialty.objects.filter(campaign=campaign).exclude(
            specialty_id__in=wanted_ids
        ).delete()
        have_ids = set(
            CampaignSpecialty.objects.filter(campaign=campaign).values_list(
                "specialty_id", flat=True
            )
        )
        CampaignSpecialty.objects.bulk_create(
            [
                CampaignSpecialty(campaign=campaign, specialty_id=pk)
                for pk in sorted(wanted_ids - have_ids, key=str)
            ]
        )
    if governorates is not None:
        wanted_ids = {g.pk for g in governorates}
        CampaignGovernorate.objects.filter(campaign=campaign).exclude(
            governorate_id__in=wanted_ids
        ).delete()
        have_ids = set(
            CampaignGovernorate.objects.filter(campaign=campaign).values_list(
                "governorate_id", flat=True
            )
        )
        CampaignGovernorate.objects.bulk_create(
            [
                CampaignGovernorate(campaign=campaign, governorate_id=pk)
                for pk in sorted(wanted_ids - have_ids, key=str)
            ]
        )


def _validated_targets(provider_types, specialties, governorates) -> None:
    problems: dict[str, str] = {}
    if provider_types is not None and any(t not in ProviderType.values for t in provider_types):
        problems["provider_types"] = "invalid_choice"
    if specialties is not None and any(
        not isinstance(s, Specialty) or not s.is_active for s in specialties
    ):
        problems["specialties"] = "specialty_inactive"
    if governorates is not None and any(
        not isinstance(g, Governorate) or not g.is_active for g in governorates
    ):
        problems["governorates"] = "governorate_inactive"
    if problems:
        raise CampaignProblems(problems)


def _draft_structure_problems(campaign: AdvertisingCampaign) -> dict[str, str]:
    problems: dict[str, str] = {}
    if not campaign.name.strip():
        problems["name"] = "name_required"
    if (
        campaign.starts_on is not None
        and campaign.ends_on is not None
        and campaign.ends_on < campaign.starts_on
    ):
        problems["ends_on"] = "dates_invalid"
    return problems


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _build_quote(rate: AdvertisingRate, starts_on: date, ends_on: date) -> Quote:
    days = (ends_on - starts_on).days + 1
    return Quote(
        days=days,
        daily_rate=rate.price_per_day,
        total=_quantize(rate.price_per_day * days),
        currency=rate.currency,
        rate=rate,
    )


def _date_problems_for_quote(starts_on, ends_on) -> dict[str, str]:
    problems: dict[str, str] = {}
    if starts_on is None:
        problems["starts_on"] = "dates_required"
    if ends_on is None:
        problems["ends_on"] = "dates_required"
    if problems:
        return problems
    if ends_on < starts_on:
        problems["ends_on"] = "dates_invalid"
    return problems


# ---- quote (preview) -------------------------------------------------------------------------


def quote_for_dates(starts_on: date | None, ends_on: date | None) -> Quote:
    """A PREVIEW from the currently active rate. Submission recomputes its own
    quote under lock and never accepts this one back from a client."""
    problems = _date_problems_for_quote(starts_on, ends_on)
    if problems:
        raise CampaignProblems(problems)
    rate = AdvertisingRate.objects.filter(is_active=True).first()
    if rate is None:
        raise PricingUnavailable("Advertising pricing has not been configured yet.")
    return _build_quote(rate, starts_on, ends_on)


def _lock_active_rate() -> AdvertisingRate:
    # Two tries: a rate swap committing while we waited must not look like "no price".
    for _ in range(2):
        rate = AdvertisingRate.objects.select_for_update().filter(is_active=True).first()
        if rate is not None:
            return rate
    raise PricingUnavailable("Advertising pricing has not been configured yet.")


# ---- company: drafts ---------------------------------------------------------------------------


@transaction.atomic
def create_campaign(
    company: MedicalCompany,
    fields: dict,
    *,
    provider_types=None,
    specialties=None,
    governorates=None,
) -> AdvertisingCampaign:
    locked_company = _lock_company(company.pk)
    _require_company_account(locked_company)
    product = fields.get("product")
    if (
        product is None
        or not Product.objects.filter(
            pk=getattr(product, "pk", None), company=locked_company
        ).exists()
    ):
        raise CampaignProblems({"product": "product_not_found"})
    campaign = AdvertisingCampaign(
        company=locked_company,
        product=product,
        name=fields.get("name", "").strip(),
        starts_on=fields.get("starts_on"),
        ends_on=fields.get("ends_on"),
    )
    problems = _draft_structure_problems(campaign)
    if problems:
        raise CampaignProblems(problems)
    _validated_targets(provider_types, specialties, governorates)
    campaign.save()
    _replace_targets(
        campaign, provider_types=provider_types, specialties=specialties, governorates=governorates
    )
    audit.record(
        actor=locked_company.account,
        action="advertising.campaign.created",
        target=campaign,
        summary=campaign.name,
        data={"product": str(campaign.product_id)},
    )
    return campaign


@transaction.atomic
def update_campaign(
    company: MedicalCompany,
    campaign_id,
    changes: dict,
    *,
    provider_types=None,
    specialties=None,
    governorates=None,
) -> AdvertisingCampaign:
    locked_company = _lock_company(company.pk)
    _require_company_account(locked_company)
    campaign = _lock_campaign(locked_company, campaign_id)
    if campaign.status != CampaignStatus.DRAFT:
        raise CampaignNotEditable("Only a draft campaign can be edited.")
    changed = [k for k in changes if k in CAMPAIGN_FIELDS]
    if "product" in changes:
        product = changes["product"]
        if not Product.objects.filter(
            pk=getattr(product, "pk", None), company=locked_company
        ).exists():
            raise CampaignProblems({"product": "product_not_found"})
        campaign.product = product
    for key in ("name", "starts_on", "ends_on"):
        if key in changes:
            setattr(campaign, key, changes[key].strip() if key == "name" else changes[key])
    problems = _draft_structure_problems(campaign)
    if problems:
        raise CampaignProblems(problems)
    _validated_targets(provider_types, specialties, governorates)
    if changed:
        campaign.save(update_fields=[*changed, "updated_at"])
    _replace_targets(
        campaign, provider_types=provider_types, specialties=specialties, governorates=governorates
    )
    audit.record(
        actor=locked_company.account,
        action="advertising.campaign.updated",
        target=campaign,
        summary=campaign.name,
        data={
            "fields": sorted(
                [
                    *changed,
                    *(["provider_types"] if provider_types is not None else []),
                    *(["specialties"] if specialties is not None else []),
                    *(["governorates"] if governorates is not None else []),
                ]
            )
        },
    )
    return campaign


# ---- company: submission (the authoritative quote) ---------------------------------------------


@transaction.atomic
def submit_campaign(company: MedicalCompany, campaign_id) -> AdvertisingCampaign:
    """DRAFT -> PENDING_PAYMENT. Recomputes the price under lock from the
    CURRENT active rate, snapshots it on the campaign and creates the one
    CampaignPayment (PENDING). Nothing here trusts a client price."""
    locked_company = _lock_company(company.pk)
    _require_company_eligible(locked_company)
    campaign = _lock_campaign(locked_company, campaign_id)
    if campaign.status != CampaignStatus.DRAFT:
        raise CampaignNotSubmittable("Only a draft campaign can be submitted.")
    _require_exposable_product(locked_company, campaign.product_id)
    problems = {
        **_draft_structure_problems(campaign),
        **_date_problems_for_quote(campaign.starts_on, campaign.ends_on),
    }
    if not problems:
        today = timezone.localdate()
        if campaign.starts_on < today:
            problems["starts_on"] = "start_in_past"
        if campaign.ends_on < today:
            problems["ends_on"] = "end_in_past"
    problems.update(_reference_problems(campaign))
    if problems:
        raise CampaignProblems(problems)
    rate = _lock_active_rate()
    quote = _build_quote(rate, campaign.starts_on, campaign.ends_on)
    now = timezone.now()
    campaign.quoted_days = quote.days
    campaign.quoted_daily_rate = quote.daily_rate
    campaign.quoted_amount = quote.total
    campaign.quoted_currency = quote.currency
    campaign.quoted_at = now
    campaign.rate = rate
    campaign.status = CampaignStatus.PENDING_PAYMENT
    campaign.save()
    payment = CampaignPayment.objects.create(
        campaign=campaign,
        amount=quote.total,
        currency=quote.currency,
        status=PaymentStatus.PENDING,
    )
    audit.record(
        actor=locked_company.account,
        action="advertising.payment.created",
        target=payment,
        summary=f"{payment.amount} {payment.currency}",
        data={"campaign": str(campaign.pk)},
    )
    audit.record(
        actor=locked_company.account,
        action="advertising.campaign.submitted",
        target=campaign,
        summary=campaign.name,
        data={"days": quote.days, "amount": str(quote.total), "currency": quote.currency},
    )
    return campaign


@transaction.atomic
def cancel_campaign(company: MedicalCompany, campaign_id) -> AdvertisingCampaign:
    """ACTIVE -> CANCELLED. Stops exposure at once; nothing financial changes
    (no refund, credit or payment edit — reconciliation stays manual)."""
    locked_company = _lock_company(company.pk)  # withdrawal is allowed whatever the account state
    campaign = _lock_campaign(locked_company, campaign_id)
    if campaign.status != CampaignStatus.ACTIVE:
        raise InvalidTransition("Only an active campaign can be cancelled.")
    campaign.status = CampaignStatus.CANCELLED
    campaign.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=locked_company.account,
        action="advertising.campaign.cancelled",
        target=campaign,
        summary=campaign.name,
    )
    return campaign


# ---- administrators: manual payment decisions -------------------------------------------------


def _lock_pending(campaign_id):
    """Company -> campaign -> payment, all locked, all re-read. Returns the trio."""
    company_id = (
        AdvertisingCampaign.objects.filter(pk=campaign_id)
        .values_list("company_id", flat=True)
        .first()
    )
    if company_id is None:
        raise CampaignNotFound("Campaign not found.")
    company = _lock_company(company_id)
    campaign = _lock_campaign(company, campaign_id)
    payment = (
        CampaignPayment.objects.select_for_update(of=("self",)).filter(campaign=campaign).first()
    )
    if campaign.status != CampaignStatus.PENDING_PAYMENT or payment is None:
        raise InvalidTransition("This campaign is not awaiting payment verification.")
    if payment.status != PaymentStatus.PENDING:
        raise PaymentNotPending("This payment has already been decided.")
    return company, campaign, payment


@transaction.atomic
def verify_campaign_payment(
    campaign_id, *, method: str, reference: str = "", note: str = "", verified_by
) -> AdvertisingCampaign:
    """The payment-verification boundary. Marks the payment VERIFIED and the
    campaign ACTIVE in ONE transaction, only after every activation check passes
    on current state (none of them is skipped because money was received). The
    amount is the campaign's own snapshot — never an input."""
    if method not in PaymentMethod.values:
        raise CampaignProblems({"method": "invalid_choice"})
    company, campaign, payment = _lock_pending(campaign_id)
    _require_company_eligible(company)
    _require_exposable_product(company, campaign.product_id)
    problems = _reference_problems(campaign)
    if problems:
        raise CampaignProblems(problems)
    if campaign.ends_on < timezone.localdate():
        raise CampaignEnded("The campaign's end date has already passed.")
    now = timezone.now()
    payment.status = PaymentStatus.VERIFIED
    payment.method = method
    payment.reference = reference.strip()
    payment.verified_by = verified_by
    payment.verified_at = now
    payment.admin_note = note.strip()
    payment.save()
    campaign.status = CampaignStatus.ACTIVE
    campaign.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=verified_by,
        action="advertising.payment.verified",
        target=payment,
        summary=f"{payment.amount} {payment.currency}",
        data={"campaign": str(campaign.pk), "method": method},
    )
    audit.record(
        actor=verified_by,
        action="advertising.campaign.activated",
        target=campaign,
        summary=campaign.name,
    )
    return campaign


@transaction.atomic
def reject_campaign_payment(campaign_id, *, reason: str, rejected_by) -> AdvertisingCampaign:
    """PENDING payment -> REJECTED and PENDING_PAYMENT campaign -> REJECTED, atomically.
    A rejected campaign is history: another attempt is a new campaign."""
    if not reason.strip():
        raise CampaignProblems({"reason": "reason_required"})
    _company, campaign, payment = _lock_pending(campaign_id)
    payment.status = PaymentStatus.REJECTED
    payment.admin_note = reason.strip()
    payment.save()
    campaign.status = CampaignStatus.REJECTED
    campaign.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=rejected_by,
        action="advertising.payment.rejected",
        target=payment,
        summary=f"{payment.amount} {payment.currency}",
        data={"campaign": str(campaign.pk)},
    )
    return campaign


# ---- dashboard --------------------------------------------------------------------------------


def dashboard_summary(company: MedicalCompany) -> dict:
    """Backend-computed counts (no analytics exist: no impressions, clicks or ROI)."""
    today = timezone.localdate()
    rows = AdvertisingCampaign.objects.filter(company=company)
    return rows.aggregate(
        campaigns_total=Count("pk"),
        campaigns_draft=Count("pk", filter=Q(status=CampaignStatus.DRAFT)),
        campaigns_pending_payment=Count("pk", filter=Q(status=CampaignStatus.PENDING_PAYMENT)),
        campaigns_active=Count("pk", filter=Q(status=CampaignStatus.ACTIVE)),
        campaigns_live=Count(
            "pk",
            filter=Q(status=CampaignStatus.ACTIVE, starts_on__lte=today, ends_on__gte=today),
        ),
        campaigns_ended=Count("pk", filter=Q(status=CampaignStatus.ACTIVE, ends_on__lt=today)),
        campaigns_rejected=Count("pk", filter=Q(status=CampaignStatus.REJECTED)),
        campaigns_cancelled=Count("pk", filter=Q(status=CampaignStatus.CANCELLED)),
    )
