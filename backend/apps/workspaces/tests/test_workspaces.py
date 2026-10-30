import pytest
from django.utils import timezone

from apps.accounts.roles import AccountRole
from apps.providers.types import ProviderType
from apps.workspaces.models import OrganizationMember

from .conftest import client_for

pytestmark = pytest.mark.django_db

WORKSPACES = "/api/v1/workspaces"


def _kinds(account):
    response = client_for(account).get(WORKSPACES)
    assert response.status_code == 200
    return [(w["kind"], w["role"]) for w in response.json()]


def test_anonymous_cannot_list_workspaces(api_client):
    assert api_client.get(WORKSPACES).status_code == 401


def test_patient_has_only_patient_workspace(account_factory):
    patient = account_factory(role=AccountRole.PATIENT)
    assert [kind for kind, _ in _kinds(patient)] == ["patient"]


def test_company_owner_and_member_workspaces(account_factory, store):
    assert any(kind == "company" and role == "OWNER" for kind, role in _kinds(store.account))
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, company=store, role="STAFF", added_by=store.account
    )
    kinds = _kinds(staff)
    assert ("company", "STAFF") in kinds and any(kind == "patient" for kind, _ in kinds)


def test_multi_org_member_sees_both_and_ended_membership_disappears(
    account_factory, store, company_factory, provider_factory
):
    other = company_factory()
    hospital = provider_factory(provider_type=ProviderType.HOSPITAL)
    person = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=person, company=store, role="MANAGER", added_by=store.account
    )
    ended = OrganizationMember.objects.create(
        account=person, company=other, role="VIEWER", added_by=other.account
    )
    OrganizationMember.objects.create(
        account=person, facility=hospital, role="STAFF", added_by=hospital.account
    )
    kinds = _kinds(person)
    assert (
        ("company", "MANAGER") in kinds
        and ("company", "VIEWER") in kinds
        and ("facility", "STAFF") in kinds
    )
    ended.status = "ENDED"
    ended.ended_at = timezone.now()
    ended.save()
    assert ("company", "VIEWER") not in _kinds(person)
    assert client_for(person).get(f"{WORKSPACES}/company/{other.pk}").status_code == 404


def test_tenant_isolation_between_companies(account_factory, store, company_factory):
    other = company_factory()
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, company=store, role="STAFF", added_by=store.account
    )
    client = client_for(staff)
    assert client.get(f"{WORKSPACES}/company/{store.pk}").status_code == 200
    assert client.get(f"{WORKSPACES}/company/{other.pk}").status_code == 404
    assert client.get(f"{WORKSPACES}/company/{other.pk}/members").status_code == 404


def test_tenant_isolation_between_facilities(account_factory, provider_factory):
    hospital_a = provider_factory(provider_type=ProviderType.HOSPITAL)
    hospital_b = provider_factory(provider_type=ProviderType.HOSPITAL)
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, facility=hospital_a, role="STAFF", added_by=hospital_a.account
    )
    client = client_for(staff)
    assert client.get(f"{WORKSPACES}/facility/{hospital_a.pk}").status_code == 200
    assert client.get(f"{WORKSPACES}/facility/{hospital_a.pk}/reservations").status_code == 200
    assert client.get(f"{WORKSPACES}/facility/{hospital_b.pk}").status_code == 404
    assert client.get(f"{WORKSPACES}/facility/{hospital_b.pk}/reservations").status_code == 404


def test_member_management_owner_only(account_factory, store):
    manager = account_factory(role=AccountRole.PATIENT)
    viewer = account_factory(role=AccountRole.PATIENT)
    newcomer = account_factory(role=AccountRole.PATIENT, email="newcomer@example.com")
    OrganizationMember.objects.create(
        account=manager, company=store, role="MANAGER", added_by=store.account
    )
    OrganizationMember.objects.create(
        account=viewer, company=store, role="VIEWER", added_by=store.account
    )
    members = f"{WORKSPACES}/company/{store.pk}/members"
    assert client_for(viewer).get(members).status_code == 403
    assert client_for(manager).get(members).status_code == 200
    body = {"email": newcomer.email, "role": "STAFF"}
    assert client_for(manager).post(members, body, format="json").status_code == 403
    assert (
        client_for(store.account)
        .post(members, {"email": newcomer.email, "role": "OWNER"}, format="json")
        .status_code
        == 400
    )
    created = client_for(store.account).post(members, body, format="json")
    assert created.status_code == 201, created.json()
    member_id = created.json()["id"]
    assert client_for(newcomer).get(f"{WORKSPACES}/company/{store.pk}").status_code == 200
    assert (
        client_for(store.account).post(f"{members}/{member_id}/end", format="json").status_code
        == 200
    )
    assert client_for(newcomer).get(f"{WORKSPACES}/company/{store.pk}").status_code == 404


def test_deactivated_owner_company_is_inaccessible_to_staff(account_factory, store):
    staff = account_factory(role=AccountRole.PATIENT)
    OrganizationMember.objects.create(
        account=staff, company=store, role="STAFF", added_by=store.account
    )
    store.account.is_active = False
    store.account.save(update_fields=["is_active"])
    assert client_for(staff).get(f"{WORKSPACES}/company/{store.pk}").status_code == 404
