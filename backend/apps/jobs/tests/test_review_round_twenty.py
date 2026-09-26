"""Twentieth Codex review of PR #4 (commit bf5edf4): job cross-field rules
re-evaluated on the locked row, so concurrent partial edits never produce an
invalid job or a 500."""

import threading
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection
from rest_framework.test import APIClient

from apps.geography.models import City
from apps.jobs import services
from apps.jobs.models import JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.types import JobStatus

pytestmark = pytest.mark.django_db
JOBS = "/api/v1/jobs/employer/jobs"


@pytest.fixture
def draft(employer, job_factory):
    return job_factory(employer, status=JobStatus.DRAFT, salary_min=10, salary_max=30)


def _patch(employer, job, payload):
    client = APIClient()
    client.force_authenticate(user=owner_of(employer))
    return client.patch(f"{JOBS}/{job.pk}", payload, format="json")


def test_single_bound_updates_and_null_bounds(employer, draft):
    assert _patch(employer, draft, {"salary_min": "25"}).status_code == 200
    assert _patch(employer, draft, {"salary_max": "40"}).status_code == 200
    assert _patch(employer, draft, {"salary_max": None}).status_code == 200
    assert _patch(employer, draft, {"salary_min": "90"}).status_code == 200  # open-ended range
    row = JobPost.objects.get(pk=draft.pk)
    assert (row.salary_min, row.salary_max) == (Decimal("90"), None)


def test_invalid_range_in_one_request_is_refused(employer, draft):
    resp = _patch(employer, draft, {"salary_min": "50"})
    assert resp.status_code == 400 and "salary_max" in resp.json()["error"]["codes"]


def test_stale_opposite_bound_edits_are_refused_on_the_locked_row(employer, draft):
    """A and B both read (10, 30). A raises the minimum to 25 and commits; B,
    validated against 30, lowers the maximum to 20. B must be refused."""
    stale_a, stale_b = JobPost.objects.get(pk=draft.pk), JobPost.objects.get(pk=draft.pk)
    services.edit_job(stale_a, {"salary_min": Decimal("25")}, actor=owner_of(employer))
    with pytest.raises(services.JobFieldsInvalid) as exc:
        services.edit_job(stale_b, {"salary_max": Decimal("20")}, actor=owner_of(employer))
    assert list(exc.value.errors) == ["salary_max"]
    row = JobPost.objects.get(pk=draft.pk)
    assert (row.salary_min, row.salary_max) == (Decimal("25"), Decimal("30"))


def test_stale_governorate_and_city_edits_are_refused(employer, draft, baghdad, basra):
    city_b = City.objects.filter(governorate=baghdad).first()
    stale_a, stale_b = JobPost.objects.get(pk=draft.pk), JobPost.objects.get(pk=draft.pk)
    services.edit_job(stale_a, {"governorate": basra, "city": None}, actor=owner_of(employer))
    with pytest.raises(services.JobFieldsInvalid) as exc:
        services.edit_job(stale_b, {"city": city_b}, actor=owner_of(employer))
    assert list(exc.value.errors) == ["city"]
    row = JobPost.objects.get(pk=draft.pk)
    assert row.governorate_id == basra.pk and row.city_id is None


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_opposite_bound_patches_never_500(employer_factory, job_factory):
    employer = employer_factory(plan_code="PROFESSIONAL")
    job = job_factory(employer, status=JobStatus.DRAFT, salary_min=10, salary_max=30)
    barrier = threading.Barrier(2)
    outcomes: list[int] = []

    def run(payload):
        try:
            barrier.wait(timeout=10)
            outcomes.append(_patch(employer, job, payload).status_code)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=({"salary_min": "25"},)),
        threading.Thread(target=run, args=({"salary_max": "20"},)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == [200, 400], outcomes
    row = JobPost.objects.get(pk=job.pk)
    assert row.salary_min <= row.salary_max


def test_unrelated_database_errors_are_not_swallowed(employer, draft, monkeypatch):
    def broken(self, *args, **kwargs):
        raise IntegrityError("some other constraint")

    monkeypatch.setattr(JobPost, "save", broken)
    with pytest.raises(IntegrityError):
        _patch(employer, draft, {"title": "Renamed"})
