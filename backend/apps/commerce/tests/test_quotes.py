from decimal import Decimal

import pytest

from apps.accounts.roles import AccountRole
from apps.marketplace.types import BusinessType
from apps.providers.types import ProviderType
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

QUOTES = "/api/v1/quotes"
MERCHANT = "/api/v1/merchant/quotes"


@pytest.fixture
def dental_setup(company_factory, category_factory, product_factory, dentistry):
    company = company_factory(
        name="Fictional Dental Supply", business_type=BusinessType.MEDICAL_SUPPLIES_OFFICE
    )
    category = category_factory(rules=[(ProviderType.DOCTOR, dentistry)])
    product = product_factory(
        company, category, title="Dental chair (demo)", price=Decimal("9000000")
    )
    return company, product


def test_targeted_dentist_can_request_quote_and_flow_completes(
    dental_setup, provider_factory, dentistry
):
    company, product = dental_setup
    dentist = provider_factory(specialties=[dentistry])
    response = client_for(dentist.account).post(
        QUOTES, {"product": str(product.pk), "quantity": 2}, format="json"
    )
    assert response.status_code == 201, response.json()
    quote_id = response.json()["id"]
    # the requester identity the company sees is minimal
    company_view = client_for(company.account).get(MERCHANT).json()["results"][0]
    assert "email" not in str(company_view) and "phone" not in str(company_view["requester"])
    responded = client_for(company.account).post(
        f"{MERCHANT}/{quote_id}/respond",
        {"unit_price": "8500000", "note": "Demo price"},
        format="json",
    )
    assert responded.status_code == 200 and responded.json()["status"] == "QUOTED"
    closed = client_for(dentist.account).post(
        f"{QUOTES}/{quote_id}/close", {"outcome": "ACCEPTED"}, format="json"
    )
    assert closed.status_code == 200 and closed.json()["status"] == "ACCEPTED"


def test_cardiologist_cannot_quote_a_dental_product(dental_setup, provider_factory, cardiology):
    _, product = dental_setup
    cardiologist = provider_factory(specialties=[cardiology])
    response = client_for(cardiologist.account).post(
        QUOTES, {"product": str(product.pk), "quantity": 1}, format="json"
    )
    assert response.status_code == 404


def test_duplicate_open_quote_refused(dental_setup, provider_factory, dentistry):
    _, product = dental_setup
    dentist = provider_factory(specialties=[dentistry])
    client = client_for(dentist.account)
    assert (
        client.post(QUOTES, {"product": str(product.pk), "quantity": 1}, format="json").status_code
        == 201
    )
    assert (
        client.post(QUOTES, {"product": str(product.pk), "quantity": 1}, format="json").status_code
        == 409
    )


def test_patients_and_unverified_providers_cannot_request(
    dental_setup, provider_factory, account_factory, dentistry
):
    _, product = dental_setup
    patient = account_factory(role=AccountRole.PATIENT)
    assert (
        client_for(patient)
        .post(QUOTES, {"product": str(product.pk), "quantity": 1}, format="json")
        .status_code
        == 403
    )
    pending = provider_factory(specialties=[dentistry], verification_status="PENDING")
    assert (
        client_for(pending.account)
        .post(QUOTES, {"product": str(product.pk), "quantity": 1}, format="json")
        .status_code
        == 403
    )


def test_viewer_sees_quotes_but_cannot_respond_and_rivals_are_blind(
    dental_setup, provider_factory, account_factory, company_factory, dentistry
):
    company, product = dental_setup
    dentist = provider_factory(specialties=[dentistry])
    quote_id = (
        client_for(dentist.account)
        .post(QUOTES, {"product": str(product.pk), "quantity": 1}, format="json")
        .json()["id"]
    )
    viewer = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=viewer, company=company, role="VIEWER", added_by=company.account
    )
    query = f"?company={company.pk}"
    assert client_for(viewer).get(f"{MERCHANT}{query}").status_code == 200
    assert (
        client_for(viewer)
        .post(f"{MERCHANT}/{quote_id}/respond{query}", {"unit_price": "1"}, format="json")
        .status_code
        == 403
    )
    rival = company_factory()
    assert (
        client_for(rival.account)
        .post(f"{MERCHANT}/{quote_id}/respond", {"unit_price": "1"}, format="json")
        .status_code
        == 404
    )
    other_dentist = provider_factory(specialties=[dentistry])
    assert (
        client_for(other_dentist.account)
        .post(f"{QUOTES}/{quote_id}/close", {"outcome": "WITHDRAWN"}, format="json")
        .status_code
        == 404
    )
