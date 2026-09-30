"""Phase 6 acceptance review (commit 0b32801), ADR-045: the identity an
administrator verified (company name/location/website; provider type and
specialties) is frozen while review is pending or granted, decided on the
locked row, so marketplace exposure and targeting always rest on reviewed
identity."""

import threading

import pytest
from django.db import connection

from apps.accounts.roles import AccountRole
from apps.marketplace import services
from apps.marketplace.models import MedicalCompany, Product
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers import services as provider_services
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db
COMPANY = "/api/v1/marketplace/company"
PROVIDER_ME = "/api/v1/providers/me"
CATALOG = "/api/v1/marketplace/products"


def _codes(resp):
    return resp.json()["error"]["codes"]


# ---- company verified identity ------------------------------------------------------------


@pytest.mark.parametrize("status", ["PENDING", "VERIFIED"])
@pytest.mark.parametrize(
    "field,value",
    [("name", "Impostor Ltd"), ("address", "Elsewhere"), ("website", "https://evil.example")],
)
def test_company_identity_is_frozen_under_review_or_verification(
    company_factory, status, field, value
):
    company = company_factory(status=status, website="https://real.example")
    resp = client_for(company.account).patch(COMPANY, {field: value}, format="json")
    assert resp.status_code == 400 and _codes(resp)[field] == ["identity_locked"]
    company.refresh_from_db()
    assert getattr(company, field) != value and company.verification_status == status


@pytest.mark.parametrize("status", ["PENDING", "VERIFIED"])
def test_company_location_is_frozen(company_factory, status):
    from apps.geography.models import Governorate

    company = company_factory(status=status)
    basra = Governorate.objects.get(slug="basra")
    resp = client_for(company.account).patch(COMPANY, {"governorate": str(basra.pk)}, format="json")
    assert resp.status_code == 400 and _codes(resp)["governorate"] == ["identity_locked"]


def test_non_identity_fields_and_unchanged_values_stay_editable(company_factory):
    company = company_factory(status=CompanyVerificationStatus.VERIFIED)
    resp = client_for(company.account).patch(
        COMPANY,
        {
            "description": "New catalogue",
            "phone": "+9647700000000",
            "public_email": "sales@x.example",
            "name": company.name,
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["description"] == "New catalogue" and body["identity_locked"] is True
    assert body["verification_status"] == "VERIFIED"


@pytest.mark.parametrize("status", ["UNVERIFIED", "REJECTED", "SUSPENDED"])
def test_company_identity_is_editable_outside_review(company_factory, status):
    company = company_factory(status=status)
    resp = client_for(company.account).patch(COMPANY, {"name": "Renamed Co"}, format="json")
    assert resp.status_code == 200 and resp.json()["identity_locked"] is False


def test_products_are_hidden_whenever_verification_is_withdrawn(
    company_factory, product_factory, category_factory, provider_factory
):
    company = company_factory()
    category = category_factory(rules=[(ProviderType.LABORATORY, None)])
    product_factory(company, category)
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    assert client_for(lab.account).get(CATALOG).json()["count"] == 1
    for status in ("UNVERIFIED", "REJECTED", "SUSPENDED"):
        services.set_verification(company, status, admin=None)
        assert client_for(lab.account).get(CATALOG).json()["count"] == 0, status
        assert Product.objects.exposable().count() == 0
        if status == "UNVERIFIED":  # re-review requested: still hidden while PENDING
            services.request_verification(company)
            assert client_for(lab.account).get(CATALOG).json()["count"] == 0


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_company_identity_patch_racing_verification_never_leaves_unreviewed_identity_verified(
    company_factory,
):
    company = company_factory(status=CompanyVerificationStatus.PENDING, name="Reviewed Name")
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
                "patch",
                lambda: services.update_company(
                    MedicalCompany.objects.get(pk=company.pk), {"name": "Unreviewed Name"}
                ),
            ),
        ),
        threading.Thread(
            target=run,
            args=(
                "verify",
                lambda: services.set_verification(
                    MedicalCompany.objects.get(pk=company.pk),
                    CompanyVerificationStatus.VERIFIED,
                    admin=None,
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["verify"] == "ok" and outcomes["patch"] == "identity_locked", outcomes
    row = MedicalCompany.objects.get(pk=company.pk)
    assert row.verification_status == "VERIFIED" and row.name == "Reviewed Name"


# ---- provider verified identity (type and specialties) -------------------------------------


def test_verified_provider_cannot_add_a_specialty_to_reach_other_products(
    provider_factory, company_factory, product_factory, category_factory, dentistry, cardiology
):
    company = company_factory()
    dental = product_factory(
        company, category_factory(rules=[("", dentistry)]), title="Dental unit"
    )
    cardiologist = provider_factory(specialties=[cardiology])
    client = client_for(cardiologist.account)
    assert client.get(CATALOG).json()["count"] == 0
    resp = client.patch(
        PROVIDER_ME, {"specialty_ids": [str(cardiology.pk), str(dentistry.pk)]}, format="json"
    )
    assert resp.status_code == 400 and _codes(resp)["specialty_ids"] == ["identity_locked"]
    assert set(cardiologist.specialties.values_list("slug", flat=True)) == {"cardiology"}
    assert client.get(CATALOG).json()["count"] == 0
    assert client.get(f"{CATALOG}/{dental.pk}").status_code == 404  # detail stays non-disclosing


@pytest.mark.parametrize("status", [VerificationStatus.PENDING, VerificationStatus.VERIFIED])
def test_verified_or_pending_provider_cannot_remove_or_replace_specialties(
    provider_factory, dentistry, cardiology, status
):
    provider = provider_factory(specialties=[dentistry], verification_status=status)
    client = client_for(provider.account)
    for payload in ([], [str(cardiology.pk)]):
        resp = client.patch(PROVIDER_ME, {"specialty_ids": payload}, format="json")
        assert resp.status_code == 400 and _codes(resp)["specialty_ids"] == ["identity_locked"]
    same = client.patch(
        PROVIDER_ME, {"specialty_ids": [str(dentistry.pk)], "display_name": "Ok"}, format="json"
    )
    assert same.status_code == 200  # resending the verified identity is not a change
    assert client.get(PROVIDER_ME).json()["identity_locked"] is True


@pytest.mark.parametrize("status", [VerificationStatus.PENDING, VerificationStatus.VERIFIED])
def test_provider_type_is_frozen_too(provider_factory, status):
    provider = provider_factory(provider_type=ProviderType.DOCTOR, verification_status=status)
    resp = client_for(provider.account).patch(
        PROVIDER_ME, {"provider_type": ProviderType.LABORATORY}, format="json"
    )
    assert resp.status_code == 400 and "provider_type" in _codes(resp)


def test_unverified_and_pending_providers_cannot_browse(provider_factory, dentistry):
    for status in (
        VerificationStatus.UNVERIFIED,
        VerificationStatus.PENDING,
        VerificationStatus.REJECTED,
        VerificationStatus.SUSPENDED,
    ):
        provider = provider_factory(specialties=[dentistry], verification_status=status)
        assert client_for(provider.account).get(CATALOG).status_code == 403, status


def test_identity_changed_only_after_leaving_verification_and_access_returns_on_re_verification(
    provider_factory, company_factory, product_factory, category_factory, dentistry, cardiology
):
    company = company_factory()
    dental = product_factory(
        company, category_factory(rules=[("", dentistry)]), title="Dental unit"
    )
    provider = provider_factory(specialties=[cardiology])
    provider_services.set_verification(provider, VerificationStatus.UNVERIFIED, by=None)
    client = client_for(provider.account)
    assert (
        client.patch(PROVIDER_ME, {"specialty_ids": [str(dentistry.pk)]}, format="json").status_code
        == 200
    )
    assert client.get(CATALOG).status_code == 403  # no access until re-verified
    provider_services.request_verification(ProviderProfile.objects.get(pk=provider.pk))
    assert client.get(CATALOG).status_code == 403  # pending review: still no access
    provider_services.set_verification(
        ProviderProfile.objects.get(pk=provider.pk), VerificationStatus.VERIFIED, by=None
    )
    fresh = client_for(ProviderProfile.objects.get(pk=provider.pk).account)  # a new request reloads
    assert fresh.get(f"{CATALOG}/{dental.pk}").status_code == 200


def test_hidden_provider_keeps_b2b_access(
    provider_factory, company_factory, product_factory, category_factory, dentistry
):
    company = company_factory()
    product_factory(company, category_factory(rules=[("", dentistry)]))
    hidden = provider_factory(specialties=[dentistry], is_visible=False)
    assert client_for(hidden.account).get(CATALOG).json()["count"] == 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_provider_specialty_patch_racing_verification_never_trusts_unreviewed_specialties(
    account_factory, baghdad, dentistry, cardiology
):
    provider = ProviderProfile.objects.create(
        account=account_factory(role=AccountRole.PROVIDER),
        provider_type=ProviderType.DOCTOR,
        display_name="Race",
        governorate=baghdad,
        verification_status=VerificationStatus.PENDING,
    )
    provider.specialties.set([cardiology])
    barrier = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def patch():
        try:
            barrier.wait(timeout=10)
            outcomes["patch"] = (
                client_for(provider.account)
                .patch(PROVIDER_ME, {"specialty_ids": [str(dentistry.pk)]}, format="json")
                .status_code
            )
        finally:
            connection.close()

    def verify():
        try:
            barrier.wait(timeout=10)
            provider_services.set_verification(
                ProviderProfile.objects.get(pk=provider.pk), VerificationStatus.VERIFIED, by=None
            )
            outcomes["verify"] = "ok"
        finally:
            connection.close()

    threads = [threading.Thread(target=patch), threading.Thread(target=verify)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes == {"patch": 400, "verify": "ok"}, outcomes
    row = ProviderProfile.objects.get(pk=provider.pk)
    assert row.verification_status == VerificationStatus.VERIFIED
    assert set(row.specialties.values_list("slug", flat=True)) == {"cardiology"}
