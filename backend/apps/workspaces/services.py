"""Workspace descriptors and organization membership writes."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.audit import services as audit
from apps.jobs.models import EmployerMembership, JobSeekerProfile
from apps.jobs.types import MemberStatus as EmployerMemberStatus
from apps.marketplace.models import MedicalCompany
from apps.marketplace.types import RETAIL_BUSINESS_TYPES
from apps.providers.models import ProviderProfile
from apps.providers.types import FACILITY_TYPES, PRACTITIONER_TYPES

from .models import OrganizationMember
from .types import CAPABILITIES, GRANTABLE_ROLES, MemberStatus, OrgRole

PRACTITIONER_MODULES = (
    "profile",
    "services",
    "availability",
    "reservations",
    "reviews",
    "offers",
    "memberships",
    "catalogue",
    "sponsored",
    "quotes",
    "messages",
)
FACILITY_OWNER_MODULES = (
    "profile",
    "services",
    "availability",
    "reservations",
    "reviews",
    "offers",
    "practitioners",
    "staff",
    "catalogue",
    "sponsored",
    "quotes",
    "recruitment",
    "messages",
)


class MembershipError(Exception):
    code = "membership_error"


def capabilities_of(role: str) -> list[str]:
    return sorted(code for code, roles in CAPABILITIES.items() if role in roles)


def _descriptor(**fields) -> dict:
    """`id` is unique per workspace ("<kind>:<pk>"); `org_id` is the organization's own id for
    facility/company workspaces (what `/workspaces/<kind>/<org_id>` expects); `team_path` opens
    the staff workspace (reservations, orders, team) when the role can use one."""
    fields.setdefault("role", OrgRole.OWNER)
    fields.setdefault("org_id", None)
    fields.setdefault("team_path", None)
    fields.setdefault("verification_status", "")
    fields.setdefault("subtype", "")
    fields.setdefault("modules", [])
    return fields


def build_workspaces(account) -> list[dict]:
    """Every workspace this account may open RIGHT NOW (server-computed; the client only renders).

    Order: personal identity first, then organizations owned, then memberships, then optional
    profiles (job seeker), then administration.
    """
    out: list[dict] = []
    if account.role == AccountRole.PATIENT:
        out.append(
            _descriptor(
                id="personal",
                kind="patient",
                title=account.full_name,
                path="/dashboard",
                modules=["search", "reservations", "reviews", "store", "orders", "messages"],
            )
        )
    profile = ProviderProfile.objects.filter(account=account).first()
    if profile and account.role == AccountRole.PROVIDER:
        if profile.provider_type in PRACTITIONER_TYPES:
            out.append(
                _descriptor(
                    id=f"practitioner:{profile.pk}",
                    kind="practitioner",
                    subtype=profile.provider_type,
                    title=profile.display_name,
                    path="/dashboard",
                    verification_status=profile.verification_status,
                    modules=list(PRACTITIONER_MODULES),
                )
            )
        elif profile.provider_type in FACILITY_TYPES:
            out.append(
                _descriptor(
                    id=f"facility:{profile.pk}",
                    org_id=str(profile.pk),
                    team_path=f"/workspace/facility/{profile.pk}",
                    kind="facility",
                    subtype=profile.provider_type,
                    title=profile.display_name,
                    path="/dashboard",
                    verification_status=profile.verification_status,
                    modules=list(FACILITY_OWNER_MODULES),
                )
            )
    company = MedicalCompany.objects.filter(account=account).first()
    if company and account.role == AccountRole.MEDICAL_COMPANY:
        modules = ["profile", "products", "advertising", "quotes", "staff", "recruitment"]
        if company.business_type in RETAIL_BUSINESS_TYPES:
            modules.insert(2, "store_orders")
        out.append(
            _descriptor(
                id=f"company:{company.pk}",
                org_id=str(company.pk),
                team_path=f"/workspace/company/{company.pk}",
                kind="company",
                subtype=company.business_type,
                title=company.name,
                path="/company",
                verification_status=company.verification_status,
                modules=modules,
            )
        )
    if account.role == AccountRole.REAL_ESTATE_SELLER and hasattr(account, "real_estate_seller"):
        seller = account.real_estate_seller
        out.append(
            _descriptor(
                id=f"property:{seller.pk}",
                kind="property",
                subtype=seller.seller_type,
                title=seller.display_name,
                path="/real-estate/owner",
                modules=["listings", "promotions"],
            )
        )
    members = (
        OrganizationMember.objects.filter(account=account, status=MemberStatus.ACTIVE)
        .select_related("facility", "facility__account", "company", "company__account")
        .order_by("created_at")
    )
    for member in members:
        if member.facility_id and member.facility.account.is_active:
            out.append(
                _descriptor(
                    id=f"facility:{member.facility_id}",
                    org_id=str(member.facility_id),
                    team_path=f"/workspace/facility/{member.facility_id}",
                    kind="facility",
                    subtype=member.facility.provider_type,
                    title=member.facility.display_name,
                    role=member.role,
                    path=f"/workspace/facility/{member.facility_id}",
                    verification_status=member.facility.verification_status,
                    modules=["reservations"]
                    + (["staff"] if member.role == OrgRole.MANAGER else []),
                )
            )
        elif member.company_id and member.company.account.is_active:
            modules = ["store_orders", "quotes"]
            out.append(
                _descriptor(
                    id=f"company:{member.company_id}",
                    org_id=str(member.company_id),
                    team_path=f"/workspace/company/{member.company_id}",
                    kind="company",
                    subtype=member.company.business_type,
                    title=member.company.name,
                    role=member.role,
                    path=f"/workspace/company/{member.company_id}",
                    verification_status=member.company.verification_status,
                    modules=modules,
                )
            )
    for membership in (
        EmployerMembership.objects.filter(account=account, status=EmployerMemberStatus.ACTIVE)
        .select_related("employer")
        .order_by("created_at")
    ):
        out.append(
            _descriptor(
                id=f"employer:{membership.employer_id}",
                kind="employer",
                subtype=membership.employer.organization_type,
                title=membership.employer.name,
                role=membership.role,
                path="/employer",
                verification_status=membership.employer.verification_status,
                modules=["jobs", "applicants", "talent", "team"],
            )
        )
    if JobSeekerProfile.objects.filter(account=account).exists():
        out.append(
            _descriptor(
                id="job_seeker",
                kind="job_seeker",
                title=account.full_name,
                path="/jobs/profile",
                modules=["resume", "applications", "invitations"],
            )
        )
    if account.is_staff:
        out.append(
            _descriptor(
                id="admin",
                kind="admin",
                title="Racheeta",
                path="/admin-console",
                modules=["verification", "moderation", "billing", "advertising", "audit"],
            )
        )
    # An account whose role needs a profile it has not created yet gets ONE setup workspace,
    # so its dashboard always opens (on the next step) instead of erroring.
    setup_path = {
        AccountRole.PROVIDER: ("/provider/profile", profile is None),
        AccountRole.MEDICAL_COMPANY: ("/company", company is None),
        AccountRole.REAL_ESTATE_SELLER: (
            "/real-estate/owner",
            not hasattr(account, "real_estate_seller"),
        ),
    }.get(account.role)
    if setup_path and setup_path[1]:
        out.insert(
            0,
            _descriptor(
                id="setup",
                kind="setup",
                subtype=account.account_type or account.role,
                title=account.full_name,
                path=setup_path[0],
                modules=["setup"],
            ),
        )
    for item in out:
        item["capabilities"] = (
            capabilities_of(item["role"]) if item["kind"] in ("facility", "company") else []
        )
    return out


# ---- membership management (owner only, per CAPABILITIES["members.manage"]) ----------------------


@transaction.atomic
def add_member(*, actor, org_kind: str, org_id, email: str, role: str) -> OrganizationMember:
    if role not in GRANTABLE_ROLES:
        raise MembershipError("Choose manager, staff or viewer.")
    target = Account.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if target is None:
        raise MembershipError("No active account uses this e-mail address.")
    if target.is_staff:
        raise MembershipError("Administrators cannot be added to an organization.")
    if org_kind == "facility":
        org = ProviderProfile.objects.get(pk=org_id)
        if target.pk == org.account_id:
            raise MembershipError("The owner is already part of this organization.")
        fields = {"facility": org}
    else:
        org = MedicalCompany.objects.get(pk=org_id)
        if target.pk == org.account_id:
            raise MembershipError("The owner is already part of this organization.")
        fields = {"company": org}
    try:
        with transaction.atomic():
            member = OrganizationMember.objects.create(
                account=target, role=role, added_by=actor, **fields
            )
    except IntegrityError as exc:
        raise MembershipError("This person is already an active member.") from exc
    audit.record(actor=actor, action="workspaces.member.added", target=member, summary=role)
    return member


@transaction.atomic
def end_member(*, actor, org_kind: str, org_id, member_id) -> OrganizationMember:
    scope = {"facility_id": org_id} if org_kind == "facility" else {"company_id": org_id}
    member = (
        OrganizationMember.objects.select_for_update()
        .filter(pk=member_id, status=MemberStatus.ACTIVE, **scope)
        .first()
    )
    if member is None:
        raise MembershipError("Membership not found.")
    member.status = MemberStatus.ENDED
    member.ended_at = timezone.now()
    member.save(update_fields=["status", "ended_at", "updated_at"])
    audit.record(actor=actor, action="workspaces.member.ended", target=member, summary=member.role)
    return member
