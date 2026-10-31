"""Module-based workspace dashboards (docs/LOCAL_WORKSPACE_DEMO.md §9).

ONE composer for every account type. The workspace to render is re-resolved from
`services.build_workspaces(account)` on every request, so a forged, revoked or suspended
workspace id simply is not there (404 in the view). Which modules appear is decided here from
the workspace kind, its subtype (doctor, pharmacy, assistive-device store...) and the caller's
CURRENT capabilities in that organization; React only renders what it receives.

Every number comes from a real query over the caller's own rows (or, for an organization
member, that organization's rows). Nothing is estimated or invented: no impressions, clicks or
revenue exist, so none are reported. Lists carry public/business facts only — never a patient's
contact data or a requester's e-mail.

Payload: {workspace, header, actions[], modules[]}. A module is
    {key, variant, stats: [{key, value}], items: [{id, title, subtitle, status, status_group,
     path}], link}
Two "feed" modules (`sponsored`, `promoted`) carry no data: the client loads them from their
own eligibility-checked endpoints, and they are included only when the caller is eligible.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Account
from apps.advertising.models import AdvertisingCampaign, CampaignPayment
from apps.advertising.types import CampaignStatus
from apps.chat import services as chat_services
from apps.commerce.models import Order, QuoteRequest
from apps.commerce.types import OPEN_QUOTE_STATUSES, OrderStatus, QuoteStatus
from apps.dashboards.services import admin as admin_services
from apps.dashboards.services import providers as provider_services
from apps.dashboards.services import recruiter as recruiter_services
from apps.dashboards.services import reservations as reservation_services
from apps.dashboards.services.common import status_counts
from apps.jobs import services as jobs_services
from apps.jobs.models import (
    EmployerMembership,
    InterviewRequest,
    JobApplication,
    JobInvitation,
    JobPost,
    JobSeekerProfile,
)
from apps.jobs.types import ApplicationStatus, InterviewStatus, InvitationStatus, JobStatus
from apps.jobs.types import MemberStatus as EmployerMemberStatus
from apps.marketplace.models import MedicalCompany, Product, ProductCategory
from apps.marketplace.permissions import current_verified_provider
from apps.marketplace.types import RETAIL_BUSINESS_TYPES, CompanyVerificationStatus
from apps.notifications import services as notification_services
from apps.offers.models import Offer
from apps.preferences import services as preferences
from apps.providers.models import ProviderMembership, ProviderProfile, ServiceOffering
from apps.providers.types import MembershipStatus, VerificationStatus
from apps.real_estate.models import ListingPromotion, PropertyListing, RealEstateSeller
from apps.real_estate.types import PromotionStatus, PublicationStatus
from apps.reservations.types import ReservationStatus
from apps.reviews.models import Review

from . import services
from .models import OrganizationMember
from .types import MemberStatus, role_has

LIST_LIMIT = 5
LOW_STOCK = 5


# ---- building blocks --------------------------------------------------------------------------


def _stat(key: str, value) -> dict:
    return {"key": key, "value": value}


def _item(id, title, subtitle="", status="", status_group="", path="") -> dict:
    return {
        "id": str(id),
        "title": title,
        "subtitle": subtitle,
        "status": status,
        "status_group": status_group,
        "path": path,
    }


def _module(key, *, variant="", stats=(), items=(), link="") -> dict:
    return {
        "key": key,
        "variant": variant,
        "stats": list(stats),
        "items": list(items),
        "link": link,
    }


def reservations_enabled() -> bool:
    return bool(settings.RACHEETA.get("RESERVATIONS_ENABLED", True))


def _money(value, currency) -> str:
    return "" if value is None else f"{value:,.0f} {currency}"


# ---- shared modules ---------------------------------------------------------------------------


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


# ---- compositions -----------------------------------------------------------------------------

PRACTITIONER_VARIANT = {
    "DOCTOR": ("medical", "appointments", "products"),
    "NURSE": ("nursing", "appointments", "suppliers"),
    "THERAPIST": ("therapy", "sessions", "rehab_products"),
}
FACILITY_SERVICES = {
    "HOSPITAL": "departments",
    "MEDICAL_CENTER": "clinics",
    "PHARMACY": "pharmacy",
    "LABORATORY": "lab_tests",
    "BEAUTY_CENTER": "aesthetic",
}


def _practitioner(account, profile: ProviderProfile) -> list:
    services_variant, reservation_variant, products_variant = PRACTITIONER_VARIANT.get(
        profile.provider_type, ("medical", "appointments", "products")
    )
    verified = profile.verification_status == VerificationStatus.VERIFIED
    modules = [
        _profile_module(profile),
        _services_module(profile, services_variant),
        _reservations_module(profile, reservation_variant, "/provider/reservations"),
        _offers_module(profile),
    ]
    if profile.provider_type == "NURSE":
        modules.append(_connections_module(profile))
    else:
        modules.append(_reviews_module(profile))
    if verified:
        modules += [_relevant_products(profile, products_variant), _buyer_quotes_module(profile)]
    modules += _feeds(account, profile)
    return modules


def _facility(account, facility: ProviderProfile, role: str, team_path: str) -> list:
    kind = facility.provider_type
    owner = role_has(role, "org.owner_tools")
    verified = facility.verification_status == VerificationStatus.VERIFIED
    modules = [_profile_module(facility, edit_path="/provider/profile" if owner else team_path)]
    if kind != "PHARMACY":
        modules.append(
            _services_module(facility, FACILITY_SERVICES.get(kind, "clinics"), team_path)
        )
    if kind in ("HOSPITAL", "MEDICAL_CENTER"):
        modules.append(_practitioners_module(facility))
    if role_has(role, "facility.reservations.view") and kind != "PHARMACY":
        modules.append(_reservations_module(facility, "appointments", f"{team_path}"))
    modules.append(
        _offers_module(
            facility,
            "promotions" if kind == "BEAUTY_CENTER" else "offers",
            "/provider/offers" if owner else team_path,
        )
    )
    if role_has(role, "members.view"):
        modules.append(_team_module(facility=facility, team_path=team_path))
    if owner:
        modules.append(_recruitment_module(account))
        if verified:
            if kind == "PHARMACY":
                modules.append(_categories_module(facility))
            modules.append(
                _relevant_products(
                    facility,
                    {
                        "HOSPITAL": "equipment_suppliers",
                        "MEDICAL_CENTER": "suppliers",
                        "PHARMACY": "suppliers",
                        "LABORATORY": "lab_supplies",
                        "BEAUTY_CENTER": "equipment_suppliers",
                    }.get(kind, "suppliers"),
                )
            )
            modules.append(_buyer_quotes_module(facility))
        modules += _feeds(account, facility)
    return modules


def _company(account, company: MedicalCompany, role: str, team_path: str) -> list:
    owner = role_has(role, "org.owner_tools")
    retail = company.business_type in RETAIL_BUSINESS_TYPES
    q = "" if owner else f"?company={company.pk}"
    modules = []
    products = Product.objects.filter(company=company)
    if role_has(role, "company.products.view"):
        stats = [
            _stat("verification", company.verification_status),
            _stat("products_total", products.count()),
            _stat("products_active", products.filter(is_active=True).count()),
        ]
        if company.business_type in ("PHARMACEUTICAL_COMPANY", "PHARMA_DISTRIBUTOR"):
            stats.append(_stat("restricted_b2b", products.filter(is_restricted=True).count()))
        stats.append(
            _stat(
                "consumer_listed",
                products.filter(sale_channel__in=["B2C", "BOTH"], is_active=True).count(),
            )
        )
        modules.append(
            _module(
                "catalogue",
                variant=company.business_type,
                stats=stats,
                items=[
                    _item(p.pk, p.title, _money(p.price, p.currency))
                    for p in products.order_by("-created_at")[:LIST_LIMIT]
                ],
                link="/company" if owner else team_path,
            )
        )
        if retail:
            stocked = products.filter(is_active=True, stock_quantity__isnull=False)
            low = stocked.filter(stock_quantity__lte=LOW_STOCK).order_by("stock_quantity")
            modules.append(
                _module(
                    "inventory",
                    stats=[
                        _stat("stocked_products", stocked.count()),
                        _stat("low_stock", low.filter(stock_quantity__gt=0).count()),
                        _stat("out_of_stock", stocked.filter(stock_quantity=0).count()),
                    ],
                    items=[
                        _item(
                            p.pk,
                            p.title,
                            str(p.stock_quantity),
                            "OUT" if p.stock_quantity == 0 else "LOW",
                            "dash.stock",
                        )
                        for p in low[:LIST_LIMIT]
                    ],
                    link="/company" if owner else team_path,
                )
            )
    if retail and role_has(role, "company.orders.view"):
        orders = Order.objects.filter(merchant=company)
        counts = status_counts(orders, "status", OrderStatus.values)
        modules.append(
            _module(
                "store_orders",
                stats=[_stat(f"order_{k.lower()}", v) for k, v in counts["by_status"].items()],
                items=[
                    _item(
                        o.pk,
                        o.number,
                        _money(o.total, o.currency),
                        o.status,
                        "store.orderStatus",
                        f"/merchant/orders{q}",
                    )
                    for o in orders.order_by("-created_at")[:LIST_LIMIT]
                ],
                link=f"/merchant/orders{q}",
            )
        )
    if role_has(role, "company.quotes.view"):
        quotes = QuoteRequest.objects.filter(company=company)
        counts = status_counts(quotes, "status", QuoteStatus.values)
        modules.append(
            _module(
                "quote_requests",
                stats=[
                    _stat("awaiting_reply", counts["by_status"][QuoteStatus.REQUESTED]),
                    _stat("quoted", counts["by_status"][QuoteStatus.QUOTED]),
                    _stat("accepted", counts["by_status"][QuoteStatus.ACCEPTED]),
                ],
                items=[
                    _item(
                        r.pk,
                        r.product.title,
                        r.requester.display_name,
                        r.status,
                        "quotes.status",
                        f"/merchant/quotes{q}",
                    )
                    for r in quotes.select_related("product", "requester").order_by("-created_at")[
                        :LIST_LIMIT
                    ]
                ],
                link=f"/merchant/quotes{q}",
            )
        )
    if role_has(role, "company.campaigns.view"):
        campaigns = AdvertisingCampaign.objects.filter(company=company)
        counts = status_counts(campaigns, "status", CampaignStatus.values)
        today = timezone.localdate()
        live = campaigns.filter(
            status=CampaignStatus.ACTIVE, starts_on__lte=today, ends_on__gte=today
        ).count()
        modules.append(
            _module(
                "campaigns",
                stats=[
                    _stat("live", live),
                    _stat("pending_payment", counts["by_status"][CampaignStatus.PENDING_PAYMENT]),
                    _stat("rejected", counts["by_status"][CampaignStatus.REJECTED]),
                    _stat(
                        "payments_verified",
                        CampaignPayment.objects.filter(
                            campaign__company=company, status="VERIFIED"
                        ).count(),
                    ),
                ],
                items=[
                    _item(c.pk, c.name, f"{c.starts_on} → {c.ends_on}", c.status, "campaignStatus")
                    for c in campaigns.order_by("-created_at")[:LIST_LIMIT]
                ],
                link="/company/advertising" if owner else "",
            )
        )
    if role_has(role, "members.view"):
        modules.append(_team_module(company=company, team_path=team_path))
    if owner:
        modules.append(_recruitment_module(account))
    return modules


def _property(account) -> list:
    seller = RealEstateSeller.objects.filter(account=account).first()
    if seller is None:
        return []
    listings = PropertyListing.objects.filter(seller=seller)
    visible = PropertyListing.objects.publicly_visible().filter(seller=seller).count()
    promos = ListingPromotion.objects.filter(listing__seller=seller).select_related("listing")
    counts = status_counts(promos, "status", PromotionStatus.values)
    return [
        _module(
            "listings",
            stats=[
                _stat(
                    "published",
                    listings.filter(publication_status=PublicationStatus.PUBLISHED).count(),
                ),
                _stat("visible", visible),
                _stat(
                    "drafts", listings.filter(publication_status=PublicationStatus.DRAFT).count()
                ),
            ],
            items=[
                _item(
                    lst.pk,
                    lst.title,
                    lst.district,
                    lst.publication_status,
                    "publicationStatus",
                    f"/real-estate/{lst.pk}",
                )
                for lst in listings.order_by("-created_at")[:LIST_LIMIT]
            ],
            link="/real-estate/owner",
        ),
        _module(
            "promotions",
            stats=[_stat(f"promo_{k.lower()}", v) for k, v in counts["by_status"].items()],
            items=[
                _item(p.pk, p.listing.title, f"{p.days}d", p.status, "promo.status")
                for p in promos.order_by("-created_at")[:LIST_LIMIT]
            ],
            link="/real-estate/owner",
        ),
    ]


def _employer(account, employer_id) -> list:
    membership = (
        EmployerMembership.objects.filter(
            account=account, employer_id=employer_id, status=EmployerMemberStatus.ACTIVE
        )
        .select_related("employer")
        .first()
    )
    if membership is None:
        return []
    summary = recruiter_services.recruiter_summary(membership)
    modules = [
        _module(
            "jobs",
            stats=[
                _stat("open_jobs", summary["jobs"]["open_now"]),
                _stat(
                    "pending_review", summary["jobs"]["by_status"][JobStatus.PENDING_ADMIN_REVIEW]
                ),
                _stat("jobs_total", summary["jobs"]["total"]),
            ],
            items=[
                _item(j.pk, j.title, "", j.status, "jobStatus", f"/employer/jobs/{j.pk}")
                for j in JobPost.objects.filter(employer=membership.employer).order_by(
                    "-created_at"
                )[:LIST_LIMIT]
            ],
            link="/employer",
        )
    ]
    if summary["applications"] is not None:
        modules.append(
            _module(
                "applicants",
                stats=[
                    _stat("awaiting_review", summary["applications"]["awaiting_review"]),
                    _stat("last_7_days", summary["applications"]["last_7_days"]),
                    _stat("total", summary["applications"]["total"]),
                ],
                link="/employer",
            )
        )
        modules.append(
            _module(
                "interviews",
                stats=[
                    _stat(f"interview_{k.lower()}", v)
                    for k, v in summary["interviews"]["by_status"].items()
                ],
                link="/employer",
            )
        )
    else:
        modules.append(
            _module("applicants", stats=[_stat("access", summary["applications_access"])])
        )
    invitations = JobInvitation.objects.filter(employer=membership.employer)
    modules.append(
        _module(
            "invitations",
            stats=[
                _stat("pending", invitations.filter(status=InvitationStatus.PENDING).count()),
                _stat("accepted", invitations.filter(status=InvitationStatus.ACCEPTED).count()),
            ],
            link="/employer/talent",
        )
    )
    ent = jobs_services.employer_entitlements(membership.employer)
    modules.append(
        _module(
            "subscription",
            stats=[
                _stat("plan", getattr(ent.plan, "code", "") if ent.plan else ""),
                _stat("subscription", ent.subscription.status if ent.subscription else "NONE"),
                _stat("seats_used", summary["seats"]["active_members"]),
                _stat("seats_limit", summary["seats"]["limit"]),
            ],
            link="/employer",
        )
    )
    return modules


def _job_seeker(account) -> list:
    profile = JobSeekerProfile.objects.filter(account=account).first()
    if profile is None:
        return []
    applications = JobApplication.objects.filter(job_seeker=profile).select_related("job")
    counts = status_counts(applications, "status", ApplicationStatus.values)
    interviews = InterviewRequest.objects.filter(application__job_seeker=profile)
    invitations = JobInvitation.objects.filter(job_seeker=profile).select_related("job")
    relevant = (
        JobPost.objects.public()
        .filter(profession=profile.profession)
        .exclude(applications__job_seeker=profile)
        .select_related("employer")
        .order_by("-published_at")
    )
    return [
        _module(
            "resume",
            variant=profile.profession,
            stats=[
                _stat("profession", profile.profession),
                _stat("years_of_experience", profile.years_of_experience),
                _stat("discoverable", profile.discoverable_by_employers),
            ],
            link="/jobs/profile",
        ),
        _module(
            "applications",
            stats=[
                _stat("total", counts["total"]),
                _stat(
                    "in_review",
                    counts["by_status"][ApplicationStatus.REVIEWING]
                    + counts["by_status"][ApplicationStatus.SHORTLISTED],
                ),
                _stat("interview", counts["by_status"][ApplicationStatus.INTERVIEW]),
            ],
            items=[
                _item(a.pk, a.job.title, "", a.status, "applicationStatus", "/jobs/my-applications")
                for a in applications.order_by("-created_at")[:LIST_LIMIT]
            ],
            link="/jobs/my-applications",
        ),
        _module(
            "interviews",
            stats=[
                _stat("proposed", interviews.filter(status=InterviewStatus.PROPOSED).count()),
                _stat("accepted", interviews.filter(status=InterviewStatus.ACCEPTED).count()),
            ],
            link="/jobs/my-applications",
        ),
        _module(
            "invitations",
            stats=[_stat("pending", invitations.filter(status=InvitationStatus.PENDING).count())],
            items=[
                _item(i.pk, i.job.title, "", i.status, "invitationStatus", f"/jobs/{i.job_id}")
                for i in invitations.order_by("-created_at")[:LIST_LIMIT]
            ],
            link="/jobs/my-applications",
        ),
        _module(
            "relevant_jobs",
            variant=profile.profession,
            stats=[_stat("open_matching", relevant.count())],
            items=[
                _item(j.pk, j.title, j.employer.name, path=f"/jobs/{j.pk}")
                for j in relevant[:LIST_LIMIT]
            ],
            link=f"/jobs?profession={profile.profession}",
        ),
    ]


def _patient(account) -> list:
    orders = Order.objects.filter(buyer=account)
    counts = status_counts(orders, "status", OrderStatus.values)
    open_orders = sum(
        counts["by_status"][s]
        for s in (OrderStatus.PLACED, OrderStatus.CONFIRMED, OrderStatus.SHIPPED)
    )
    modules = [
        _module(
            "my_orders",
            stats=[
                _stat("open_orders", open_orders),
                _stat("order_delivered", counts["by_status"][OrderStatus.DELIVERED]),
                _stat("total", counts["total"]),
            ],
            items=[
                _item(
                    o.pk,
                    o.number,
                    _money(o.total, o.currency),
                    o.status,
                    "store.orderStatus",
                    "/orders",
                )
                for o in orders.order_by("-created_at")[:LIST_LIMIT]
            ],
            link="/orders",
        )
    ]
    if reservations_enabled():
        summary = reservation_services.patient_summary(account)
        modules.append(
            _module(
                "reservations",
                variant="patient",
                stats=[
                    _stat("upcoming", summary["reservations"]["upcoming"]),
                    _stat("total", summary["reservations"]["total"]),
                ],
                items=[
                    _item(
                        r["id"],
                        r["provider_name_snapshot"],
                        r["starts_at"].isoformat(),
                        r["status"],
                        "reservationStatus",
                        "/reservations",
                    )
                    for r in summary["upcoming"]
                ],
                link="/reservations",
            )
        )
    store = Product.objects.consumer_store().filter(stock_quantity__gt=0).select_related("company")
    modules.append(
        _module(
            "store",
            stats=[_stat("available_products", store.count())],
            items=[
                _item(p.pk, p.title, _money(p.price, p.currency), path="/store")
                for p in store.order_by("title")[:4]
            ],
            link="/store",
        )
    )
    modules.append(
        _module(
            "my_reviews",
            stats=[_stat("review_count", Review.objects.filter(patient=account).count())],
            link="/reservations" if reservations_enabled() else "",
        )
    )
    return modules


def _admin() -> list:
    summary = admin_services.admin_summary()
    providers_pending = ProviderProfile.objects.filter(
        verification_status=VerificationStatus.PENDING
    ).count()
    companies_pending = MedicalCompany.objects.filter(
        verification_status=CompanyVerificationStatus.PENDING
    ).count()
    return [
        _module(
            "verification",
            stats=[
                _stat("providers_pending", providers_pending),
                _stat("companies_pending", companies_pending),
                _stat(
                    "employers_pending", summary["employers"]["by_verification"].get("PENDING", 0)
                ),
            ],
            link="/admin-console",
        ),
        _module(
            "moderation",
            stats=[
                _stat(
                    "jobs_pending_review",
                    summary["jobs"]["by_status"][JobStatus.PENDING_ADMIN_REVIEW],
                ),
                _stat(
                    "promotions_requested",
                    ListingPromotion.objects.filter(status=PromotionStatus.REQUESTED).count(),
                ),
                _stat("recruitment_suspended", summary["employers"]["recruitment_suspended"]),
            ],
            link="/admin-console?tab=jobs",
        ),
        _module(
            "campaigns_admin",
            stats=[
                _stat(
                    "pending_payment",
                    summary["advertising"]["campaigns_by_status"][CampaignStatus.PENDING_PAYMENT],
                ),
                _stat("live", summary["advertising"]["campaigns_by_status"][CampaignStatus.ACTIVE]),
            ],
            link="/admin-console?tab=advertising",
        ),
        _module(
            "subscriptions",
            stats=[
                _stat(f"sub_{k.lower()}", v)
                for k, v in summary["billing"]["subscriptions_by_status"].items()
            ],
            link="/admin-console?tab=subscriptions",
        ),
        _module(
            "users",
            stats=[
                _stat("accounts_active", summary["accounts"]["active"]),
                _stat("accounts_inactive", summary["accounts"]["inactive"]),
                *[_stat(f"role_{k.lower()}", v) for k, v in summary["accounts"]["by_role"].items()],
            ],
        ),
        _module(
            "audit",
            stats=[
                _stat("last_24_hours", summary["audit"]["last_24_hours"]),
                _stat("last_7_days", summary["audit"]["last_7_days"]),
            ],
        ),
    ]


# ---- actions ----------------------------------------------------------------------------------


def _actions(ws: dict, account) -> list[dict]:
    kind, role = ws["kind"], ws.get("role")
    out: list[tuple[str, str]] = []
    if kind == "patient":
        out = [("store", "/store"), ("my_orders", "/orders"), ("find_providers", "/providers")]
        if reservations_enabled():
            out.append(("my_reservations", "/reservations"))
    elif kind == "practitioner":
        out = [("edit_profile", "/provider/profile"), ("offers", "/provider/offers")]
        if reservations_enabled():
            out.append(("appointments", "/provider/reservations"))
        out.append(("marketplace", "/marketplace"))
    elif kind == "facility":
        if role_has(role, "org.owner_tools"):
            out = [
                ("edit_profile", "/provider/profile"),
                ("offers", "/provider/offers"),
                ("team", ws["team_path"]),
                ("recruitment", "/employer"),
                ("marketplace", "/marketplace"),
            ]
        else:
            out = [("open_workspace", ws["team_path"])]
    elif kind == "company":
        q = "" if role_has(role, "org.owner_tools") else f"?company={ws['org_id']}"
        if role_has(role, "org.owner_tools"):
            out = [("products", "/company"), ("advertising", "/company/advertising")]
        if ws["subtype"] in RETAIL_BUSINESS_TYPES and role_has(role, "company.orders.view"):
            out.append(("store_orders", f"/merchant/orders{q}"))
        if role_has(role, "company.quotes.view"):
            out.append(("quote_requests", f"/merchant/quotes{q}"))
        out.append(("team", ws["team_path"]))
    elif kind == "property":
        out = [("listings", "/real-estate/owner")]
    elif kind == "employer":
        out = [
            ("employer", "/employer"),
            ("new_job", "/employer/jobs/new"),
            ("talent", "/employer/talent"),
        ]
    elif kind == "job_seeker":
        out = [
            ("resume", "/jobs/profile"),
            ("find_jobs", "/jobs"),
            ("my_applications", "/jobs/my-applications"),
        ]
    elif kind == "admin":
        out = [
            ("admin_console", "/admin-console"),
            ("promotions_review", "/admin-console?tab=promotions"),
        ]
    return [{"key": k, "path": p} for k, p in out if p]


# ---- entry point ------------------------------------------------------------------------------


def default_workspace(workspaces: list[dict], account) -> dict | None:
    """Staff land in their assigned workspace: a personal account with an active organization
    membership opens that organization first; everyone else opens their own primary one."""
    if not workspaces:
        return None
    if account.role == "PATIENT":
        for ws in workspaces:
            if ws["kind"] in ("facility", "company") and ws.get("role") != "OWNER":
                return ws
    return workspaces[0]


def compose(account: Account, ws_id: str | None) -> dict | None:
    """The dashboard for one of the caller's CURRENT workspaces, or None (unknown/forged id)."""
    workspaces = services.build_workspaces(account)
    if ws_id:
        ws = next((w for w in workspaces if w["id"] == ws_id), None)
    else:
        ws = default_workspace(workspaces, account)
    if ws is None:
        return None
    kind, role = ws["kind"], ws.get("role")
    modules: list = []
    if kind == "patient":
        modules = _patient(account)
    elif kind == "practitioner":
        profile = ProviderProfile.objects.filter(account=account).first()
        modules = _practitioner(account, profile) if profile else []
    elif kind == "facility":
        facility = ProviderProfile.objects.get(pk=ws["org_id"])
        modules = _facility(account, facility, role, ws["team_path"])
    elif kind == "company":
        company = MedicalCompany.objects.get(pk=ws["org_id"])
        modules = _company(account, company, role, ws["team_path"])
    elif kind == "property":
        modules = _property(account)
    elif kind == "employer":
        modules = _employer(account, ws["id"].split(":", 1)[1])
    elif kind == "job_seeker":
        modules = _job_seeker(account)
    elif kind == "admin":
        modules = _admin()
    modules = [m for m in modules if m is not None]
    modules += [_notifications(account), _account_settings()]
    return {
        "workspace": {
            key: ws.get(key)
            for key in ("id", "kind", "subtype", "title", "role", "verification_status", "org_id")
        },
        "header": {
            "name": account.full_name,
            "since": account.created_at.date().isoformat(),
            "reservations_enabled": reservations_enabled(),
        },
        "actions": _actions(ws, account),
        "modules": modules,
        "generated_at": timezone.now().isoformat(),
    }
