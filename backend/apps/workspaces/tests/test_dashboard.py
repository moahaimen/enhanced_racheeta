from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.marketplace.types import BusinessType, SaleChannel
from apps.preferences import services as prefs
from apps.providers.types import ProviderType
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

URL = "/api/v1/workspaces/dashboard"


def _dash(account, ws=None, expect=200):
    response = client_for(account).get(URL, {"ws": ws} if ws else {})
    assert response.status_code == expect, response.content
    return response.json() if expect == 200 else None


def _keys(payload):
    return [m["key"] for m in payload["modules"]]


def _module(payload, key):
    return next(m for m in payload["modules"] if m["key"] == key)


def _stat(module, key):
    return next(s["value"] for s in module["stats"] if s["key"] == key)


def test_anonymous_refused(api_client):
    assert api_client.get(URL).status_code == 401


def test_patient_dashboard_is_personal_only_and_never_cached(buyer):
    response = client_for(buyer).get(URL)
    assert response["Cache-Control"] == "private, no-store"
    payload = response.json()
    assert payload["workspace"]["kind"] == "patient"
    keys = _keys(payload)
    assert {"my_orders", "store", "notifications", "account"} <= set(keys)
    for foreign in ("catalogue", "team", "campaigns", "verification", "sponsored", "store_orders"):
        assert foreign not in keys


def test_forged_and_foreign_workspace_ids_are_404(buyer, store, company_factory):
    other = company_factory()
    for forged in (f"company:{store.pk}", f"company:{other.pk}", "admin", "facility:nonsense", "x"):
        _dash(buyer, forged, expect=404)
    _dash(store.account, f"company:{other.pk}", expect=404)


def test_staff_lands_in_their_organization_and_sees_only_their_capabilities(account_factory, store):
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, company=store, role="STAFF", added_by=store.account
    )
    listed = client_for(staff).get("/api/v1/workspaces").json()
    assert [w["id"] for w in listed if w["is_default"]] == [f"company:{store.pk}"]
    payload = _dash(staff)  # default
    assert (
        payload["workspace"]["id"] == f"company:{store.pk}"
        and payload["workspace"]["role"] == "STAFF"
    )
    keys = _keys(payload)
    assert {"catalogue", "inventory", "store_orders", "quote_requests"} <= set(keys)
    for owner_only in ("campaigns", "team", "recruitment"):
        assert owner_only not in keys  # least privilege: staff never sees these modules
    orders = _module(payload, "store_orders")
    assert orders["link"] == f"/merchant/orders?company={store.pk}"
    assert all(a["key"] not in ("advertising", "products") for a in payload["actions"])


def test_viewer_vs_manager_vs_owner(account_factory, store):
    viewer = account_factory(role=AccountRole.PATIENT)
    manager = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=viewer, company=store, role="VIEWER", added_by=store.account
    )
    OrganizationMember.objects.create(
        account=manager, company=store, role="MANAGER", added_by=store.account
    )
    ws = f"company:{store.pk}"
    assert "team" not in _keys(_dash(viewer, ws)) and "campaigns" not in _keys(_dash(viewer, ws))
    manager_keys = _keys(_dash(manager, ws))
    assert (
        "team" in manager_keys and "campaigns" in manager_keys and "recruitment" not in manager_keys
    )
    owner_keys = _keys(_dash(store.account, ws))
    assert {"team", "campaigns", "recruitment"} <= set(owner_keys)


def test_revoked_membership_and_suspended_organization_close_the_dashboard(account_factory, store):
    staff = account_factory(role=AccountRole.PATIENT)
    member = OrganizationMember.objects.create(
        account=staff, company=store, role="STAFF", added_by=store.account
    )
    ws = f"company:{store.pk}"
    _dash(staff, ws)
    member.status = "ENDED"
    member.ended_at = timezone.now()
    member.save()
    _dash(staff, ws, expect=404)
    assert _dash(staff)["workspace"]["kind"] == "patient"  # falls back to the personal space

    other = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=other, company=store, role="MANAGER", added_by=store.account
    )
    store.account.is_active = False
    store.account.save(update_fields=["is_active"])
    _dash(other, ws, expect=404)


def test_business_compositions_differ_by_type(
    company_factory, store, store_category, product_factory
):
    pharma = company_factory(business_type=BusinessType.PHARMACEUTICAL_COMPANY)
    product_factory(pharma, store_category, is_restricted=True, sale_channel=SaleChannel.B2B)
    pharma_dash = _dash(pharma.account)
    assert "inventory" not in _keys(pharma_dash) and "store_orders" not in _keys(pharma_dash)
    assert _stat(_module(pharma_dash, "catalogue"), "restricted_b2b") == 1
    product_factory(
        store, store_category, price=Decimal("10"), sale_channel=SaleChannel.B2C, stock_quantity=2
    )
    product_factory(
        store, store_category, price=Decimal("10"), sale_channel=SaleChannel.B2C, stock_quantity=0
    )
    store_dash = _dash(store.account)
    inventory = _module(store_dash, "inventory")
    assert _stat(inventory, "low_stock") == 1 and _stat(inventory, "out_of_stock") == 1


def test_store_stats_are_real_and_tenant_isolated(
    buyer, store, store_product, checkout, company_factory, store_category, product_factory
):
    rival = company_factory(business_type=BusinessType.ASSISTIVE_DEVICE_STORE)
    rival_product = product_factory(
        rival, store_category, price=Decimal("5"), sale_channel=SaleChannel.B2C, stock_quantity=5
    )
    client = client_for(buyer)
    assert (
        client.post("/api/v1/orders", checkout([(store_product, 1)]), format="json").status_code
        == 201
    )
    assert (
        client.post("/api/v1/orders", checkout([(rival_product, 1)]), format="json").status_code
        == 201
    )
    mine = _module(_dash(store.account), "store_orders")
    assert _stat(mine, "order_placed") == 1 and len(mine["items"]) == 1
    patient = _module(_dash(buyer), "my_orders")
    assert _stat(patient, "open_orders") == 2


def test_practitioner_compositions_by_profession(provider_factory, dentistry):
    doctor = _keys(_dash(provider_factory(ProviderType.DOCTOR, specialties=[dentistry]).account))
    nurse = _keys(_dash(provider_factory(ProviderType.NURSE).account))
    therapist_payload = _dash(provider_factory(ProviderType.THERAPIST).account)
    assert "reviews" in doctor and "connections" not in doctor
    assert "connections" in nurse and "reviews" not in nurse
    assert _module(therapist_payload, "services")["variant"] == "therapy"
    assert _module(therapist_payload, "reservations")["variant"] == "sessions"


def test_sponsored_and_promoted_follow_verification_and_preferences(provider_factory):
    doctor = provider_factory()
    keys = _keys(_dash(doctor.account))
    assert "sponsored" in keys and "promoted" not in keys  # real-estate promotions are opt-in
    prefs.update(doctor.account, {"real_estate_promotions": True, "show_sponsored_products": False})
    keys = _keys(_dash(doctor.account))
    assert "promoted" in keys and "sponsored" not in keys
    pending = provider_factory(verification_status="PENDING")
    keys = _keys(_dash(pending.account))
    assert "sponsored" not in keys and "products" not in keys and "promoted" not in keys


def test_facility_member_never_gets_owner_feeds(account_factory, provider_factory):
    hospital = provider_factory(ProviderType.HOSPITAL)
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, facility=hospital, role="STAFF", added_by=hospital.account
    )
    keys = _keys(_dash(staff, f"facility:{hospital.pk}"))
    assert "reservations" in keys and "practitioners" in keys
    for owner_only in ("sponsored", "promoted", "products", "my_quotes", "recruitment", "team"):
        assert owner_only not in keys


def test_reservation_modules_can_be_switched_off(settings, buyer, provider_factory):
    settings.RACHEETA = {**settings.RACHEETA, "RESERVATIONS_ENABLED": False}
    patient = _dash(buyer)
    assert "reservations" not in _keys(patient)
    assert all(a["key"] != "my_reservations" for a in patient["actions"])
    doctor = _dash(provider_factory().account)
    assert "reservations" not in _keys(doctor) and doctor["header"]["reservations_enabled"] is False


def test_admin_dashboard_only_for_staff(buyer):
    from apps.accounts.models import Account

    admin = Account.objects.create_superuser(
        email="ops@example.com", password="Str0ng-Passw0rd!", full_name="Ops"
    )
    assert {"verification", "moderation", "campaigns_admin", "users", "audit"} <= set(
        _keys(_dash(admin, "admin"))
    )
    _dash(buyer, "admin", expect=404)


def test_dashboard_payload_has_no_personal_contact_data(buyer, store, store_product, checkout):
    client_for(buyer).post("/api/v1/orders", checkout([(store_product, 1)]), format="json")
    text = client_for(store.account).get(URL).content.decode()
    assert buyer.email not in text and "+964 770 000 0000" not in text and "Street 1" not in text
