"""Twenty-fourth Codex review of PR #4 (commit 58b35ba): the work-experience
date range is re-validated on the locked row with the submitted fields
applied, so concurrent partial PATCHes never commit end_date < start_date."""

import threading

import pytest
from django.db import IntegrityError, connection
from rest_framework.test import APIClient

from apps.jobs.models import WorkExperience
from apps.jobs.serializers import WorkExperienceSerializer
from apps.jobs.views import MyExperienceDetailView

pytestmark = pytest.mark.django_db
XP = "/api/v1/jobs/me/profile/experiences"


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.fixture
def experience(seeker):
    resp = _client(seeker.account).post(
        XP,
        {
            "title": "Nurse",
            "organization_name": "Hospital A",
            "start_date": "2020-01-01",
            "end_date": "2025-01-01",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    return WorkExperience.objects.get(pk=resp.json()["id"])


def _patch(seeker, xp, payload):
    return _client(seeker.account).patch(f"{XP}/{xp.pk}", payload, format="json")


def test_single_and_simultaneous_date_updates(seeker, experience):
    assert _patch(seeker, experience, {"start_date": "2021-01-01"}).status_code == 200
    assert _patch(seeker, experience, {"end_date": "2024-06-30"}).status_code == 200
    resp = _patch(seeker, experience, {"start_date": "2018-01-01", "end_date": "2019-01-01"})
    assert resp.status_code == 200
    row = WorkExperience.objects.get(pk=experience.pk)
    assert str(row.start_date) == "2018-01-01" and str(row.end_date) == "2019-01-01"


def test_invalid_single_request_range_is_the_existing_error(seeker, experience):
    resp = _patch(seeker, experience, {"end_date": "2019-01-01"})
    assert resp.status_code == 400 and "end_date" in resp.json()["error"]["codes"]
    assert str(WorkExperience.objects.get(pk=experience.pk).end_date) == "2025-01-01"


def test_open_ended_employment_stays_valid(seeker, experience):
    assert _patch(seeker, experience, {"end_date": None, "is_current": True}).status_code == 200
    assert _patch(seeker, experience, {"start_date": "2024-01-01"}).status_code == 200
    row = WorkExperience.objects.get(pk=experience.pk)
    assert row.end_date is None and row.is_current and str(row.start_date) == "2024-01-01"


def test_unrelated_fields_update_and_omitted_fields_survive(seeker, experience):
    WorkExperience.objects.filter(pk=experience.pk).update(description="Committed meanwhile")
    assert _patch(seeker, experience, {"title": "Senior nurse"}).status_code == 200
    row = WorkExperience.objects.get(pk=experience.pk)
    assert (row.title, row.description, str(row.end_date)) == (
        "Senior nurse",
        "Committed meanwhile",
        "2025-01-01",
    )


def test_stale_request_is_refused_on_the_locked_row(seeker, experience):
    """B validated end_date=2021 against (2020, 2025); A moved start_date to
    2024 and committed. B's save must be refused with the end_date error."""
    stale = WorkExperience.objects.get(pk=experience.pk)
    serializer = WorkExperienceSerializer(stale, data={"end_date": "2021-01-01"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert _patch(seeker, experience, {"start_date": "2024-01-01"}).status_code == 200
    with pytest.raises(Exception) as exc:
        MyExperienceDetailView().perform_update(serializer)
    assert "end_date" in getattr(exc.value, "detail", {})
    row = WorkExperience.objects.get(pk=experience.pk)
    assert (str(row.start_date), str(row.end_date)) == ("2024-01-01", "2025-01-01")


@pytest.mark.parametrize("first", ["start", "end"])
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_opposite_date_patches_never_commit_an_inverted_range(seeker_factory, first):
    seeker = seeker_factory()
    xp = WorkExperience.objects.create(
        profile=seeker,
        title="Nurse",
        organization_name="Hospital A",
        start_date="2020-01-01",
        end_date="2025-01-01",
    )
    payloads = [{"start_date": "2024-01-01"}, {"end_date": "2021-01-01"}]
    if first == "end":
        payloads.reverse()
    barrier = threading.Barrier(2)
    outcomes: list[int] = []

    def run(payload):
        try:
            barrier.wait(timeout=10)
            outcomes.append(_patch(seeker, xp, payload).status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(p,)) for p in payloads]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == [200, 400], outcomes
    row = WorkExperience.objects.get(pk=xp.pk)
    assert row.end_date is None or row.end_date >= row.start_date


def test_unrelated_integrity_errors_still_propagate(seeker, experience, monkeypatch):
    def broken(self, *args, **kwargs):
        raise IntegrityError("some other constraint")

    monkeypatch.setattr(WorkExperience, "save", broken)
    with pytest.raises(IntegrityError):
        _patch(seeker, experience, {"title": "X"})
