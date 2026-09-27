"""Phase 3 production smoke: one end-to-end walk through every primary
workflow over the public API (employer → verification → subscription →
members → job → public search → application → review → interview → talent →
saved → invitation → messages → negative paths). Kept deliberately linear so a
broken step is obvious."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import Subscription

pytestmark = pytest.mark.django_db


def _client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


def test_phase3_end_to_end(account_factory, admin_client, baghdad):
    owner_acc = account_factory(role="PROVIDER")
    recruiter_acc = account_factory(role="PROVIDER")
    viewer_acc = account_factory(role="PROVIDER")
    seeker_acc = account_factory(role="PATIENT")
    seeker2_acc = account_factory(role="PATIENT")
    owner, recruiter, viewer = _client(owner_acc), _client(recruiter_acc), _client(viewer_acc)
    seeker, seeker2, anon = _client(seeker_acc), _client(seeker2_acc), APIClient()

    # 1. create + verify the employer
    r = owner.post(
        "/api/v1/jobs/employer",
        {"name": "Smoke Hospital", "organization_type": "HOSPITAL", "governorate": str(baghdad.pk)},
        format="json",
    )
    assert r.status_code == 201, r.content
    employer_id = r.json()["id"]
    assert r.json()["my_role"] == "OWNER"
    assert owner.post("/api/v1/jobs/employer/verification/request").status_code == 200
    r = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{employer_id}/verification",
        {"status": "VERIFIED", "note": "docs checked"},
        format="json",
    )
    assert r.status_code == 200 and r.json()["verification_status"] == "VERIFIED"

    # 12. subscription / entitlement flow (before members: seats are plan-limited)
    assert anon.get("/api/v1/billing/plans").status_code == 200
    r = owner.post("/api/v1/jobs/employer/billing/request", {"plan": "PROFESSIONAL"}, format="json")
    assert r.status_code in (200, 201), r.content
    pending = admin_client.get("/api/v1/admin/billing/subscriptions", {"status": "PENDING"}).json()
    rows = pending["results"] if isinstance(pending, dict) else pending
    sub_id = next(row["id"] for row in rows if row["plan"]["code"] == "PROFESSIONAL")
    r = admin_client.post(
        f"/api/v1/admin/billing/subscriptions/{sub_id}/activate",
        {"term_days": 30, "reference": "TRX-SMOKE"},
        format="json",
    )
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    billing = owner.get("/api/v1/jobs/employer/billing").json()
    assert (
        billing["plan"]["code"] == "PROFESSIONAL" and billing["subscription"]["status"] == "ACTIVE"
    )

    # 2. membership roles
    for acc, role in ((recruiter_acc, "RECRUITER"), (viewer_acc, "VIEWER")):
        r = owner.post(
            "/api/v1/jobs/employer/members", {"email": acc.email, "role": role}, format="json"
        )
        assert r.status_code == 201, r.content
    assert recruiter.get("/api/v1/jobs/employer").json()["my_role"] == "RECRUITER"
    assert viewer.get("/api/v1/jobs/employer").json()["my_role"] == "VIEWER"
    assert (
        recruiter.post(
            "/api/v1/jobs/employer/members",
            {"email": seeker_acc.email, "role": "VIEWER"},
            format="json",
        ).status_code
        == 403
    )

    # 3. job: create (recruiter) → submit → approve → published
    job_payload = {
        "title": "ICU nurse",
        "profession": "NURSE",
        "description": "Night shifts in the intensive care unit.",
        "governorate": str(baghdad.pk),
        "employment_type": "FULL_TIME",
    }
    assert viewer.post("/api/v1/jobs/employer/jobs", job_payload, format="json").status_code == 403
    r = recruiter.post("/api/v1/jobs/employer/jobs", job_payload, format="json")
    assert r.status_code == 201 and r.json()["status"] == "DRAFT", r.content
    job_id = r.json()["id"]
    assert anon.get(f"/api/v1/jobs/{job_id}").status_code == 404  # drafts are private
    r = recruiter.post(f"/api/v1/jobs/employer/jobs/{job_id}/submit")
    assert r.status_code == 200 and r.json()["status"] == "PENDING_ADMIN_REVIEW", r.content
    r = admin_client.post(
        f"/api/v1/admin/recruitment/jobs/{job_id}/approve", {"note": ""}, format="json"
    )
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED", r.content

    # 4. public search + detail
    ids = {row["id"] for row in anon.get("/api/v1/jobs", {"profession": "NURSE"}).json()["results"]}
    assert job_id in ids
    public = anon.get(f"/api/v1/jobs/{job_id}").json()
    assert public["title"] == "ICU nurse"
    assert "moderation_note" not in public and "verification_note" not in str(public)
    assert anon.get(f"/api/v1/employers/{employer_id}").status_code == 200

    # 5. application (seeker profile first)
    profile = {
        "professional_title": "Nurse",
        "profession": "NURSE",
        "degree": "BACHELOR",
        "governorate": str(baghdad.pk),
        "years_of_experience": 3,
        "discoverable_by_employers": True,
    }
    assert seeker.post("/api/v1/jobs/me/profile", profile, format="json").status_code in (200, 201)
    r = seeker.post(
        f"/api/v1/jobs/{job_id}/apply", {"cover_text": "Ready to start."}, format="json"
    )
    assert r.status_code == 201, r.content
    application_id = r.json()["id"]
    assert seeker.post(f"/api/v1/jobs/{job_id}/apply", {}, format="json").status_code == 409
    assert (
        seeker.post(
            f"/api/v1/jobs/{job_id}/apply", {"cover_text": "call 07701234567"}, format="json"
        ).status_code
        == 400
    )

    # 6. applicant review (viewer reads, recruiter acts)
    r = viewer.get(f"/api/v1/jobs/employer/jobs/{job_id}/applications")
    assert r.status_code == 200 and r.json()["count"] == 1
    applicant = r.json()["results"][0]
    assert "email" not in applicant["candidate"] and "phone" not in str(applicant["candidate"])
    transition = f"/api/v1/jobs/employer/applications/{application_id}/transition"
    assert viewer.post(transition, {"status": "REVIEWING"}, format="json").status_code == 403
    for status_ in ("REVIEWING", "SHORTLISTED"):
        r = recruiter.post(transition, {"status": status_}, format="json")
        assert r.status_code == 200 and r.json()["status"] == status_, r.content

    # 7. interview
    r = recruiter.post(
        f"/api/v1/jobs/employer/applications/{application_id}/interviews",
        {"proposed_at": (timezone.now() + timedelta(days=2)).isoformat(), "mode": "ONLINE"},
        format="json",
    )
    assert r.status_code == 201, r.content
    interview_id = r.json()["id"]
    assert (
        recruiter.get(f"/api/v1/jobs/employer/applications/{application_id}").json()["status"]
        == "INTERVIEW"
    )
    r = seeker.post(
        f"/api/v1/jobs/me/interviews/{interview_id}/respond", {"accept": True}, format="json"
    )
    assert r.status_code == 200 and r.json()["status"] == "ACCEPTED", r.content
    assert seeker.post(
        f"/api/v1/jobs/me/interviews/{interview_id}/respond", {"accept": False}, format="json"
    ).status_code in (400, 409)

    # 8. talent search
    assert viewer.get("/api/v1/talent", {"profession": "NURSE"}).status_code == 403
    r = recruiter.get("/api/v1/talent", {"profession": "NURSE"})
    assert r.status_code == 200, r.content
    seeker_profile_id = next(
        row["id"] for row in r.json()["results"] if row["professional_title"] == "Nurse"
    )
    assert recruiter.get(f"/api/v1/talent/{seeker_profile_id}").status_code == 200

    # 9. save candidate
    r = recruiter.post(
        "/api/v1/talent/saved", {"job_seeker": seeker_profile_id, "note": "strong"}, format="json"
    )
    assert r.status_code == 201, r.content
    saved_id = r.json()["id"]
    assert recruiter.post(
        "/api/v1/talent/saved", {"job_seeker": seeker_profile_id}, format="json"
    ).status_code in (400, 409)
    assert recruiter.get("/api/v1/talent/saved").json()["count"] == 1
    assert recruiter.delete(f"/api/v1/talent/saved/{saved_id}").status_code == 204
    assert viewer.get("/api/v1/talent/saved").status_code == 403

    # 10. invitation (second, discoverable candidate)
    assert seeker2.post(
        "/api/v1/jobs/me/profile", {**profile, "professional_title": "Nurse two"}, format="json"
    ).status_code in (200, 201)
    seeker2_profile_id = next(
        row["id"]
        for row in recruiter.get("/api/v1/talent", {"profession": "NURSE"}).json()["results"]
        if row["professional_title"] == "Nurse two"
    )
    r = recruiter.post(
        "/api/v1/talent/invitations",
        {"job": job_id, "job_seeker": seeker2_profile_id, "message": "Join us"},
        format="json",
    )
    assert r.status_code == 201, r.content
    invitation_id = r.json()["id"]
    assert (
        recruiter.post(
            "/api/v1/talent/invitations",
            {"job": job_id, "job_seeker": seeker2_profile_id},
            format="json",
        ).status_code
        == 409
    )
    assert seeker2.get("/api/v1/jobs/me/invitations").json()["count"] == 1
    r = seeker2.post(
        f"/api/v1/jobs/me/invitations/{invitation_id}/respond", {"accept": True}, format="json"
    )
    assert r.status_code == 200 and r.json()["status"] == "ACCEPTED", r.content
    assert viewer.get("/api/v1/talent/invitations").status_code == 403

    # 11. recruitment messages (both parties, never contact data, never a viewer)
    messages = f"/api/v1/recruitment/applications/{application_id}/messages"
    assert (
        recruiter.post(messages, {"body": "Please confirm the time."}, format="json").status_code
        == 201
    )
    assert seeker.post(messages, {"body": "Confirmed."}, format="json").status_code == 201
    assert len(seeker.get(messages).json()) == 2
    assert (
        recruiter.post(messages, {"body": "email me at x@y.com"}, format="json").status_code == 400
    )
    assert (
        viewer.get(messages).status_code == 404
        and viewer.post(messages, {"body": "hi"}, format="json").status_code == 404
    )
    assert seeker2.get(messages).status_code == 404

    # 13. negative paths: suspended organisation, then an expired subscription
    r = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{employer_id}/recruitment/SUSPENDED",
        {"reason": "complaint"},
        format="json",
    )
    assert r.status_code == 200, r.content
    assert job_id not in {row["id"] for row in anon.get("/api/v1/jobs").json()["results"]}
    assert anon.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert recruiter.post(transition, {"status": "ACCEPTED"}, format="json").status_code == 403
    assert recruiter.post(messages, {"body": "still here?"}, format="json").status_code == 403
    assert recruiter.get("/api/v1/talent", {"profession": "NURSE"}).status_code == 403
    assert (
        seeker.post(messages, {"body": "hello?"}, format="json").status_code == 201
    )  # the candidate may still write
    r = admin_client.post(
        f"/api/v1/admin/recruitment/employers/{employer_id}/recruitment/ACTIVE",
        {"reason": "resolved"},
        format="json",
    )
    assert r.status_code == 200
    assert anon.get(f"/api/v1/jobs/{job_id}").status_code == 200

    Subscription.objects.filter(pk=sub_id).update(ends_at=timezone.now() - timedelta(days=1))
    billing = owner.get("/api/v1/jobs/employer/billing").json()
    assert billing["subscription"] is None and billing["plan"]["code"] != "PROFESSIONAL"
    listed = admin_client.get("/api/v1/admin/billing/subscriptions", {"status": "EXPIRED"}).json()
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert sub_id in {row["id"] for row in rows}
    # the default plan carries one seat: the extra members exceed it, so adding another is refused
    r = owner.post(
        "/api/v1/jobs/employer/members",
        {"email": account_factory().email, "role": "VIEWER"},
        format="json",
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "usage_limit_reached", r.content
