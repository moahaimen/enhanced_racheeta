"""Regression tests for the ninth Codex review of PR #4 (commit 0e399c1):

1. the billing summary exposes a PENDING request separately from the ACTIVE
   subscription, without a PENDING row ever granting an entitlement;
2. a non-agency job can be repaired by submitting clearing values for both
   retained hiring fields in one save (what the web editor now sends);
4. a scope named after a write (jobs_create, talent_invite) is spent by that
   write only — listing and pagination never consume it.

(3 — linking a provider profile during employer onboarding — is already
covered by `test_employers.test_link_provider_profile_must_be_own_facility`
and `test_review_round_four.test_verified_organisation_cannot_swap_provider_profile`;
the fix for it is in the web form.)
"""

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.billing import services as billing
from apps.billing.models import Plan, Subscription
from apps.billing.types import Audience, Keys, SubjectType, SubscriptionStatus
from apps.jobs import services
from apps.jobs.models import JobPost
from apps.jobs.tests.conftest import owner_of
from apps.jobs.tests.test_jobs_lifecycle import draft_payload
from apps.jobs.types import JobStatus, VerificationStatus

pytestmark = pytest.mark.django_db

ME = "/api/v1/jobs/employer"
JOBS = f"{ME}/jobs"
BILLING = f"{ME}/billing"
INVITES = "/api/v1/talent/invitations"


def account_of(employer):
    return billing.get_or_create_billing_account(
        SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER
    )


# ---- 1. pending subscriptions in the billing summary ------------------------


def test_pending_request_is_visible_without_granting_entitlements(
    api_client, employer_factory, baghdad
):
    """The exact reload bug: after requesting a plan the summary must still say
    'you have a pending request', while entitlements stay on the default plan."""
    employer = employer_factory()  # no subscription: the TRIAL default applies
    api_client.force_authenticate(user=owner_of(employer))
    requested = api_client.post(BILLING + "/request", {"plan": "BASIC", "note": "transfer 9"})
    assert requested.status_code == 201

    body = api_client.get(BILLING).json()
    # Entitlement state is untouched by the request.
    assert body["subscription"] is None
    assert body["plan"]["code"] == "TRIAL"
    # …and the pending request is visible in its own field.
    assert body["pending_subscription"]["status"] == "PENDING"
    assert body["pending_subscription"]["plan"]["code"] == "BASIC"
    assert body["pending_subscription"]["requester_note"] == "transfer 9"

    # PENDING grants nothing: BASIC has talent search, TRIAL does not.
    ent = billing.EntitlementService(account_of(employer))
    assert ent.plan.code == "TRIAL"
    assert not ent.can(Keys.TALENT_SEARCH)


def test_summary_without_any_subscription_resolves_the_default_plan_as_before(
    api_client, employer_factory
):
    employer = employer_factory()
    api_client.force_authenticate(user=owner_of(employer))
    body = api_client.get(BILLING).json()
    assert body["subscription"] is None and body["pending_subscription"] is None
    assert body["plan"]["code"] == "TRIAL"
    assert {e["key"] for e in body["entitlements"]}  # default entitlements still resolve


def test_active_subscription_stays_effective_and_shows_no_pending(employer_client, employer):
    """ACTIVE and PENDING cannot coexist (one-live-subscription DB constraint),
    so the coexistence case is: the second request is refused and the ACTIVE
    subscription remains the effective one, with pending_subscription null."""
    body = employer_client.get(BILLING).json()
    assert body["subscription"]["status"] == "ACTIVE"
    assert body["subscription"]["plan"]["code"] == "PROFESSIONAL"
    assert body["pending_subscription"] is None

    duplicate = employer_client.post(BILLING + "/request", {"plan": "BASIC"})
    assert duplicate.status_code == 400

    after = employer_client.get(BILLING).json()
    assert after["subscription"]["plan"]["code"] == "PROFESSIONAL"
    assert after["pending_subscription"] is None


def test_suspended_subscription_plus_a_new_request_keeps_the_two_fields_apart(
    api_client, employer_factory, admin
):
    """SUSPENDED does not block a new request, so this is the one shape where a
    non-ACTIVE row and a PENDING row really do coexist: entitlements fall back
    to the default plan and the PENDING request is reported separately."""
    employer = employer_factory(plan_code="PROFESSIONAL")
    acc = account_of(employer)
    active = Subscription.objects.get(billing_account=acc, status=SubscriptionStatus.ACTIVE)
    billing.suspend_subscription(active, admin=admin, reason="unpaid")

    api_client.force_authenticate(user=owner_of(employer))
    assert api_client.post(BILLING + "/request", {"plan": "BASIC"}).status_code == 201

    body = api_client.get(BILLING).json()
    assert body["subscription"] is None  # suspended is not effective
    assert body["plan"]["code"] == "TRIAL"  # default entitlements
    assert body["pending_subscription"]["plan"]["code"] == "BASIC"


@pytest.mark.parametrize(
    "transition",
    ["suspend", "cancel", "reject", "expire"],
)
def test_finished_subscriptions_are_never_reported_as_pending(
    api_client, employer_factory, admin, transition
):
    employer = employer_factory()
    acc = account_of(employer)
    owner = owner_of(employer)
    sub = billing.request_subscription(acc, Plan.objects.get(code="BASIC"), requested_by=owner)
    if transition == "reject":
        billing.reject_subscription(sub, admin=admin, reason="no payment")
    else:
        billing.activate_subscription(sub, admin=admin, term_days=30)
        if transition == "suspend":
            billing.suspend_subscription(sub, admin=admin, reason="unpaid")
        elif transition == "cancel":
            billing.cancel_subscription(sub, admin=admin, reason="left")
        else:
            Subscription.objects.filter(pk=sub.pk).update(
                ends_at=timezone.now() - timezone.timedelta(days=1)
            )

    api_client.force_authenticate(user=owner)
    body = api_client.get(BILLING).json()
    assert body["pending_subscription"] is None
    assert body["subscription"] is None
    assert body["plan"]["code"] == "TRIAL"


def test_admin_activation_flow_is_unchanged_and_clears_the_pending_state(
    api_client, employer_factory, admin_client, admin
):
    employer = employer_factory()
    owner = owner_of(employer)
    api_client.force_authenticate(user=owner)
    assert api_client.post(BILLING + "/request", {"plan": "BASIC"}).status_code == 201
    pending_id = api_client.get(BILLING).json()["pending_subscription"]["id"]

    activated = admin_client.post(
        f"/api/v1/admin/billing/subscriptions/{pending_id}/activate", {"reference": "TRX-9"}
    )
    assert activated.status_code == 200 and activated.json()["status"] == "ACTIVE"

    body = api_client.get(BILLING).json()
    assert body["subscription"]["id"] == pending_id and body["subscription"]["status"] == "ACTIVE"
    assert body["pending_subscription"] is None
    assert body["plan"]["code"] == "BASIC"


# ---- 2. repairing a former agency's retained hiring fields ------------------


def test_clearing_both_hiring_fields_in_one_save_repairs_a_former_agency_draft(
    api_client, employer_factory, employer, baghdad, admin
):
    """What the web editor now sends for a non-agency job: hiring_employer=null
    AND hiring_organization_name="" on every save, so a draft created while the
    organisation was an agency stops being un-editable."""
    agency = employer_factory(
        verified=False, is_recruitment_agency=True, organization_type="RECRUITMENT_AGENCY"
    )
    api_client.force_authenticate(user=owner_of(agency))
    created = api_client.post(
        JOBS,
        draft_payload(
            baghdad,
            hiring_employer=str(employer.id),
            hiring_organization_name="Karrada clinic",
        ),
    )
    assert created.status_code == 201
    job = JobPost.objects.get(pk=created.json()["id"])
    assert job.hiring_employer_id and job.hiring_organization_name

    # The organisation stops being an agency; the draft keeps both values.
    assert api_client.patch(ME, {"is_recruitment_agency": False}, format="json").status_code == 200
    services.set_employer_verification(agency, VerificationStatus.VERIFIED, admin=admin)

    # A save that does not clear them is still refused (the round-eight rule).
    blocked = api_client.patch(f"{JOBS}/{job.id}", {"title": "Renamed"}, format="json")
    assert blocked.status_code == 400

    # The editor's payload clears both at once and the save succeeds.
    repaired = api_client.patch(
        f"{JOBS}/{job.id}",
        {"title": "Renamed", "hiring_employer": None, "hiring_organization_name": ""},
        format="json",
    )
    assert repaired.status_code == 200, repaired.content
    job.refresh_from_db()
    assert job.title == "Renamed"
    assert job.hiring_employer_id is None and job.hiring_organization_name == ""

    # …and the draft can be submitted afterwards.
    submitted = api_client.post(f"{JOBS}/{job.id}/submit")
    assert submitted.status_code == 200, submitted.content
    job.refresh_from_db()
    assert job.status != JobStatus.DRAFT


def test_an_agency_save_still_keeps_its_hiring_fields(
    api_client, employer_factory, employer, baghdad
):
    agency = employer_factory(
        is_recruitment_agency=True, organization_type="RECRUITMENT_AGENCY", plan_code="PROFESSIONAL"
    )
    api_client.force_authenticate(user=owner_of(agency))
    created = api_client.post(JOBS, draft_payload(baghdad, hiring_employer=str(employer.id)))
    assert created.status_code == 201
    job_id = created.json()["id"]
    edited = api_client.patch(
        f"{JOBS}/{job_id}",
        {"hiring_employer": str(employer.id), "hiring_organization_name": "Karrada clinic"},
        format="json",
    )
    assert edited.status_code == 200
    job = JobPost.objects.get(pk=job_id)
    assert job.hiring_employer_id == employer.id
    assert job.hiring_organization_name == "Karrada clinic"


# ---- 4. write-scoped throttles ----------------------------------------------


@pytest.fixture
def tight_jobs_create(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "jobs_create", "3/hour")
    cache.clear()
    yield
    cache.clear()


def test_listing_jobs_never_consumes_the_creation_throttle(
    employer_client, baghdad, tight_jobs_create
):
    """The reported bug: a workspace refresh used to spend the create quota."""
    for _ in range(30):
        assert employer_client.get(JOBS).status_code == 200

    # The full creation allowance is still available after all that listing.
    for _ in range(3):
        assert employer_client.post(JOBS, draft_payload(baghdad)).status_code == 201
    assert employer_client.post(JOBS, draft_payload(baghdad)).status_code == 429

    # And listing still works once creation is exhausted.
    assert employer_client.get(JOBS).status_code == 200


def test_job_creation_still_respects_its_own_throttle(employer_client, baghdad, monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "jobs_create", "2/hour")
    cache.clear()
    assert employer_client.post(JOBS, draft_payload(baghdad)).status_code == 201
    assert employer_client.post(JOBS, draft_payload(baghdad)).status_code == 201
    throttled = employer_client.post(JOBS, draft_payload(baghdad))
    assert throttled.status_code == 429
    assert throttled.json()["error"]["code"] == "throttled"


def test_listing_invitations_never_consumes_the_invitation_throttle(employer_client, monkeypatch):
    """Same misuse found in the targeted audit: `talent_invite` is a write
    quota that was attached to a GET+POST view."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "talent_invite", "2/hour")
    cache.clear()
    for _ in range(10):
        assert employer_client.get(INVITES).status_code == 200
    # POST is still throttled: the scope is counted before the view runs, so
    # two attempts (rejected on their payload) exhaust it and the third is 429.
    assert employer_client.post(INVITES, {}, format="json").status_code == 400
    assert employer_client.post(INVITES, {}, format="json").status_code == 400
    assert employer_client.post(INVITES, {}, format="json").status_code == 429
    # Reading the list is still available after the write quota is gone.
    assert employer_client.get(INVITES).status_code == 200
