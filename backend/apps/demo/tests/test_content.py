"""The dataset itself: realistic, fictional, consistent, inside the requested volumes."""

import re

from apps.demo.content import common, estate, jobs, market, people, providers
from apps.jobs.types import (
    Degree,
    EmploymentType,
    JobStatus,
    Profession,
    ShiftType,
    WorkMode,
)
from apps.real_estate.types import PropertyType, SuitableUse, TransactionType

FORBIDDEN = re.compile(
    r"\b(foo|bar|abc|lorem|ipsum|sample)\b|test (user|company|product|provider)"
    r"|(product|user|company) \d",
    re.I,
)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def test_no_developer_fixture_style_text_anywhere():
    for module in (providers, market, jobs, estate, people):
        for name in dir(module):
            if name.isupper():
                for text in _strings(getattr(module, name)):
                    assert not FORBIDDEN.search(text), (module.__name__, name, text)


def test_volumes_match_the_requested_targets():
    assert 20 <= len(providers.PRACTITIONERS) <= 30
    assert 6 <= len(providers.FACILITIES) <= 10
    pharma = [c for c in market.COMPANIES if c[3] == "pharma"]
    equipment = [c for c in market.COMPANIES if c[3] == "equipment"]
    assert 5 <= len(pharma) <= 8 and 5 <= len(equipment) <= 8
    assert 40 <= len(market.PRODUCTS) <= 60
    assert 15 <= len(jobs.JOBS) <= 25 + 5  # 15-25 live postings plus draft/pending/closed examples
    assert 15 <= len(estate.LISTINGS) <= 25


def test_keys_are_unique_and_references_resolve():
    practitioner_keys = [p[0] for p in providers.PRACTITIONERS]
    facility_keys = [f[0] for f in providers.FACILITIES]
    assert len(set(practitioner_keys + facility_keys)) == len(practitioner_keys + facility_keys)
    assert {p[11] for p in providers.PRACTITIONERS if p[11]} <= set(facility_keys)
    assert set(people.REVIEW_PLAN) <= set(practitioner_keys + facility_keys)
    assert {c[1] for c in people.CHATS} <= set(practitioner_keys)
    company_keys = {c[0] for c in market.COMPANIES}
    assert {p[0] for p in market.PRODUCTS} <= company_keys
    assert {p[1] for p in market.PRODUCTS} <= {c[0] for c in market.CATEGORIES}
    assert {e[0] for e in jobs.EMPLOYERS if e[1] == "facility"} <= set(facility_keys)
    assert {e[0] for e in jobs.EMPLOYERS if e[1] == "company"} <= company_keys
    assert {j[0] for j in jobs.JOBS} <= {e[0] for e in jobs.EMPLOYERS}
    seeker_keys = {s[0] for s in jobs.SEEKERS}
    assert {a[1] for a in jobs.APPLICATIONS} <= seeker_keys
    assert all(0 <= a[0] < len(jobs.JOBS) for a in jobs.APPLICATIONS)
    assert {s[0] for s in estate.SELLERS} >= {r[0] for r in estate.LISTINGS}


def test_every_enum_value_used_is_a_real_platform_value():
    for j in jobs.JOBS:
        assert j[3] in Profession.values and j[5] in Degree.values
        assert j[9] in EmploymentType.values and j[10] in WorkMode.values
        assert j[11] in ShiftType.values and j[15] in JobStatus.values
    for s in jobs.SEEKERS:
        assert s[3] in Profession.values and s[5] in Degree.values
    for r in estate.LISTINGS:
        assert r[3] in PropertyType.values and r[4] in TransactionType.values
        assert set(r[10]) <= set(SuitableUse.values)


def test_arabic_text_is_present_and_demo_notice_is_explicit():
    arabic = re.compile(r"[؀-ۿ]")
    assert all(arabic.search(f[2]) for f in providers.FACILITIES)
    assert all(arabic.search(c[1]) for c in market.COMPANIES)
    assert "فقط" in common.DEMO_NOTE_AR and "fictional" in common.DEMO_NOTE_EN
    assert common.EMAIL_DOMAIN.endswith(".invalid")


def test_review_plan_gives_varied_ratings_not_all_fives():
    means = {k: sum(v) / len(v) for k, v in people.REVIEW_PLAN.items()}
    assert min(means.values()) < 4.1 and max(means.values()) > 4.7
    assert all(3.0 <= m <= 5.0 for m in means.values())
    assert not all(r == 5 for v in people.REVIEW_PLAN.values() for r in v)
