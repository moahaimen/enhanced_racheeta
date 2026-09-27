"""Default-plan invariant (round twenty follow-up): for each audience,
application-supported operations cannot commit a state with zero or multiple
default plans. `is_default` and `audience` are immutable once a plan exists;
the default cannot be deleted, retired or unset."""

import uuid

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.test import Client

from apps.billing import services
from apps.billing.models import Plan
from apps.billing.types import Audience, SubjectType

pytestmark = pytest.mark.django_db
PLANS = f"/{settings.ADMIN_URL_PATH}billing/plan/"


@pytest.fixture
def django_admin(admin):
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def default_plan():
    return Plan.objects.get(audience=Audience.EMPLOYER, is_default=True)


def _form(plan, **overrides):
    data = {
        "name_ar": plan.name_ar,
        "name_en": plan.name_en,
        "description_ar": plan.description_ar,
        "description_en": plan.description_en,
        "billing_period": plan.billing_period,
        "term_days": plan.term_days,
        "price_amount": plan.price_amount or "",
        "price_currency": plan.price_currency,
        "is_active": "on" if plan.is_active else "",
        "is_public": "on" if plan.is_public else "",
        "sort_order": plan.sort_order,
        "entitlements-TOTAL_FORMS": "0",
        "entitlements-INITIAL_FORMS": "0",
        "entitlements-MIN_NUM_FORMS": "0",
        "entitlements-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v != ""}


def _resolved_default(audience):
    acc = services.get_or_create_billing_account(
        SubjectType.ORGANIZATION if audience == Audience.EMPLOYER else SubjectType.ACCOUNT,
        uuid.uuid4(),
        audience,
    )
    return services.entitlements_for(acc.subject_type, acc.subject_id, acc.audience).plan


def test_every_audience_has_exactly_one_active_default():
    for audience, _ in Audience.choices:
        assert Plan.objects.filter(audience=audience, is_default=True, is_active=True).count() == 1
        assert _resolved_default(audience).audience == audience


def test_the_default_cannot_be_unset_through_save(default_plan):
    default_plan.is_default = False
    with pytest.raises(ValidationError) as exc:
        default_plan.save()
    assert "is_default" in exc.value.message_dict
    assert Plan.objects.get(pk=default_plan.pk).is_default is True
    assert _resolved_default(Audience.EMPLOYER).pk == default_plan.pk  # resolver unaffected
    with pytest.raises(ValidationError):
        default_plan.full_clean()  # the form path sees the same rule


def test_admin_change_form_cannot_untick_the_default(django_admin, default_plan):
    html = django_admin.get(f"{PLANS}{default_plan.pk}/change/").content.decode()
    assert 'name="is_default"' not in html  # read-only for an existing plan
    assert 'name="price_amount"' in html  # configuration stays editable
    # a crafted POST without the flag (what "unticking" would send) changes nothing
    resp = django_admin.post(
        f"{PLANS}{default_plan.pk}/change/", _form(default_plan, price_amount="12345")
    )
    assert resp.status_code == 302
    row = Plan.objects.get(pk=default_plan.pk)
    assert row.is_default is True and row.price_amount == 12345
    assert _resolved_default(Audience.EMPLOYER).pk == default_plan.pk


def test_no_second_default_can_be_created(django_admin, default_plan):
    with pytest.raises(ValidationError) as exc:
        Plan.objects.create(
            code="second-default",
            audience=Audience.EMPLOYER,
            name_ar="x",
            name_en="x",
            is_default=True,
        )
    assert "is_default" in exc.value.message_dict
    resp = django_admin.post(
        f"{PLANS}add/",
        _form(default_plan, code="second-default", audience=Audience.EMPLOYER, is_default="on"),
    )
    assert resp.status_code == 200 and "already has a default plan" in resp.content.decode()
    assert Plan.objects.filter(audience=Audience.EMPLOYER, is_default=True).count() == 1
    assert not Plan.objects.filter(code="second-default").exists()


def test_a_non_default_plan_cannot_be_promoted_and_keeps_its_audience(default_plan):
    other = Plan.objects.create(
        code="ordinary", audience=Audience.EMPLOYER, name_ar="x", name_en="x"
    )
    other.is_default = True
    with pytest.raises(ValidationError):
        other.save()
    other.refresh_from_db()
    other.audience = Audience.JOB_SEEKER
    with pytest.raises(ValidationError) as exc:
        other.save()
    assert "audience" in exc.value.message_dict
    default_plan.audience = Audience.JOB_SEEKER
    with pytest.raises(ValidationError):
        default_plan.save()
    assert Plan.objects.filter(is_default=True).count() == len(Audience.choices)


def test_non_default_plans_and_default_configuration_stay_editable(default_plan):
    other = Plan.objects.create(
        code="ordinary", audience=Audience.EMPLOYER, name_ar="x", name_en="x"
    )
    other.is_public, other.price_amount, other.is_active = False, 50, False
    other.save()
    default_plan.price_amount, default_plan.term_days, default_plan.name_en = 999, 45, "Trial+"
    default_plan.save()
    row = Plan.objects.get(pk=default_plan.pk)
    assert (row.price_amount, row.term_days, row.name_en, row.is_default) == (
        999,
        45,
        "Trial+",
        True,
    )


def test_the_default_can_be_neither_deleted_retired_nor_unset(default_plan):
    with pytest.raises(ProtectedError), transaction.atomic():
        default_plan.delete()
    default_plan.refresh_from_db()
    default_plan.is_active = False
    with pytest.raises(ValidationError):
        default_plan.save()
    default_plan.refresh_from_db()
    default_plan.is_default = False
    with pytest.raises(ValidationError):
        default_plan.save()
    row = Plan.objects.get(pk=default_plan.pk)
    assert row.is_default and row.is_active
