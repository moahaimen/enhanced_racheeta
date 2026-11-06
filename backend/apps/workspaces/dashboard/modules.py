"""Reusable dashboard modules (notifications, feeds, provider/organization blocks, setup steps)."""

from __future__ import annotations

from django.utils import timezone

from apps.chat import services as chat_services
from apps.commerce.models import QuoteRequest
from apps.commerce.types import OPEN_QUOTE_STATUSES, QuoteStatus
from apps.core.features import reservations_enabled
from apps.dashboards.services import providers as provider_services
from apps.dashboards.services import recruiter as recruiter_services
from apps.dashboards.services import reservations as reservation_services
from apps.dashboards.services.common import status_counts
from apps.jobs.models import EmployerMembership
from apps.jobs.types import MemberStatus as EmployerMemberStatus
from apps.marketplace.models import Product, ProductCategory
from apps.marketplace.permissions import current_verified_provider
from apps.notifications import services as notification_services
from apps.offers.models import Offer
from apps.preferences import services as preferences
from apps.providers.models import ProviderMembership, ProviderProfile, ServiceOffering
from apps.providers.types import MembershipStatus, VerificationStatus
from apps.reservations.types import ReservationStatus

from ..models import OrganizationMember
from ..types import MemberStatus
from .primitives import LIST_LIMIT, _item, _module, _money, _stat


def _notifications(account) -> dict:
    return _module(
        "notifications",
        stats=[
            _stat("unread_notifications", notification_services.unread_count(account)),
            _stat("unread_messages", chat_services.unread_count(account)),
        ],
        link="/notifications",
    )


def _account_settings() -> dict:
    return _module(
        "account",
        items=[
            _item("profile", "profile", path="/profile"),
            _item("preferences", "preferences", path="/settings/preferences"),
        ],
    )


def _feeds(account, provider) -> list[dict]:
    """Sponsored products and promoted properties: only for a verified provider (re-read now)
    whose display preference / outreach opt-in allows them."""
    if provider is None or current_verified_provider(account) is None:
        return []
    prefs = preferences.get(account)
    out = []
    if prefs["show_sponsored_products"]:
        out.append(_module("sponsored"))
    if prefs["real_estate_promotions"] and prefs["channel_in_app"]:
        out.append(_module("promoted"))
    return out


# ---- provider (practitioner and facility) modules ----------------------------------------------


def _profile_module(profile: ProviderProfile, edit_path="/provider/profile") -> dict:
    services_count = ServiceOffering.objects.filter(provider=profile, is_active=True).count()
    return _module(
        "profile",
        variant=profile.provider_type,
        stats=[
            _stat("verification", profile.verification_status),
            _stat("visible", profile.is_visible),
            _stat("active_services", services_count),
        ],
        link=edit_path,
    )


def _services_module(profile: ProviderProfile, variant: str, link="/provider/profile") -> dict:
    rows = ServiceOffering.objects.filter(provider=profile, is_active=True).order_by("title")
    return _module(
        "services",
        variant=variant,
        stats=[_stat("active_services", rows.count())],
        items=[_item(s.pk, s.title, _money(s.price, s.currency)) for s in rows[:LIST_LIMIT]],
        link=link,
    )


def _reservations_module(profile: ProviderProfile, variant="appointments", link="") -> dict | None:
    if not reservations_enabled():
        return None
    summary = reservation_services.provider_summary(profile)
    counts = summary["reservations"]
    return _module(
        "reservations",
        variant=variant,
        stats=[
            _stat("upcoming", counts["upcoming"]),
            _stat("pending", counts["by_status"][ReservationStatus.PENDING]),
            _stat("completed", counts["by_status"][ReservationStatus.COMPLETED]),
            _stat("total", counts["total"]),
        ],
        items=[
            _item(
                r["id"],
                r["service_title_snapshot"],
                r["starts_at"].isoformat(),
                r["status"],
                "reservationStatus",
            )
            for r in summary["upcoming"]
        ],
        link=link,
    )


def _offers_module(profile: ProviderProfile, variant="offers", link="/provider/offers") -> dict:
    summary = provider_services.offer_summary(profile)
    now = timezone.now()
    running = Offer.objects.filter(
        provider=profile, is_active=True, starts_at__lte=now, ends_at__gt=now
    ).order_by("ends_at")
    return _module(
        "offers",
        variant=variant,
        stats=[
            _stat("running_now", summary["running_now"]),
            _stat("scheduled", summary["scheduled"]),
            _stat("total", summary["total"]),
        ],
        items=[_item(o.pk, o.title, _money(o.offer_price, "IQD")) for o in running[:LIST_LIMIT]],
        link=link,
    )


def _reviews_module(profile: ProviderProfile) -> dict:
    summary = provider_services.review_summary(profile)
    return _module(
        "reviews",
        stats=[
            _stat("average_rating", summary["average_rating"]),
            _stat("review_count", summary["review_count"]),
        ],
    )


def _relevant_products(profile: ProviderProfile, variant: str) -> dict | None:
    """The professional B2B catalogue the targeting rule admits for THIS provider."""
    rows = Product.objects.targeted_for(profile).select_related("company").order_by("-created_at")
    suppliers = rows.values("company_id").distinct().count()
    return _module(
        "products",
        variant=variant,
        stats=[_stat("relevant_products", rows.count()), _stat("suppliers", suppliers)],
        items=[
            _item(p.pk, p.title, p.company.name, path=f"/marketplace/products/{p.pk}")
            for p in rows[:LIST_LIMIT]
        ],
        link="/marketplace",
    )


def _categories_module(profile: ProviderProfile) -> dict:
    """Pharmacy: the product categories its provider type is eligible to see."""
    category_ids = Product.objects.targeted_for(profile).values("category_id").distinct()
    rows = ProductCategory.objects.filter(pk__in=category_ids).order_by("sort_order")
    return _module(
        "categories",
        stats=[_stat("eligible_categories", rows.count())],
        items=[_item(c.pk, f"{c.name_ar} | {c.name_en}") for c in rows[:LIST_LIMIT]],
        link="/marketplace",
    )


def _buyer_quotes_module(profile: ProviderProfile) -> dict:
    rows = QuoteRequest.objects.filter(requester=profile)
    counts = status_counts(rows, "status", QuoteStatus.values)
    return _module(
        "my_quotes",
        stats=[
            _stat("open", sum(counts["by_status"][s] for s in OPEN_QUOTE_STATUSES)),
            _stat("quoted", counts["by_status"][QuoteStatus.QUOTED]),
            _stat("accepted", counts["by_status"][QuoteStatus.ACCEPTED]),
        ],
        items=[
            _item(q.pk, q.product.title, q.company.name, q.status, "quotes.status", "/quotes")
            for q in rows.select_related("product", "company").order_by("-created_at")[:LIST_LIMIT]
        ],
        link="/quotes",
    )


def _connections_module(profile: ProviderProfile) -> dict:
    """Practitioner ↔ facility affiliations (public professional connections)."""
    rows = ProviderMembership.objects.filter(practitioner=profile).select_related("facility")
    active = rows.filter(status=MembershipStatus.ACTIVE)
    return _module(
        "connections",
        stats=[
            _stat("active", active.count()),
            _stat("pending", rows.filter(status=MembershipStatus.PENDING).count()),
        ],
        items=[_item(m.pk, m.facility.display_name, m.role_title) for m in active[:LIST_LIMIT]],
        link="/provider/profile",
    )


def _practitioners_module(facility: ProviderProfile) -> dict:
    summary = provider_services.facility_membership_summary(facility)
    rows = (
        ProviderMembership.objects.filter(facility=facility, status=MembershipStatus.ACTIVE)
        .select_related("practitioner")
        .order_by("practitioner__display_name")
    )
    return _module(
        "practitioners",
        stats=[
            _stat("active", summary["active"]),
            _stat("incoming_requests", summary["incoming_requests"]),
            _stat("outgoing_invitations", summary["outgoing_invitations"]),
        ],
        items=[_item(m.pk, m.practitioner.display_name, m.role_title) for m in rows[:LIST_LIMIT]],
        link="/provider/profile",
    )


def _team_module(*, facility=None, company=None, team_path="") -> dict:
    scope = {"facility": facility} if facility is not None else {"company": company}
    rows = OrganizationMember.objects.filter(status=MemberStatus.ACTIVE, **scope).select_related(
        "account"
    )
    by_role = status_counts(rows, "role", ["MANAGER", "STAFF", "VIEWER"])["by_status"]
    return _module(
        "team",
        stats=[_stat(f"role_{k.lower()}", v) for k, v in by_role.items()],
        items=[
            _item(m.pk, m.account.full_name, "", m.role, "ws.roles")
            for m in rows.order_by("role", "account__full_name")[:LIST_LIMIT]
        ],
        link=team_path,
    )


def _recruitment_module(owner_account) -> dict | None:
    membership = (
        EmployerMembership.objects.filter(account=owner_account, status=EmployerMemberStatus.ACTIVE)
        .select_related("employer")
        .first()
    )
    if membership is None:
        return _module("recruitment", stats=[_stat("employer_profile", False)], link="/employer")
    summary = recruiter_services.recruiter_summary(membership)
    stats = [
        _stat("open_jobs", summary["jobs"]["open_now"]),
        _stat("jobs_total", summary["jobs"]["total"]),
    ]
    if summary["applications"] is not None:
        stats.append(_stat("awaiting_review", summary["applications"]["awaiting_review"]))
    return _module("recruitment", stats=stats, link="/employer")


# ---- setup (new or unverified accounts) -------------------------------------------------------


def _step(key, done: bool, path: str) -> dict:
    return _item(key, key, "", "DONE" if done else "TODO", "dash.step", path)


def _provider_setup(profile: ProviderProfile) -> dict | None:
    """Checklist for a provider that is not yet verified (nothing to show once it is)."""
    if profile.verification_status == VerificationStatus.VERIFIED:
        return None
    has_services = ServiceOffering.objects.filter(provider=profile, is_active=True).exists()
    requested = profile.verification_status in (
        VerificationStatus.PENDING,
        VerificationStatus.VERIFIED,
    )
    return _module(
        "setup",
        variant="provider",
        stats=[_stat("verification", profile.verification_status)],
        items=[
            _step("create_profile", True, "/provider/profile"),
            _step("add_services", has_services, "/provider/profile"),
            _step("request_verification", requested, "/provider/profile"),
        ],
        link="/provider/profile",
    )


def _setup(account) -> list:
    role = account.role
    if role == "PROVIDER":
        steps = [
            _step("create_profile", False, "/provider/profile"),
            _step("add_services", False, "/provider/profile"),
            _step("request_verification", False, "/provider/profile"),
        ]
        link = "/provider/profile"
    elif role == "MEDICAL_COMPANY":
        steps = [
            _step("create_company", False, "/company"),
            _step("add_products", False, "/company"),
            _step("request_verification", False, "/company"),
        ]
        link = "/company"
    elif role == "PATIENT" and account.account_type == "EMPLOYER":
        steps = [
            _step("create_employer", False, "/employer"),
            _step("request_verification", False, "/employer"),
            _step("post_job", False, "/employer/jobs/new"),
        ]
        link = "/employer"
        return [_module("setup", variant="employer", items=steps, link=link)]
    elif role == "PATIENT" and account.account_type == "JOB_SEEKER":
        steps = [
            _step("create_resume", False, "/jobs/profile"),
            _step("browse_jobs", False, "/jobs"),
        ]
        link = "/jobs/profile"
        return [_module("setup", variant="job_seeker", items=steps, link=link)]
    else:
        steps = [
            _step("create_seller", False, "/real-estate/owner"),
            _step("add_listing", False, "/real-estate/owner"),
        ]
        link = "/real-estate/owner"
    return [_module("setup", variant=role.lower(), items=steps, link=link)]


# ---- compositions -----------------------------------------------------------------------------
