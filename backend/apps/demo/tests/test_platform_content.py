"""The platform-completion demo content only uses codes the product accepts (the local phase
itself runs against the guarded local demo database: seed → seed → clear → seed)."""

from apps.accounts.roles import ACCOUNT_TYPE_PROVIDER, AccountType
from apps.demo.content import platform as pc
from apps.jobs.types import CLINICAL_PROFESSIONS, Degree, Profession
from apps.real_estate.types import INQUIRY_MESSAGE_MAX


def test_typed_providers_match_the_onboarding_presets():
    for _key, _name, ptype, spec, kind, _gov, _city in pc.TYPED_PROVIDERS:
        assert kind in AccountType.values
        assert ACCOUNT_TYPE_PROVIDER[kind] == (ptype, spec)


def test_business_employer_only_posts_non_clinical_roles():
    for _suffix, _ar, _en, profession, degree, _years, low, high in pc.BUSINESS_JOBS:
        assert profession in Profession.values and profession not in CLINICAL_PROFESSIONS
        assert degree in Degree.values and 0 < low <= high


def test_seekers_setup_accounts_and_inquiries_are_valid():
    for _key, _name, profession, _title, degree, _years in pc.TYPED_SEEKERS:
        assert profession in Profession.values and degree in Degree.values
    assert {kind for _k, _n, kind in pc.SETUP_ACCOUNTS} == {"EMPLOYER", "JOB_SEEKER"}
    suffixes = {row[0] for row in pc.BUSINESS_JOBS}
    assert all(suffix in suffixes for _key, suffix in pc.BUSINESS_APPLICATIONS)
    outcomes = {row[4] for row in pc.INQUIRIES}
    assert outcomes == {"open", "answered", "closed", "withdrawn"}
    assert all(10 <= len(row[5]) <= INQUIRY_MESSAGE_MAX for row in pc.INQUIRIES)


def test_the_demo_has_a_live_lab_only_campaign_on_a_lab_product():
    """The lab positive case is demonstrable: a live, paid campaign narrowed to laboratories, on
    an unrestricted B2B product of a lab supplier whose category reaches laboratories."""
    from apps.demo.content import local_extras as lx
    from apps.demo.content import market

    rows = {row[0]: row for row in lx.CAMPAIGNS}
    key, company, product, status, payment, offset, length, ptypes, specs = rows["lab-live"]
    assert (status, payment, ptypes, specs) == ("ACTIVE", "VERIFIED", ["LABORATORY"], [])
    assert offset <= 0 < offset + length  # live today
    products = {row[0]: row for row in lx.EXTRA_PRODUCTS}
    _k, owner, category, _ar, _en, _price, channel, restricted, _stock = products[product]
    assert owner == company and channel == "B2B" and restricted is False
    audiences = {row[0]: row[3] for row in market.CATEGORIES}
    assert "LABORATORY" in audiences[category] and len(audiences[category]) > 1  # narrowed
