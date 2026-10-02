"""Recruiter dashboard for the caller's CURRENT organisation.

Mirrors the existing applicant-read gate (`jobs.views._require_application_review`): application
and interview aggregates are included only while the organisation may still recruit AND its plan
carries `jobs.application_review`; otherwise they are `None` with an explicit machine-readable
reason, never silently zero. Job counts are the organisation's own and stay visible to every
member. Recruitment-specific messaging is not touched.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.billing.types import Keys
from apps.jobs import services as jobs_services
from apps.jobs.models import EmployerMembership, InterviewRequest, JobApplication, JobPost
from apps.jobs.types import ApplicationStatus, InterviewStatus, JobStatus, MemberStatus

from .common import status_counts

RECENT_APPLICATION_DAYS = 7

ACCESS_OK = None
ACCESS_ORGANIZATION_NOT_VERIFIED = "organization_not_verified"
ACCESS_PLAN_REQUIRED = "plan_required"


def recruiter_summary(membership, *, now=None) -> dict:
    now = now or timezone.now()
    employer = membership.employer
    entitlements = jobs_services.employer_entitlements(employer)

    # Jobs: open_now uses the same rule as JobPost.is_open (published, organisation may recruit,
    # deadline day still open), expressed in SQL.
    open_filter = Q(status=JobStatus.PUBLISHED) & (
        Q(application_deadline__isnull=True) | Q(application_deadline__gte=timezone.localdate(now))
    )
    jobs = status_counts(
        JobPost.objects.filter(employer=employer),
        "status",
        JobStatus.values,
        open_now=Count("pk", filter=open_filter),
    )
    if not employer.can_recruit:
        jobs["open_now"] = 0  # a suspended/unverified organisation has no open jobs

    if not employer.can_recruit:
        reason = ACCESS_ORGANIZATION_NOT_VERIFIED
    elif not entitlements.can(Keys.JOBS_APPLICATION_REVIEW):
        reason = ACCESS_PLAN_REQUIRED
    else:
        reason = ACCESS_OK

    applications = interviews = None
    if reason is ACCESS_OK:
        since = now - timedelta(days=RECENT_APPLICATION_DAYS)
        counted = status_counts(
            JobApplication.objects.filter(job__employer=employer),
            "status",
            ApplicationStatus.values,
            last_7_days=Count("pk", filter=Q(submitted_at__gte=since)),
        )
        applications = {
            "total": counted["total"],
            "by_status": counted["by_status"],
            "awaiting_review": counted["by_status"][ApplicationStatus.SUBMITTED],
            "last_7_days": counted["last_7_days"],
        }
        interview_counts = status_counts(
            InterviewRequest.objects.filter(application__job__employer=employer),
            "status",
            InterviewStatus.values,
        )
        interviews = {
            "total": interview_counts["total"],
            "by_status": interview_counts["by_status"],
        }

    seat = entitlements.get(Keys.RECRUITER_SEATS)
    active_members = EmployerMembership.objects.filter(
        employer=employer, status=MemberStatus.ACTIVE
    ).count()

    return {
        "organization": {
            "id": employer.pk,
            "name": employer.name,
            "verification_status": employer.verification_status,
            "recruitment_status": employer.recruitment_status,
            "can_recruit": employer.can_recruit,
            "my_role": membership.role,
        },
        "jobs": {
            "total": jobs["total"],
            "by_status": jobs["by_status"],
            "open_now": jobs["open_now"],
        },
        "applications_access": reason,
        "applications": applications,
        "interviews": interviews,
        "seats": {
            "active_members": active_members,
            "enabled": bool(seat.enabled),
            # Same arithmetic the seat check enforces: plan limit plus credits; null = unlimited.
            "limit": None if seat.limit is None else seat.limit + seat.credits,
        },
    }
