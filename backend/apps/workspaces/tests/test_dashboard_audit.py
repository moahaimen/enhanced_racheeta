"""Functional audit of the specialized dashboards (docs/DASHBOARD_AUDIT.md).

The composer refactor kept 233/233 payloads identical, which proves equivalence, not completeness.
This file pins the REQUIRED primary actions of every profession, booking ON and OFF, and the gaps
the audit closed:

* a B2B-only seller (scientific office, pharmaceutical company...) reaches the orders its accepted
  quotes became and its commission statement (it had neither on its dashboard);
* finance staff reach the marketplace finance console from their dashboard;
* anyone who asked about a property (patient, practitioner, facility or company owner) reaches
  their own inquiries; organization staff never see the owner's personal inquiries.
"""

import pytest
from django.contrib.auth.models import Permission

from apps.accounts.roles import AccountRole
from apps.jobs import services as jobs_services
from apps.jobs.models import JobSeekerProfile
from apps.ledger.settlement import FINANCE_PERMISSION
from apps.marketplace.types import BusinessType
from apps.providers.types import ProviderType
from apps.real_estate import inquiries
from apps.real_estate.models import PropertyListing, RealEstateSeller
from apps.real_estate.types import PublicationStatus
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

URL = "/api/v1/workspaces/dashboard"


@pytest.fixture(params=[True, False], ids=["booking-on", "booking-off"])
def booking(request, settings):
    settings.RACHEETA = {**settings.RACHEETA, "RESERVATIONS_ENABLED": request.param}
    return request.param


def _dash(account, ws=None):
    response = client_for(account).get(URL, {"ws": ws} if ws else {})
    assert response.status_code == 200, response.content
    return response.json()


def _actions(payload) -> list[str]:
    return [a["key"] for a in payload["actions"]]


def _modules(payload) -> dict:
    return {m["key"]: m for m in payload["modules"]}


# ---- required actions per profession ----------------------------------------------------------

PRACTITIONERS = {
    ProviderType.DOCTOR: {"reviews", "services", "products", "my_quotes", "offers", "profile"},
    ProviderType.NURSE: {"connections", "services", "products", "my_quotes", "offers", "profile"},
    ProviderType.THERAPIST: {"reviews", "services", "products", "my_quotes", "offers", "profile"},
}


@pytest.mark.parametrize("ptype", sorted(PRACTITIONERS))
def test_practitioner_actions_and_modules(provider_factory, booking, ptype):
    provider = provider_factory(provider_type=ptype)
    payload = _dash(provider.account)
    assert payload["workspace"]["kind"] == "practitioner"
    expected = ["edit_profile", "offers"] + (["appointments"] if booking else []) + ["marketplace"]
    assert _actions(payload) == expected
    assert PRACTITIONERS[ptype] <= set(_modules(payload))


def test_an_unverified_practitioner_has_no_marketplace(provider_factory):
    provider = provider_factory(provider_type=ProviderType.DOCTOR, verification_status="PENDING")
    assert "marketplace" not in _actions(_dash(provider.account))


FACILITIES = {
    ProviderType.HOSPITAL: ("departments", {"practitioners"}),
    ProviderType.MEDICAL_CENTER: ("clinics", {"practitioners"}),
    ProviderType.LABORATORY: ("lab_tests", set()),
    ProviderType.BEAUTY_CENTER: ("aesthetic", set()),
    ProviderType.PHARMACY: (None, {"categories"}),
}


@pytest.mark.parametrize("ftype", sorted(FACILITIES))
def test_facility_owner_actions_and_modules(provider_factory, booking, ftype):
    facility = provider_factory(provider_type=ftype)
    payload = _dash(facility.account, f"facility:{facility.pk}")
    assert _actions(payload) == ["edit_profile", "offers", "team", "recruitment", "marketplace"]
    modules = _modules(payload)
    services_variant, extra = FACILITIES[ftype]
    if services_variant:
        assert modules["services"]["variant"] == services_variant
    else:
        assert "services" not in modules  # a pharmacy sells; its catalogue is its store
    assert extra | {"profile", "offers", "team", "recruitment", "products", "my_quotes"} <= set(
        modules
    )
    assert modules["offers"]["variant"] == ("promotions" if ftype == "BEAUTY_CENTER" else "offers")
    assert ("reservations" in modules) == (booking and ftype != "PHARMACY")


def test_employer_job_seeker_and_property_owner_actions(account_factory, baghdad):
    owner = account_factory(role=AccountRole.PATIENT, account_type="EMPLOYER")
    employer = jobs_services.create_employer(
        owner, name="Fictional Software Co", organization_type="BUSINESS", governorate=baghdad
    )
    assert _actions(_dash(owner, f"employer:{employer.pk}")) == ["employer", "new_job", "talent"]

    seeker = account_factory(role=AccountRole.PATIENT, account_type="JOB_SEEKER")
    JobSeekerProfile.objects.create(
        account=seeker, professional_title="Data analyst", profession="DATA_ANALYST",
        degree="BACHELOR", governorate=baghdad, years_of_experience=2,
    )  # fmt: skip
    assert _actions(_dash(seeker)) == ["resume", "find_jobs", "my_applications"]

    seller_account = account_factory(role=AccountRole.REAL_ESTATE_SELLER)
    RealEstateSeller.objects.create(
        account=seller_account, seller_type="OWNER", display_name="Fictional owner"
    )
    payload = _dash(seller_account)
    assert _actions(payload) == ["listings", "inquiries"]
    assert {"listings", "promotions", "inquiries"} <= set(_modules(payload))


# ---- gap 1: B2B-only sellers reach their orders and commission statement -----------------------


@pytest.mark.parametrize(
    "business_type",
    [
        BusinessType.SCIENTIFIC_OFFICE,
        BusinessType.PHARMACEUTICAL_COMPANY,
        BusinessType.PHARMA_DISTRIBUTOR,
        BusinessType.MEDICAL_COMPANY,
    ],
)
def test_a_b2b_only_seller_reaches_its_quote_orders_and_statement(company_factory, business_type):
    company = company_factory(business_type=business_type)
    payload = _dash(company.account)
    expected = ["products", "advertising", "store_orders", "quote_requests", "team"]
    assert _actions(payload) == expected
    modules = _modules(payload)
    assert modules["store_orders"]["variant"] == "b2b"
    assert modules["store_orders"]["link"] == "/merchant/orders"
    assert "store_finance" in modules and "inventory" not in modules
    # the orders page itself accepts this seller
    assert client_for(company.account).get("/api/v1/merchant/orders").status_code == 200


def test_b2b_seller_staff_see_orders_only_with_the_permission(account_factory, company_factory):
    company = company_factory(business_type=BusinessType.SCIENTIFIC_OFFICE)
    editor = account_factory(role=AccountRole.PATIENT)
    viewer = account_factory(role=AccountRole.PATIENT)
    for account, role in ((editor, "PRODUCT_EDITOR"), (viewer, "VIEWER")):
        OrganizationMember.objects.create(
            account=account, company=company, role=role, added_by=company.account
        )
    ws = f"company:{company.pk}"
    assert "store_orders" not in _actions(_dash(editor, ws))
    assert "store_orders" not in _modules(_dash(editor, ws))
    viewer_payload = _dash(viewer, ws)
    orders = _modules(viewer_payload)["store_orders"]
    assert orders["link"] == f"/merchant/orders?company={company.pk}"
    assert "store_finance" not in _modules(viewer_payload)  # finance is not a viewer capability


# ---- gap 2: finance staff reach the finance console --------------------------------------------


def test_only_finance_staff_get_the_finance_console_action(account_factory):
    support = account_factory(role=AccountRole.PATIENT)
    finance = account_factory(role=AccountRole.PATIENT)
    for staff in (support, finance):
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
    app_label, codename = FINANCE_PERMISSION.split(".")
    finance.user_permissions.add(
        Permission.objects.get(content_type__app_label=app_label, codename=codename)
    )
    assert "marketplace_finance" not in _actions(_dash(support, "admin"))
    finance_actions = _actions(_dash(finance, "admin"))
    assert finance_actions[-1] == "marketplace_finance"
    assert {a["key"]: a["path"] for a in _dash(finance, "admin")["actions"]}[
        "marketplace_finance"
    ] == "/admin-finance"


# ---- gap 3: askers reach their own property inquiries ------------------------------------------


@pytest.fixture
def listing(account_factory, baghdad):
    seller = RealEstateSeller.objects.create(
        account=account_factory(role=AccountRole.REAL_ESTATE_SELLER),
        seller_type="OWNER", display_name="Fictional owner",
    )  # fmt: skip
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    return PropertyListing.objects.create(
        seller=seller, title="Clinic for rent (demo)", property_type="CLINIC",
        transaction_type="RENT", governorate=baghdad, area_sqm=Decimal("60"),
        publication_status=PublicationStatus.PUBLISHED, published_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
    )  # fmt: skip


def _ask(account, listing):
    return inquiries.create_inquiry(
        account, listing.pk, message="Is the clinic available next month?", share_contact=False
    )


def test_a_patient_sees_their_inquiries_only_after_asking(buyer, listing):
    assert "my_inquiries" not in _actions(_dash(buyer))
    assert "my_inquiries" not in _modules(_dash(buyer))
    _ask(buyer, listing)
    payload = _dash(buyer)
    assert "my_inquiries" in _actions(payload)
    module = _modules(payload)["my_inquiries"]
    assert module["link"] == "/real-estate/inquiries"
    assert {s["key"]: s["value"] for s in module["stats"]} == {
        "inquiries_open": 1, "inquiries_answered": 0, "total": 1,
    }  # fmt: skip
    assert module["items"][0]["title"] == "Clinic for rent (demo)"


@pytest.mark.parametrize("ptype", [ProviderType.DOCTOR, ProviderType.MEDICAL_CENTER])
def test_practitioners_and_facility_owners_see_their_own_inquiries(
    provider_factory, listing, ptype
):
    provider = provider_factory(provider_type=ptype)
    _ask(provider.account, listing)
    kind = "practitioner" if ptype == ProviderType.DOCTOR else "facility"
    payload = _dash(provider.account, f"{kind}:{provider.pk}" if kind == "facility" else None)
    assert "my_inquiries" in _actions(payload) and "my_inquiries" in _modules(payload)


def test_organization_staff_never_see_the_owners_personal_inquiries(
    provider_factory, account_factory, listing
):
    facility = provider_factory(provider_type=ProviderType.HOSPITAL)
    _ask(facility.account, listing)
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, facility=facility, role="MANAGER", added_by=facility.account
    )
    payload = _dash(staff, f"facility:{facility.pk}")
    assert "my_inquiries" not in _actions(payload)
    assert "my_inquiries" not in _modules(payload)
