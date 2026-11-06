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

The package splits the composer by concern:

* ``primitives`` — payload building blocks (serialization);
* ``modules`` — reusable modules and setup steps (aggregation);
* ``builders`` — which modules each workspace kind gets (composition);
* this module — actions, the default workspace and ``compose`` (policy).
"""

from __future__ import annotations

from django.utils import timezone

from apps.accounts.models import Account
from apps.core.features import reservations_enabled
from apps.marketplace.models import MedicalCompany
from apps.marketplace.types import RETAIL_BUSINESS_TYPES
from apps.providers.models import ProviderProfile
from apps.providers.types import VerificationStatus

from .. import services
from ..types import role_has
from .builders import (
    _admin,
    _company,
    _employer,
    _facility,
    _job_seeker,
    _patient,
    _practitioner,
    _property,
)
from .modules import _account_settings, _notifications, _setup


def _actions(ws: dict, account) -> list[dict]:
    kind, role = ws["kind"], ws.get("role")
    out: list[tuple[str, str]] = []
    verified = ws.get("verification_status") == VerificationStatus.VERIFIED
    if kind == "setup":
        out = [("complete_setup", ws["path"])]
    elif kind == "patient":
        out = [("store", "/store"), ("my_orders", "/orders"), ("find_providers", "/providers")]
        if reservations_enabled():
            out.append(("my_reservations", "/reservations"))
    elif kind == "practitioner":
        out = [("edit_profile", "/provider/profile"), ("offers", "/provider/offers")]
        if reservations_enabled():
            out.append(("appointments", "/provider/reservations"))
        if verified:  # the B2B catalogue is for verified providers only
            out.append(("marketplace", "/marketplace"))
    elif kind == "facility":
        if role_has(role, "org.owner_tools"):
            out = [
                ("edit_profile", "/provider/profile"),
                ("offers", "/provider/offers"),
                ("team", ws["team_path"]),
                ("recruitment", "/employer"),
            ]
            if verified:
                out.append(("marketplace", "/marketplace"))
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
        out = [("listings", "/real-estate/owner"), ("inquiries", "/real-estate/owner/inquiries")]
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
        # Registered to hire or to find work: open that workspace (or its setup step) first.
        wanted = {"EMPLOYER": "employer", "JOB_SEEKER": "job_seeker"}.get(account.account_type)
        for ws in workspaces:
            if ws["kind"] == wanted or (wanted and ws["kind"] == "setup"):
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
    if kind == "setup":
        modules = _setup(account)
    elif kind == "patient":
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
