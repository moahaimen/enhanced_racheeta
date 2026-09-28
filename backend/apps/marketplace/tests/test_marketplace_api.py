"""Phase 6 medical marketplace: company lifecycle, product management and the
server-authoritative audience targeting."""

import threading
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.accounts.roles import AccountRole
from apps.audit.models import AuditEvent
from apps.marketplace import services
from apps.marketplace.models import MedicalCompany, Product, ProductAudience
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers.types import ProviderType, VerificationStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db
COMPANY = "/api/v1/marketplace/company"
PRODUCTS = "/api/v1/marketplace/company/products"
CATALOG = "/api/v1/marketplace/products"


def _ids(resp):
    return [row["id"] for row in resp.json()["results"]]


# ---- company role, ownership and lifecycle -----------------------------------------------


def test_company_onboarding_and_one_profile_per_account(account_factory, baghdad):
    account = account_factory(role=AccountRole.MEDICAL_COMPANY)
    client = client_for(account)
    assert client.get(COMPANY).status_code == 404
    resp = client.post(
        COMPANY, {"name": "Dental Supply", "governorate": str(baghdad.pk)}, format="json"
    )
    assert resp.status_code == 201 and resp.json()["verification_status"] == "UNVERIFIED"
    again = client.post(COMPANY, {"name": "Second", "governorate": str(baghdad.pk)}, format="json")
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_exists"
    assert MedicalCompany.objects.filter(account=account).count() == 1
    assert AuditEvent.objects.filter(action="marketplace.company.created").count() == 1


@pytest.mark.parametrize(
    "role", [AccountRole.PATIENT, AccountRole.PROVIDER, AccountRole.REAL_ESTATE_SELLER]
)
def test_non_company_accounts_cannot_manage(account_factory, baghdad, role):
    client = client_for(account_factory(role=role))
    assert (
        client.post(
            COMPANY, {"name": "X", "governorate": str(baghdad.pk)}, format="json"
        ).status_code
        == 403
    )
    assert client.get(PRODUCTS).status_code == 403
    assert client.get(f"{COMPANY}/dashboard").status_code == 403


def test_company_cannot_set_verification_fields(company_factory):
    company = company_factory(status=CompanyVerificationStatus.UNVERIFIED)
    resp = client_for(company.account).patch(
        COMPANY, {"verification_status": "VERIFIED"}, format="json"
    )
    assert resp.status_code == 400 and "verification_status" in resp.json()["error"]["codes"]
    company.refresh_from_db()
    assert company.verification_status == "UNVERIFIED"


def test_verification_lifecycle(company_factory, admin_client):
    company = company_factory(status=CompanyVerificationStatus.UNVERIFIED)
    client = client_for(company.account)
    resp = client.post(f"{COMPANY}/verification/request")
    assert resp.status_code == 200 and resp.json()["verification_status"] == "PENDING"
    assert client.post(f"{COMPANY}/verification/request").status_code == 400  # already pending
    decided = admin_client.post(
        f"/api/v1/admin/marketplace/companies/{company.pk}/verification",
        {"status": "VERIFIED", "note": "docs ok"},
        format="json",
    )
    assert decided.status_code == 200 and decided.json()["verification_status"] == "VERIFIED"
    assert decided.json()["can_publish"] is True
    assert (
        client.post(
            f"/api/v1/admin/marketplace/companies/{company.pk}/verification",
            {"status": "VERIFIED"},
            format="json",
        ).status_code
        == 403
    )
    assert admin_client.get("/api/v1/admin/marketplace/companies").json()["count"] == 1
    assert AuditEvent.objects.filter(action="marketplace.company.verification_set").count() == 1


# ---- products: ownership, validation and publication gate -------------------------------------


@pytest.fixture
def dental(category_factory, dentistry):
    return category_factory(rules=[(ProviderType.DOCTOR, dentistry)], slug="dental")


def test_create_edit_activate_deactivate(company_factory, dental):
    company = company_factory()
    client = client_for(company.account)
    created = client.post(
        PRODUCTS,
        {
            "category": str(dental.pk),
            "title": "Dental chair",
            "price": "1500000.00",
            "currency": "IQD",
        },
        format="json",
    )
    assert created.status_code == 201 and created.json()["is_active"] is False
    pid = created.json()["id"]
    assert (
        client.patch(f"{PRODUCTS}/{pid}", {"brand": "Acme", "price": None}, format="json").json()[
            "price"
        ]
        is None
    )
    assert client.post(f"{PRODUCTS}/{pid}/activate").json()["is_active"] is True
    assert client.post(f"{PRODUCTS}/{pid}/deactivate").json()["is_active"] is False
    assert (
        AuditEvent.objects.filter(action="marketplace.product.updated", target_id=pid).count() == 3
    )


def test_price_validation(company_factory, dental):
    client = client_for(company_factory().account)
    bad = client.post(
        PRODUCTS, {"category": str(dental.pk), "title": "X", "price": "-1"}, format="json"
    )
    assert bad.status_code == 400 and "price" in bad.json()["error"]["codes"]
    currency = client.post(
        PRODUCTS, {"category": str(dental.pk), "title": "X", "currency": "EUR"}, format="json"
    )
    assert currency.status_code == 400
    assert (
        client.post(
            PRODUCTS, {"category": str(dental.pk), "title": "X", "price": "0"}, format="json"
        ).status_code
        == 201
    )


def test_foreign_products_are_hidden_and_refused(company_factory, product_factory, dental):
    mine, other = company_factory(), company_factory()
    theirs = product_factory(other, dental, is_active=False)
    client = client_for(mine.account)
    assert client.get(f"{PRODUCTS}/{theirs.pk}").status_code == 404
    assert (
        client.patch(f"{PRODUCTS}/{theirs.pk}", {"title": "Hijack"}, format="json").status_code
        == 404
    )
    assert client.post(f"{PRODUCTS}/{theirs.pk}/activate").status_code == 404
    assert theirs.pk not in {row["id"] for row in client.get(PRODUCTS).json()["results"]}
    theirs.refresh_from_db()
    assert theirs.title != "Hijack" and theirs.is_active is False


@pytest.mark.parametrize(
    "field",
    ["provider_type", "specialty", "specialty_ids", "audience", "target", "is_active", "company"],
)
def test_payload_cannot_inject_targeting_or_state(company_factory, dental, field):
    client = client_for(company_factory().account)
    resp = client.post(
        PRODUCTS, {"category": str(dental.pk), "title": "X", field: "LABORATORY"}, format="json"
    )
    assert resp.status_code == 400 and field in resp.json()["error"]["codes"]
    assert Product.objects.count() == 0


@pytest.mark.parametrize("status", ["UNVERIFIED", "PENDING", "REJECTED", "SUSPENDED"])
def test_unverified_company_cannot_activate_but_keeps_drafts(
    company_factory, product_factory, dental, status
):
    company = company_factory(status=status)
    product = product_factory(company, dental, is_active=False)
    client = client_for(company.account)
    assert (
        client.patch(
            f"{PRODUCTS}/{product.pk}", {"title": "Edited draft"}, format="json"
        ).status_code
        == 200
    )
    resp = client.post(f"{PRODUCTS}/{product.pk}/activate")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "company_not_verified"
    product.refresh_from_db()
    assert product.is_active is False and product.title == "Edited draft"


def test_inactive_or_ruleless_category_refuses_activation(
    company_factory, product_factory, category_factory, dental
):
    company = company_factory()
    ruleless = category_factory(rules=[])
    product = product_factory(company, ruleless, is_active=False)
    client = client_for(company.account)
    resp = client.post(f"{PRODUCTS}/{product.pk}/activate")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "category_unavailable"
    in_dental = product_factory(company, dental, is_active=False)
    dental.is_active = False
    dental.save(update_fields=["is_active", "updated_at"])
    assert client.post(f"{PRODUCTS}/{in_dental.pk}/activate").status_code == 409
    # an inactive category is not offered for new products either
    assert (
        client.post(PRODUCTS, {"category": str(dental.pk), "title": "X"}, format="json").status_code
        == 400
    )


def test_audience_rule_must_constrain_something(category_factory):
    category = category_factory()
    with pytest.raises(ValidationError):
        ProductAudience.objects.create(category=category, provider_type="", specialty=None)


# ---- targeting ----------------------------------------------------------------------------


@pytest.fixture
def catalog(company_factory, product_factory, category_factory, dentistry, cardiology):
    """One product per rule shape, all published by a verified company."""
    company = company_factory()
    by_type = category_factory(rules=[(ProviderType.LABORATORY, None)], slug="lab")
    by_specialty = category_factory(rules=[("", dentistry)], slug="dental-any")
    combined = category_factory(rules=[(ProviderType.DOCTOR, cardiology)], slug="cardio-doctors")
    return {
        "lab": product_factory(company, by_type, title="Centrifuge"),
        "dental": product_factory(company, by_specialty, title="Dental unit"),
        "cardio": product_factory(company, combined, title="ECG"),
    }


def _visible(provider):
    client = client_for(provider.account)
    resp = client.get(CATALOG)
    assert resp.status_code == 200
    return set(_ids(resp))


def test_provider_type_rule(provider_factory, catalog):
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    assert _visible(lab) == {str(catalog["lab"].pk)}


def test_specialty_rule(provider_factory, catalog, dentistry):
    dentist = provider_factory(provider_type=ProviderType.DOCTOR, specialties=[dentistry])
    center = provider_factory(provider_type=ProviderType.MEDICAL_CENTER, specialties=[dentistry])
    assert _visible(dentist) == {str(catalog["dental"].pk)}
    assert _visible(center) == {str(catalog["dental"].pk)}


def test_combined_rule_needs_both(provider_factory, catalog, cardiology):
    cardiologist = provider_factory(provider_type=ProviderType.DOCTOR, specialties=[cardiology])
    cardio_nurse = provider_factory(provider_type=ProviderType.NURSE, specialties=[cardiology])
    assert _visible(cardiologist) == {str(catalog["cardio"].pk)}
    assert _visible(cardio_nurse) == set()


def test_non_matching_products_are_unreachable_by_list_filter_or_detail(provider_factory, catalog):
    pharmacy = provider_factory(provider_type=ProviderType.PHARMACY)
    client = client_for(pharmacy.account)
    assert client.get(CATALOG).json()["count"] == 0
    for product in catalog.values():
        assert client.get(CATALOG, {"category": str(product.category_id)}).json()["count"] == 0
        assert client.get(f"{CATALOG}/{product.pk}").status_code == 404
    # query parameters cannot widen the audience
    assert client.get(CATALOG, {"provider_type": "LABORATORY"}).json()["count"] == 0


def test_detail_matches_list(provider_factory, catalog):
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    client = client_for(lab.account)
    body = client.get(f"{CATALOG}/{catalog['lab'].pk}").json()
    assert body["title"] == "Centrifuge" and body["company"]["name"]
    assert client.get(f"{CATALOG}/{catalog['cardio'].pk}").status_code == 404


def test_hidden_provider_keeps_b2b_access_but_unverified_provider_does_not(
    provider_factory, catalog
):
    hidden_lab = provider_factory(provider_type=ProviderType.LABORATORY, is_visible=False)
    assert _visible(hidden_lab) == {str(catalog["lab"].pk)}
    pending_lab = provider_factory(
        provider_type=ProviderType.LABORATORY, verification_status=VerificationStatus.PENDING
    )
    assert client_for(pending_lab.account).get(CATALOG).status_code == 403


@pytest.mark.parametrize("role", [AccountRole.PATIENT, AccountRole.MEDICAL_COMPANY])
def test_non_providers_cannot_browse(account_factory, catalog, role):
    assert client_for(account_factory(role=role)).get(CATALOG).status_code == 403


def test_visibility_follows_current_server_state(
    provider_factory, catalog, company_factory, product_factory
):
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    company = catalog["lab"].company
    services.set_verification(company, CompanyVerificationStatus.SUSPENDED, admin=None)
    assert _visible(lab) == set()
    services.set_verification(company, CompanyVerificationStatus.VERIFIED, admin=None)
    assert _visible(lab) == {str(catalog["lab"].pk)}
    category = catalog["lab"].category
    category.audiences.update(is_active=False)
    assert _visible(lab) == set()
    category.audiences.update(is_active=True)
    category.is_active = False
    category.save(update_fields=["is_active", "updated_at"])
    assert _visible(lab) == set()
    category.is_active = True
    category.save(update_fields=["is_active", "updated_at"])
    company.account.is_active = False
    company.account.save(update_fields=["is_active"])
    assert _visible(lab) == set()


def test_pagination_and_stable_ordering(
    provider_factory, company_factory, product_factory, category_factory
):
    category = category_factory(rules=[(ProviderType.LABORATORY, None)])
    company = company_factory()
    ids = [str(product_factory(company, category, title=f"P{i}").pk) for i in range(23)]
    client = client_for(provider_factory(provider_type=ProviderType.LABORATORY).account)
    first = client.get(CATALOG).json()
    second = client.get(CATALOG, {"page": 2}).json()
    assert first["count"] == 23 and len(first["results"]) == 20 and len(second["results"]) == 3
    assert first["next"] and second["previous"] and second["next"] is None
    seen = [r["id"] for r in first["results"]] + [r["id"] for r in second["results"]]
    assert sorted(seen) == sorted(ids) and len(set(seen)) == 23
    assert seen == [r["id"] for r in client.get(CATALOG).json()["results"]] + [
        r["id"] for r in client.get(CATALOG, {"page": 2}).json()["results"]
    ]
    own = client_for(company.account).get(PRODUCTS).json()
    assert own["count"] == 23 and len(own["results"]) == 20


def test_dashboard_counts(company_factory, product_factory, category_factory, dental):
    company = company_factory()
    ruleless = category_factory(rules=[])
    for _ in range(3):
        product_factory(company, dental, is_active=True)
    product_factory(company, dental, is_active=False)
    product_factory(company, ruleless, is_active=True)  # active but not exposable
    body = client_for(company.account).get(f"{COMPANY}/dashboard").json()
    assert body == {
        "verification_status": "VERIFIED",
        "can_publish": True,
        "products_total": 5,
        "products_active": 4,
        "products_inactive": 1,
        "products_exposable": 3,
    }
    services.set_verification(company, CompanyVerificationStatus.SUSPENDED, admin=None)
    assert client_for(company.account).get(f"{COMPANY}/dashboard").json()["products_exposable"] == 0


def test_categories_are_public_reference_data(category_factory):
    category_factory(slug="shown")
    category_factory(slug="hidden", is_active=False)
    from rest_framework.test import APIClient

    slugs = {row["slug"] for row in APIClient().get("/api/v1/marketplace/categories").json()}
    assert "shown" in slugs and "hidden" not in slugs


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_activation_racing_suspension_never_publishes_after_it(
    company_factory, product_factory, category_factory, dentistry
):
    company = company_factory()
    category = category_factory(rules=[(ProviderType.DOCTOR, dentistry)])
    product = product_factory(company, category, is_active=False)
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except services.MarketplaceError as exc:
            outcomes[name] = exc.code
        except Exception as exc:  # pragma: no cover
            outcomes[name] = repr(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=run,
            args=(
                "activate",
                lambda: services.update_product(
                    MedicalCompany.objects.get(pk=company.pk), product.pk, {}, active=True
                ),
            ),
        ),
        threading.Thread(
            target=run,
            args=(
                "suspend",
                lambda: services.set_verification(
                    MedicalCompany.objects.get(pk=company.pk),
                    CompanyVerificationStatus.SUSPENDED,
                    admin=None,
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["suspend"] == "ok" and outcomes["activate"] in ("ok", "company_not_verified"), (
        outcomes
    )
    product.refresh_from_db()
    assert product.is_active == (outcomes["activate"] == "ok")
    # whatever won, a suspended company exposes nothing
    assert Product.objects.exposable().filter(pk=product.pk).count() == 0
    assert Decimal("0") == Decimal("0")
