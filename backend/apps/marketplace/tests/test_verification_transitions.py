"""Phase 6 acceptance review (commit 3571665), ADR-045 continued: VERIFIED is
granted only to a PENDING company or provider (the identity frozen by the
review request), and the catalogue re-reads the provider's verification and
identity at query time instead of trusting the permission check."""

import threading

import pytest
from django.db import connection

from apps.accounts.roles import AccountRole
from apps.marketplace import permissions as mp_permissions
from apps.marketplace import services
from apps.marketplace.models import MedicalCompany, Product
from apps.marketplace.types import CompanyVerificationStatus
from apps.providers import services as provider_services
from apps.providers.models import ProviderProfile
from apps.providers.types import ProviderType, VerificationStatus

from .conftest import client_for

pytestmark = pytest.mark.django_db
CATALOG = "/api/v1/marketplace/products"
PROVIDER_ME = "/api/v1/providers/me"
ADMIN_COMPANY = "/api/v1/admin/marketplace/companies/{}/verification"
ADMIN_PROVIDER = "/api/v1/admin/providers/{}/verification"


# ---- company: VERIFIED only from PENDING -------------------------------------------------


@pytest.mark.parametrize("source", ["UNVERIFIED", "REJECTED", "SUSPENDED"])
def test_company_cannot_be_verified_from_a_non_pending_state(company_factory, admin_client, source):
    company = company_factory(status=source)
    resp = admin_client.post(
        ADMIN_COMPANY.format(company.pk), {"status": "VERIFIED"}, format="json"
    )
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_transition"
    company.refresh_from_db()
    assert company.verification_status == source


def test_company_pending_to_verified_and_other_admin_decisions_still_work(
    company_factory, admin_client
):
    company = company_factory(status=CompanyVerificationStatus.PENDING)
    assert (
        admin_client.post(
            ADMIN_COMPANY.format(company.pk), {"status": "VERIFIED"}, format="json"
        ).status_code
        == 200
    )
    for status in ("SUSPENDED", "UNVERIFIED", "REJECTED"):
        resp = admin_client.post(
            ADMIN_COMPANY.format(company.pk), {"status": status}, format="json"
        )
        assert resp.status_code == 200 and resp.json()["verification_status"] == status


def test_an_edited_identity_is_verified_only_after_a_new_review_request(
    company_factory, admin_client
):
    company = company_factory(status=CompanyVerificationStatus.REJECTED, name="Old Name")
    client = client_for(company.account)
    assert (
        client.patch("/api/v1/marketplace/company", {"name": "New Name"}, format="json").status_code
        == 200
    )
    # the administrator cannot approve the edited identity directly
    assert (
        admin_client.post(
            ADMIN_COMPANY.format(company.pk), {"status": "VERIFIED"}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.post("/api/v1/marketplace/company/verification/request").status_code == 200
    )  # freezes "New Name"
    assert (
        admin_client.post(
            ADMIN_COMPANY.format(company.pk), {"status": "VERIFIED"}, format="json"
        ).status_code
        == 200
    )
    company.refresh_from_db()
    assert (company.name, company.verification_status) == ("New Name", "VERIFIED")


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_company_edit_request_and_decision_racing_never_verify_an_unreviewed_identity(
    company_factory,
):
    company = company_factory(status=CompanyVerificationStatus.UNVERIFIED, name="Before")
    barrier = threading.Barrier(3)
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

    def fresh():
        return MedicalCompany.objects.get(pk=company.pk)

    threads = [
        threading.Thread(
            target=run, args=("edit", lambda: services.update_company(fresh(), {"name": "After"}))
        ),
        threading.Thread(
            target=run, args=("request", lambda: services.request_verification(fresh()))
        ),
        threading.Thread(
            target=run,
            args=(
                "verify",
                lambda: services.set_verification(
                    fresh(), CompanyVerificationStatus.VERIFIED, admin=None
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert "Error" not in "".join(outcomes.values()), outcomes
    row = fresh()
    if row.verification_status == "VERIFIED":
        # verified only after the review request, which froze whatever name was committed then;
        # an edit after the request is refused, so the verified name is the requested one
        assert outcomes["request"] == "ok" and outcomes["verify"] == "ok"
        assert outcomes["edit"] in ("ok", "identity_locked")
        if outcomes["edit"] == "identity_locked":
            assert row.name == "Before"
    else:
        assert outcomes["verify"] == "invalid_transition"


# ---- provider: VERIFIED only from PENDING -------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [VerificationStatus.UNVERIFIED, VerificationStatus.REJECTED, VerificationStatus.SUSPENDED],
)
def test_provider_cannot_be_verified_from_a_non_pending_state(
    provider_factory, admin_client, source
):
    provider = provider_factory(verification_status=source)
    resp = admin_client.post(
        ADMIN_PROVIDER.format(provider.pk), {"status": "VERIFIED"}, format="json"
    )
    assert resp.status_code == 400 and "status" in resp.json()["error"]["codes"]
    provider.refresh_from_db()
    assert provider.verification_status == source


def test_provider_pending_to_verified_succeeds(provider_factory, admin_client):
    provider = provider_factory(verification_status=VerificationStatus.PENDING)
    resp = admin_client.post(
        ADMIN_PROVIDER.format(provider.pk), {"status": "VERIFIED"}, format="json"
    )
    assert resp.status_code == 200 and resp.json()["verification_status"] == "VERIFIED"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_provider_specialty_edit_racing_request_and_verification(
    account_factory, baghdad, dentistry, cardiology
):
    provider = ProviderProfile.objects.create(
        account=account_factory(role=AccountRole.PROVIDER),
        provider_type=ProviderType.DOCTOR,
        display_name="Race",
        governorate=baghdad,
        verification_status=VerificationStatus.UNVERIFIED,
    )
    provider.specialties.set([cardiology])
    barrier = threading.Barrier(3)
    outcomes: dict[str, object] = {}

    def fresh():
        return ProviderProfile.objects.get(pk=provider.pk)

    def edit():
        try:
            barrier.wait(timeout=10)
            outcomes["edit"] = (
                client_for(provider.account)
                .patch(PROVIDER_ME, {"specialty_ids": [str(dentistry.pk)]}, format="json")
                .status_code
            )
        finally:
            connection.close()

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            fn()
            outcomes[name] = "ok"
        except provider_services.InvalidTransition:
            outcomes[name] = "invalid_transition"
        finally:
            connection.close()

    threads = [
        threading.Thread(target=edit),
        threading.Thread(
            target=run, args=("request", lambda: provider_services.request_verification(fresh()))
        ),
        threading.Thread(
            target=run,
            args=(
                "verify",
                lambda: provider_services.set_verification(
                    fresh(), VerificationStatus.VERIFIED, by=None
                ),
            ),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    row = fresh()
    slugs = set(row.specialties.values_list("slug", flat=True))
    if row.verification_status == VerificationStatus.VERIFIED:
        assert outcomes["request"] == "ok" and outcomes["verify"] == "ok"
        # the verified specialties are those frozen by the request: the edit either landed
        # before it (200) or was refused after it (400)
        assert (outcomes["edit"], slugs) in ((200, {"dentistry"}), (400, {"cardiology"}))
    else:
        assert outcomes["verify"] == "invalid_transition"


# ---- catalogue: authoritative provider at query time ----------------------------------------


@pytest.fixture
def lab_catalog(company_factory, product_factory, category_factory, dentistry):
    company = company_factory()
    lab = product_factory(
        company, category_factory(rules=[(ProviderType.LABORATORY, None)]), title="Centrifuge"
    )
    dental = product_factory(
        company, category_factory(rules=[("", dentistry)]), title="Dental unit"
    )
    return {"lab": lab, "dental": dental}


def _stale_permission(monkeypatch):
    """The permission check ran while the provider was VERIFIED."""
    monkeypatch.setattr(
        mp_permissions.CanBrowseMarketplace, "has_permission", lambda self, request, view: True
    )


@pytest.mark.parametrize(
    "status",
    [VerificationStatus.SUSPENDED, VerificationStatus.UNVERIFIED, VerificationStatus.REJECTED],
)
def test_status_change_after_the_permission_check_discloses_nothing(
    provider_factory, lab_catalog, monkeypatch, status
):
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    client = client_for(lab.account)
    assert client.get(CATALOG).json()["count"] == 1
    _stale_permission(monkeypatch)
    provider_services.set_verification(lab, status, by=None)
    for url in (CATALOG, f"{CATALOG}/{lab_catalog['lab'].pk}"):
        resp = client.get(url)
        assert resp.status_code == 403, (url, status)
        assert "Centrifuge" not in resp.content.decode()


def test_a_queryset_built_while_verified_returns_nothing_once_suspended(
    provider_factory, lab_catalog
):
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    qs = Product.objects.targeted_for(lab)
    provider_services.set_verification(lab, VerificationStatus.SUSPENDED, by=None)
    assert list(qs) == [] and qs.count() == 0


def test_specialties_unlocked_by_suspension_are_never_matched(
    provider_factory, lab_catalog, cardiology, dentistry
):
    cardiologist = provider_factory(specialties=[cardiology])
    qs = Product.objects.targeted_for(cardiologist)  # built while VERIFIED with cardiology only
    provider_services.set_verification(cardiologist, VerificationStatus.SUSPENDED, by=None)
    cardiologist.specialties.set([dentistry])  # now editable: identity unlocked
    assert list(qs) == []  # the same in-flight query sees the suspension, not dentistry


def test_detail_stays_non_disclosing_for_unmatched_ids(provider_factory, lab_catalog):
    lab = provider_factory(provider_type=ProviderType.LABORATORY)
    client = client_for(lab.account)
    assert client.get(f"{CATALOG}/{lab_catalog['dental'].pk}").status_code == 404
    assert client.get(f"{CATALOG}/{lab_catalog['lab'].pk}").status_code == 200


def test_hidden_verified_provider_keeps_access(provider_factory, lab_catalog):
    hidden = provider_factory(provider_type=ProviderType.LABORATORY, is_visible=False)
    client = client_for(hidden.account)
    assert client.get(CATALOG).json()["count"] == 1
    assert client.get(f"{CATALOG}/{lab_catalog['lab'].pk}").status_code == 200
