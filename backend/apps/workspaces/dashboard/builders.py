"""Per-workspace-kind builders: which modules a practitioner, facility, company, property
seller, employer, job seeker, patient or administrator sees. Every number is a real query."""

from __future__ import annotations

from django.utils import timezone

from apps.advertising.models import AdvertisingCampaign, CampaignPayment
from apps.advertising.types import CampaignStatus
from apps.commerce.models import Order, QuoteRequest
from apps.commerce.types import OrderStatus, QuoteStatus
from apps.core.features import reservations_enabled
from apps.dashboards.services import admin as admin_services
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
from apps.marketplace.models import MedicalCompany, Product
from apps.marketplace.types import RETAIL_BUSINESS_TYPES, CompanyVerificationStatus
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus
from apps.real_estate.models import ListingPromotion, PropertyListing, RealEstateSeller
from apps.real_estate.types import PromotionStatus, PublicationStatus
from apps.reviews.models import Review

from ..types import role_has
from .modules import (
    _buyer_quotes_module,
    _categories_module,
    _connections_module,
    _feeds,
    _offers_module,
    _practitioners_module,
    _profile_module,
    _provider_setup,
    _recruitment_module,
    _relevant_products,
    _reservations_module,
    _reviews_module,
    _services_module,
    _team_module,
)
from .primitives import LIST_LIMIT, LOW_STOCK, _item, _module, _money, _stat

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
        _provider_setup(profile),
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
    modules = [
        _provider_setup(facility) if owner else None,
        _profile_module(facility, edit_path="/provider/profile" if owner else team_path),
    ]
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
    if retail and role_has(role, "company.finance.view"):
        from apps.ledger import settlement
        from apps.ledger.models import SettlementBatch

        statement = settlement.statement(company.pk)
        earned = statement["commission"] - statement["refunded_commission"]
        modules.append(
            _module(
                "store_finance",
                stats=[
                    _stat("completed_sales", _money(statement["merchandise_net"], "IQD")),
                    _stat("racheeta_commission", _money(earned, "IQD")),
                    _stat("owed_to_you", _money(statement["payable"], "IQD")),
                    _stat("paid_out", _money(statement["paid_out"], "IQD")),
                    _stat("awaiting_completion", statement["pending_orders"]),
                ],
                items=[
                    _item(
                        b.pk,
                        _money(b.amount, b.currency),
                        b.reference_note,
                        b.status,
                        "market.settlementStatus",
                        f"/merchant/center?tab=finance{'&' + q[1:] if q else ''}",
                    )
                    for b in SettlementBatch.objects.filter(company=company)[:LIST_LIMIT]
                ],
                link=f"/merchant/center?tab=finance{'&' + q[1:] if q else ''}",
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
        _inquiries_module(seller),
    ]


def _inquiries_module(seller) -> dict:
    """Real counts and the newest live inquiries about this seller's listings (Phase E)."""
    from apps.real_estate.inquiries import owner_counts
    from apps.real_estate.models import ListingInquiry
    from apps.real_estate.types import LIVE_INQUIRY_STATUSES

    counts = owner_counts(seller)
    live = (
        ListingInquiry.objects.filter(listing__seller=seller, status__in=LIVE_INQUIRY_STATUSES)
        .select_related("inquirer")
        .order_by("-created_at")[:LIST_LIMIT]
    )
    return _module(
        "inquiries",
        stats=[
            _stat("inquiries_open", counts["inquiries_open"]),
            _stat("inquiries_answered", counts["inquiries_answered"]),
            _stat("total", counts["inquiries_total"]),
        ],
        items=[
            _item(
                i.pk,
                i.listing_title_snapshot,
                i.inquirer.full_name,
                i.status,
                "inquiries.status",
                "/real-estate/owner/inquiries",
            )
            for i in live
        ],
        link="/real-estate/owner/inquiries",
    )


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
