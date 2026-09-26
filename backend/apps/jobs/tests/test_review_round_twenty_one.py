"""Twenty-first Codex review of PR #4 (commit db9b02d): the employer location
invariant (city ∈ governorate) is re-evaluated on the locked row with the
edit applied, so concurrent partial PATCHes never commit a mismatch."""

import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.geography.models import City
from apps.jobs import services
from apps.jobs.models import Employer
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import VerificationStatus

pytestmark = pytest.mark.django_db
ME = "/api/v1/jobs/employer"


@pytest.fixture
def baghdad_city(baghdad):
    return City.objects.filter(governorate=baghdad, is_active=True).first()


@pytest.fixture
def basra_city(basra):
    return City.objects.filter(governorate=basra, is_active=True).first()


@pytest.fixture
def org(employer_factory, baghdad, baghdad_city):
    return employer_factory(verified=False, governorate=baghdad, city=baghdad_city)


def _patch(org, payload):
    client = APIClient()
    client.force_authenticate(user=owner_of(org))
    return client.patch(ME, payload, format="json")


def test_valid_location_updates_succeed(org, basra, basra_city):
    resp = _patch(org, {"governorate": str(basra.pk), "city": str(basra_city.pk)})
    assert resp.status_code == 200, resp.content
    row = Employer.objects.get(pk=org.pk)
    assert (row.governorate_id, row.city_id) == (basra.pk, basra_city.pk)


def test_city_from_another_governorate_is_the_existing_validation_error(org, basra_city):
    resp = _patch(org, {"city": str(basra_city.pk)})
    assert resp.status_code == 400 and "city" in resp.json()["error"]["codes"]


def test_changing_governorate_while_clearing_city_succeeds(org, basra):
    resp = _patch(org, {"governorate": str(basra.pk), "city": None})
    assert resp.status_code == 200
    row = Employer.objects.get(pk=org.pk)
    assert (row.governorate_id, row.city_id) == (basra.pk, None)


def test_stale_city_edit_is_refused_on_the_locked_row(org, basra, baghdad_city):
    """B validated BaghdadCity against the Baghdad row it read; A moved the
    organisation to Basra meanwhile. B must be refused, not committed."""
    stale = Employer.objects.get(pk=org.pk)
    services.update_employer(org, {"governorate": basra, "city": None}, actor=owner_of(org))
    with pytest.raises(services.FieldsInvalid) as exc:
        services.update_employer(stale, {"city": baghdad_city}, actor=owner_of(org))
    assert list(exc.value.errors) == ["city"]
    row = Employer.objects.get(pk=org.pk)
    assert (row.governorate_id, row.city_id) == (basra.pk, None)


def test_stale_governorate_edit_is_refused_when_a_city_was_set_meanwhile(
    employer_factory, baghdad, baghdad_city, basra
):
    org = employer_factory(verified=False, governorate=baghdad, city=None)
    stale = Employer.objects.get(pk=org.pk)
    services.update_employer(org, {"city": baghdad_city}, actor=owner_of(org))
    with pytest.raises(services.FieldsInvalid):
        services.update_employer(stale, {"governorate": basra}, actor=owner_of(org))
    row = Employer.objects.get(pk=org.pk)
    assert (row.governorate_id, row.city_id) == (baghdad.pk, baghdad_city.pk)


@pytest.mark.parametrize("order", ["move-first", "city-first"])
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_location_patches_never_commit_a_mismatch(
    employer_factory, baghdad, basra, admin, order
):
    baghdad_city = City.objects.filter(governorate=baghdad, is_active=True).first()
    org = employer_factory(verified=False, governorate=baghdad, city=baghdad_city)
    payloads = [
        {"governorate": str(basra.pk), "city": None},
        {"city": str(baghdad_city.pk)},
    ]
    if order == "city-first":
        payloads.reverse()
    barrier = threading.Barrier(2)
    outcomes: list[int] = []

    def run(payload):
        try:
            barrier.wait(timeout=10)
            outcomes.append(_patch(org, payload).status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(p,)) for p in payloads]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert 500 not in outcomes and 200 in outcomes, outcomes
    row = Employer.objects.select_related("city").get(pk=org.pk)
    assert row.city is None or row.city.governorate_id == row.governorate_id
    # whatever won, the organisation can still be verified without exposing an invalid pair
    services.set_employer_verification(row, VerificationStatus.VERIFIED, admin=admin)
    row.refresh_from_db()
    assert (
        row.city_id is None or City.objects.get(pk=row.city_id).governorate_id == row.governorate_id
    )


def test_identity_lock_still_precedes_the_location_check(org, admin, basra, baghdad_city):
    services.set_employer_verification(org, VerificationStatus.VERIFIED, admin=admin)
    with pytest.raises(services.IdentityLocked):
        services.update_employer(org, {"governorate": basra}, actor=owner_of(org))
    services.update_employer(org, {"description": "Still editable"}, actor=owner_of(org))
    services.update_employer(org, {"city": None}, actor=owner_of(org))  # city is not identity
    row = Employer.objects.get(pk=org.pk)
    assert row.governorate_id == org.governorate_id and row.city_id is None
