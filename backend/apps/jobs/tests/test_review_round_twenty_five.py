"""Twenty-fifth Codex review of PR #4 (commit 3e29f13): a child-row PATCH that
loses a race against DELETE (or whose row left the caller's scope) gets the
endpoint's typed not-found from the locked re-read, never a 500."""

import threading
from types import SimpleNamespace

import pytest
from django.db import DatabaseError, connection
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from apps.jobs import serializers as ser
from apps.jobs import views
from apps.jobs.models import Credential, Education, LanguageSkill, Skill, WorkExperience

pytestmark = pytest.mark.django_db
XP = "/api/v1/jobs/me/profile/experiences"


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


def _choice(model, field):
    return model._meta.get_field(field).choices[0][0]


def _row(model, profile):
    """One minimal row per child model, created the way the API would."""
    if model is WorkExperience:
        return model.objects.create(
            profile=profile, title="Nurse", organization_name="Hospital A", start_date="2020-01-01"
        )
    if model is Education:
        return model.objects.create(
            profile=profile,
            degree=_choice(model, "degree"),
            field_of_study="Nursing",
            institution_name="University",
            start_year=2015,
        )
    if model is Skill:
        return model.objects.create(profile=profile, name="ICU")
    if model is LanguageSkill:
        return model.objects.create(
            profile=profile, language="Arabic", level=_choice(model, "level")
        )
    return model.objects.create(profile=profile, kind=_choice(model, "kind"), name="BLS")


CHILDREN = [
    (
        WorkExperience,
        ser.WorkExperienceSerializer,
        views.MyExperienceDetailView,
        {"title": "Senior"},
    ),
    (
        Education,
        ser.EducationSerializer,
        views.MyEducationDetailView,
        {"field_of_study": "Midwifery"},
    ),
    (Skill, ser.SkillSerializer, views.MySkillDetailView, {"name": "Triage"}),
    (
        LanguageSkill,
        ser.LanguageSkillSerializer,
        views.MyLanguageDetailView,
        {"language": "Kurdish"},
    ),
    (Credential, ser.CredentialSerializer, views.MyCredentialDetailView, {"name": "ACLS"}),
]


def _view(view_cls, seeker):
    view = view_cls()
    view.request = SimpleNamespace(job_seeker=seeker)
    return view


@pytest.mark.parametrize(
    "model,serializer_cls,view_cls,payload", CHILDREN, ids=lambda x: getattr(x, "__name__", "")
)
def test_every_child_model_gets_a_typed_not_found_when_its_row_vanished(
    seeker, model, serializer_cls, view_cls, payload
):
    """The PATCH validated against a row that a concurrent DELETE then removed."""
    row = _row(model, seeker)
    serializer = serializer_cls(
        row, data=payload, partial=True, context={"request": _view(view_cls, seeker).request}
    )
    assert serializer.is_valid(), serializer.errors
    model.objects.filter(pk=row.pk).delete()  # the DELETE committed first
    with pytest.raises(NotFound) as exc:
        _view(view_cls, seeker).perform_update(serializer)
    assert exc.value.status_code == 404
    assert not model.objects.filter(pk=row.pk).exists()  # nothing recreated


def test_a_row_moved_out_of_scope_is_the_same_not_found(seeker, seeker_factory):
    """Scoping is unchanged: another profile's row is invisible before and after the lock."""
    other = seeker_factory()
    row = _row(WorkExperience, other)
    assert (
        _client(seeker.account).patch(f"{XP}/{row.pk}", {"title": "X"}, format="json").status_code
        == 404
    )
    serializer = ser.WorkExperienceSerializer(row, data={"title": "X"}, partial=True)
    assert serializer.is_valid()
    with pytest.raises(NotFound):
        _view(views.MyExperienceDetailView, seeker).perform_update(serializer)
    assert WorkExperience.objects.get(pk=row.pk).title == "Nurse"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_patch_racing_delete_never_500s_and_never_recreates_the_row(seeker_factory):
    seeker = seeker_factory()
    row = _row(WorkExperience, seeker)
    barrier = threading.Barrier(2)
    outcomes: dict[str, int] = {}

    def run(name, method, payload=None):
        try:
            barrier.wait(timeout=10)
            client = _client(seeker.account)
            resp = (
                client.patch(f"{XP}/{row.pk}", payload, format="json")
                if method == "patch"
                else client.delete(f"{XP}/{row.pk}")
            )
            outcomes[name] = resp.status_code
        finally:
            connection.close()

    threads = [
        threading.Thread(target=run, args=("patch", "patch", {"title": "Senior nurse"})),
        threading.Thread(target=run, args=("delete", "delete")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert outcomes["delete"] == 204, outcomes
    assert outcomes["patch"] in (200, 404), outcomes  # updated before the delete, or not found
    assert not WorkExperience.objects.filter(pk=row.pk).exists()


def test_delete_path_already_handles_missing_and_out_of_scope_rows(seeker, seeker_factory):
    row = _row(WorkExperience, seeker)
    client = _client(seeker.account)
    assert client.delete(f"{XP}/{row.pk}").status_code == 204
    assert client.delete(f"{XP}/{row.pk}").status_code == 404
    foreign = _row(WorkExperience, seeker_factory())
    assert client.delete(f"{XP}/{foreign.pk}").status_code == 404
    assert WorkExperience.objects.filter(pk=foreign.pk).exists()


def test_unrelated_database_errors_are_not_turned_into_not_found(seeker, monkeypatch):
    row = _row(WorkExperience, seeker)
    serializer = ser.WorkExperienceSerializer(row, data={"title": "X"}, partial=True)
    assert serializer.is_valid()

    def broken(*args, **kwargs):
        raise DatabaseError("connection lost")

    monkeypatch.setattr(WorkExperience, "save", broken)
    with pytest.raises(DatabaseError):
        _view(views.MyExperienceDetailView, seeker).perform_update(serializer)


def test_round_twenty_four_date_rule_still_holds_on_the_locked_row(seeker):
    row = WorkExperience.objects.create(
        profile=seeker,
        title="Nurse",
        organization_name="A",
        start_date="2020-01-01",
        end_date="2025-01-01",
    )
    stale = WorkExperience.objects.get(pk=row.pk)
    serializer = ser.WorkExperienceSerializer(stale, data={"end_date": "2021-01-01"}, partial=True)
    assert serializer.is_valid()
    WorkExperience.objects.filter(pk=row.pk).update(start_date="2024-01-01")
    with pytest.raises(Exception) as exc:
        _view(views.MyExperienceDetailView, seeker).perform_update(serializer)
    assert "end_date" in getattr(exc.value, "detail", {})
    fresh = WorkExperience.objects.get(pk=row.pk)
    assert (str(fresh.start_date), str(fresh.end_date)) == ("2024-01-01", "2025-01-01")
