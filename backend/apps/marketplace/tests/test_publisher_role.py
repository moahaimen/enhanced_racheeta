"""Phase 6 acceptance review (commit 638492f): a company publishes and is
exposed only while its account's role is still MEDICAL_COMPANY — alongside
VERIFIED and an active account — on every eligibility path (can_publish,
publishing(), exposable(), targeted_for(), the activation gate, the dashboard),
read from current database state."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.roles import AccountRole
from apps.marketplace import services, views
from apps.marketplace.models import MedicalCompany, Product
from apps.providers.types import ProviderType

from .conftest import client_for

pytestmark = pytest.mark.django_db
CATALOG = "/api/v1/marketplace/products"
COMPANY_PRODUCTS = "/api/v1/marketplace/company/products"


@pytest.fixture
def live(company_factory, category_factory, product_factory, provider_factory):
    """A verified company on an active MEDICAL_COMPANY account with one exposed
    product, and a laboratory client that is targeted by it."""
    company = company_factory(name="Exposed Supplier", public_email="sales@exposed.example")
    product = product_factory(company, category_factory(rules=[(ProviderType.LABORATORY, None)]))
    lab = client_for(provider_factory(provider_type=ProviderType.LABORATORY).account)
    return company, product, lab


def _set_role(company, role):
    Account.objects.filter(pk=company.account_id).update(role=role)
    return MedicalCompany.objects.select_related("account").get(pk=company.pk)


def _exposure(product, lab):
    return (
        lab.get(CATALOG).json()["count"],
        lab.get(f"{CATALOG}/{product.pk}").status_code,
        Product.objects.exposable().filter(pk=product.pk).exists(),
    )


def test_verified_active_medical_company_account_publishes_and_is_exposed(live):
    company, product, lab = live
    assert company.can_publish is True
    assert MedicalCompany.objects.publishing().filter(pk=company.pk).exists()
    assert _exposure(product, lab) == (1, 200, True)
    assert services.dashboard_summary(company)["products_exposable"] == 1


@pytest.mark.parametrize("role", [AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.ADMIN])
def test_role_moved_away_withdraws_publication_immediately(live, role):
    company, product, lab = live
    if role == AccountRole.ADMIN:
        Account.objects.filter(pk=company.account_id).update(is_staff=True)
    company = _set_role(company, role)
    assert company.can_publish is False
    assert not MedicalCompany.objects.publishing().filter(pk=company.pk).exists()
    assert _exposure(product, lab) == (0, 404, False)  # list, non-disclosing detail, queryset
    detail = lab.get(f"{CATALOG}/{product.pk}").content.decode()
    assert "Exposed Supplier" not in detail and "sales@exposed.example" not in detail
    summary = services.dashboard_summary(company)
    assert summary["can_publish"] is False and summary["products_exposable"] == 0


def test_activation_and_reactivation_fail_after_role_loss(live, category_factory):
    company, product, lab = live
    draft = Product.objects.create(
        company=company, category=product.category, title="Draft", is_active=False
    )
    company = _set_role(company, AccountRole.PATIENT)
    with pytest.raises(services.CompanyNotVerified):
        services.update_product(company, draft.pk, {}, active=True)
    with pytest.raises(services.CompanyNotVerified):  # an active product's edit re-runs the gate
        services.update_product(company, product.pk, {"title": "Renamed"}, active=True)
    assert Product.objects.get(pk=draft.pk).is_active is False
    # The company endpoints themselves are closed to that account.
    assert (
        client_for(company.account).post(f"{COMPANY_PRODUCTS}/{draft.pk}/activate").status_code
        == 403
    )
    # Deactivation stays possible: the owner can always withdraw.
    services.update_product(company, product.pk, {}, active=False)
    assert Product.objects.get(pk=product.pk).is_active is False


def test_restoring_the_role_restores_eligibility(live):
    company, product, lab = live
    company = _set_role(company, AccountRole.PATIENT)
    assert _exposure(product, lab) == (0, 404, False)
    company = _set_role(company, AccountRole.MEDICAL_COMPANY)
    assert company.can_publish is True
    assert _exposure(product, lab) == (1, 200, True)
    assert services.dashboard_summary(company)["products_exposable"] == 1


def test_inactive_account_still_blocks(live):
    company, product, lab = live
    Account.objects.filter(pk=company.account_id).update(is_active=False)
    company = MedicalCompany.objects.select_related("account").get(pk=company.pk)
    assert company.can_publish is False
    assert _exposure(product, lab) == (0, 404, False)
    assert services.dashboard_summary(company)["products_exposable"] == 0


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_activation_reads_the_current_role_not_the_request_snapshot(
    company_factory, category_factory, product_factory, monkeypatch
):
    """The request loaded the company (role MEDICAL_COMPANY) before staff moved
    the role; the gate decides on the company re-read under lock."""
    company = company_factory()
    draft = product_factory(
        company, category_factory(rules=[(ProviderType.DOCTOR, None)]), is_active=False
    )
    original = views._own_company

    def own_company_then_role_moves(request):
        snapshot = original(request)  # role MEDICAL_COMPANY in memory
        done = threading.Event()

        def move_role():
            try:
                Account.objects.filter(pk=company.account_id).update(role=AccountRole.PATIENT)
            finally:
                connection.close()
                done.set()

        threading.Thread(target=move_role).start()
        assert done.wait(timeout=10)
        assert (
            snapshot.account.role == AccountRole.MEDICAL_COMPANY
        )  # stale, as a request would hold
        return snapshot

    monkeypatch.setattr(views, "_own_company", own_company_then_role_moves)
    client = APIClient()
    client.force_authenticate(
        user=Account.objects.get(pk=company.account_id)
    )  # still MEDICAL_COMPANY here
    resp = client.post(f"{COMPANY_PRODUCTS}/{draft.pk}/activate")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "company_not_verified"
    assert Product.objects.get(pk=draft.pk).is_active is False
