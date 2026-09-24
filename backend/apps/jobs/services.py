"""Jobs use-cases. Views stay thin; every commercial gate goes through
apps.billing and every privileged change is audited."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.billing import services as billing
from apps.billing.types import Audience, Keys, SubjectType
from apps.moderation.contact_leak import detector

from .models import (
    Employer,
    EmployerMembership,
    InterviewRequest,
    JobApplication,
    JobApplicationTransition,
    JobInvitation,
    JobPost,
    JobPostTransition,
    JobSeekerProfile,
    RecruitmentMessage,
    SavedCandidate,
    TalentSearchQuery,
)
from .types import (
    ACTIVE_APPLICATION_STATUSES,
    EMPLOYER_APPLICATION_TRANSITIONS,
    SEEKER_WITHDRAWABLE,
    ApplicationStatus,
    InterviewStatus,
    InvitationStatus,
    JobStatus,
    MemberRole,
    MemberStatus,
    MessageSide,
    RecruitmentStatus,
    VerificationStatus,
)

INVITATION_TTL = timedelta(days=14)
ACTIVE_JOB_STATUSES = (JobStatus.PENDING_ADMIN_REVIEW, JobStatus.PUBLISHED)


class JobsError(Exception):
    code = "invalid_transition"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


class NotOpen(JobsError):
    code = "job_not_open"


class AlreadyApplied(JobsError):
    code = "already_applied"


class AlreadyInvited(JobsError):
    code = "already_invited"


class OrganizationNotVerified(JobsError):
    code = "organization_not_verified"


class ContactLeak(JobsError):
    code = "contact_information_not_allowed"


# ---- billing helpers ------------------------------------------------------


def employer_entitlements(employer: Employer) -> billing.EntitlementService:
    return billing.entitlements_for(SubjectType.ORGANIZATION, employer.pk, Audience.EMPLOYER)


def seeker_entitlements(profile: JobSeekerProfile) -> billing.EntitlementService:
    return billing.entitlements_for(SubjectType.ACCOUNT, profile.account_id, Audience.JOB_SEEKER)


# ---- employers -------------------------------------------------------------


def membership_for(account) -> EmployerMembership | None:
    if not getattr(account, "is_authenticated", False):
        return None
    return (
        EmployerMembership.objects.select_related(
            "employer", "employer__governorate", "employer__city"
        )
        .filter(account=account, status=MemberStatus.ACTIVE)
        .first()
    )


@transaction.atomic
def create_employer(account, **fields) -> Employer:
    if membership_for(account) is not None:
        raise JobsError("This account already belongs to an organisation.", code="already_member")
    employer = Employer.objects.create(created_by=account, **fields)
    EmployerMembership.objects.create(employer=employer, account=account, role=MemberRole.OWNER)
    audit.record(
        actor=account, action="jobs.employer.created", target=employer, summary=employer.name
    )
    return employer


def request_employer_verification(employer: Employer, *, actor) -> Employer:
    if employer.verification_status not in (
        VerificationStatus.UNVERIFIED,
        VerificationStatus.REJECTED,
    ):
        raise JobsError(f"Verification cannot be requested from {employer.verification_status}.")
    employer.verification_status = VerificationStatus.PENDING
    employer.verification_requested_at = timezone.now()
    employer.save(update_fields=["verification_status", "verification_requested_at", "updated_at"])
    audit.record(actor=actor, action="jobs.employer.verification_requested", target=employer)
    return employer


def set_employer_verification(
    employer: Employer, status: str, *, admin, note: str = ""
) -> Employer:
    if status not in (
        VerificationStatus.VERIFIED,
        VerificationStatus.REJECTED,
        VerificationStatus.SUSPENDED,
        VerificationStatus.UNVERIFIED,
    ):
        raise JobsError("Not an administrator-settable status.")
    employer.verification_status = status
    employer.verification_note = note
    if status == VerificationStatus.VERIFIED:
        employer.verified_at = timezone.now()
    employer.save(
        update_fields=["verification_status", "verification_note", "verified_at", "updated_at"]
    )
    audit.record(
        actor=admin,
        action="jobs.employer.verification_set",
        target=employer,
        summary=f"{status}: {note}"[:255],
    )
    return employer


def set_employer_recruitment_status(
    employer: Employer, status: str, *, admin, reason: str = ""
) -> Employer:
    employer.recruitment_status = status
    employer.save(update_fields=["recruitment_status", "updated_at"])
    audit.record(
        actor=admin,
        action="jobs.employer.recruitment_status_set",
        target=employer,
        summary=f"{status}: {reason}"[:255],
    )
    return employer


@transaction.atomic
def _lock_employer(employer: Employer) -> Employer:
    """Serialises every check-then-commit on a shared commercial resource of the
    organisation (active-job slots, featured slots, recruiter seats). Row lock
    only; no process-local locks, no Redis."""
    return Employer.objects.select_for_update().get(pk=employer.pk)


def _active_job_count(employer: Employer, *, exclude: JobPost | None = None) -> int:
    qs = JobPost.objects.filter(employer=employer, status__in=ACTIVE_JOB_STATUSES)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.count()


def _require_active_job_slot(employer: Employer, job: JobPost) -> None:
    """The single gate for entering an active status (submit and restore)."""
    ent = employer_entitlements(employer)
    ent.require(Keys.JOBS_POST)
    ent.check_concurrent(Keys.JOBS_ACTIVE_LIMIT, current=_active_job_count(employer, exclude=job))


@transaction.atomic
def add_member(employer: Employer, account, role: str, *, actor) -> EmployerMembership:
    if role == MemberRole.OWNER:
        raise JobsError("Ownership cannot be granted through this action.", code="invalid_role")
    _lock_employer(employer)
    if EmployerMembership.objects.filter(account=account, status=MemberStatus.ACTIVE).exists():
        raise JobsError("This account already belongs to an organisation.", code="already_member")
    seats = EmployerMembership.objects.filter(employer=employer, status=MemberStatus.ACTIVE).count()
    employer_entitlements(employer).check_concurrent(Keys.RECRUITER_SEATS, current=seats)
    membership = EmployerMembership.objects.create(employer=employer, account=account, role=role)
    audit.record(
        actor=actor,
        action="jobs.employer.member_added",
        target=employer,
        data={"account": str(account.pk), "role": role},
    )
    return membership


def end_membership(membership: EmployerMembership, *, actor) -> EmployerMembership:
    if membership.role == MemberRole.OWNER:
        raise JobsError("The owner membership cannot be ended.", code="invalid_role")
    membership.status = MemberStatus.ENDED
    membership.ended_at = timezone.now()
    membership.save(update_fields=["status", "ended_at", "updated_at"])
    audit.record(
        actor=actor,
        action="jobs.employer.member_ended",
        target=membership.employer,
        data={"account": str(membership.account_id)},
    )
    return membership


# ---- job posts -------------------------------------------------------------


def _job_transition(job: JobPost, to_status: str, *, actor, reason: str = "") -> None:
    JobPostTransition.objects.create(
        job=job,
        from_status=job.status,
        to_status=to_status,
        actor=actor if getattr(actor, "pk", None) else None,
        reason=reason,
    )
    job.status = to_status


def contact_flags(job: JobPost) -> list[dict]:
    flags = []
    for field in (
        "title",
        "description",
        "responsibilities",
        "requirements",
        "workplace_text",
        "hiring_organization_name",
    ):
        for finding in detector.scan(getattr(job, field, "")):
            flags.append(
                {"field": field, "category": finding.category, "excerpt": finding.excerpt[:80]}
            )
    return flags


def submit_job_for_review(job: JobPost, *, actor) -> JobPost:
    """Employer: DRAFT/REJECTED → PENDING_ADMIN_REVIEW. Commercial gate + leak gate."""
    if job.status not in (JobStatus.DRAFT, JobStatus.REJECTED):
        raise JobsError(f"A job in status {job.status} cannot be submitted.")
    employer = job.employer
    if not employer.can_recruit:
        raise OrganizationNotVerified(
            "The organisation must be verified and active before publishing jobs."
        )
    flags = contact_flags(job)
    if flags:
        # Persisted outside the submission transaction so employer and admin can see why.
        job.moderation_flags = flags
        job.save(update_fields=["moderation_flags", "updated_at"])
        raise ContactLeak("Direct contact information is not allowed in recruitment content.")
    return _submit_job(job, actor=actor)


@transaction.atomic
def _submit_job(job: JobPost, *, actor) -> JobPost:
    employer = _lock_employer(job.employer)
    _require_active_job_slot(employer, job)
    _job_transition(job, JobStatus.PENDING_ADMIN_REVIEW, actor=actor)
    job.submitted_at = timezone.now()
    job.moderation_flags = []
    job.save(update_fields=["status", "submitted_at", "moderation_flags", "updated_at"])
    audit.record(actor=actor, action="jobs.post.submitted", target=job, summary=job.title)
    return job


@transaction.atomic
def approve_job(job: JobPost, *, admin, note: str = "") -> JobPost:
    if job.status != JobStatus.PENDING_ADMIN_REVIEW:
        raise JobsError("Only jobs pending review can be approved.")
    if contact_flags(job):
        raise ContactLeak(
            "The job contains direct contact information; reject it or ask the employer to fix it."
        )
    _job_transition(job, JobStatus.PUBLISHED, actor=admin, reason=note)
    job.published_at = timezone.now()
    job.moderation_note = note
    job.save(update_fields=["status", "published_at", "moderation_note", "updated_at"])
    audit.record(actor=admin, action="jobs.post.approved", target=job, summary=job.title)
    return job


@transaction.atomic
def reject_job(job: JobPost, *, admin, reason: str) -> JobPost:
    if job.status != JobStatus.PENDING_ADMIN_REVIEW:
        raise JobsError("Only jobs pending review can be rejected.")
    _job_transition(job, JobStatus.REJECTED, actor=admin, reason=reason)
    job.moderation_note = reason
    job.save(update_fields=["status", "moderation_note", "updated_at"])
    audit.record(actor=admin, action="jobs.post.rejected", target=job, summary=reason[:255])
    return job


@transaction.atomic
def suspend_job(job: JobPost, *, admin, reason: str) -> JobPost:
    if job.status != JobStatus.PUBLISHED:
        raise JobsError("Only published jobs can be suspended.")
    _job_transition(job, JobStatus.SUSPENDED, actor=admin, reason=reason)
    job.moderation_note = reason
    job.save(update_fields=["status", "moderation_note", "updated_at"])
    audit.record(actor=admin, action="jobs.post.suspended", target=job, summary=reason[:255])
    return job


@transaction.atomic
def restore_job(job: JobPost, *, admin, note: str = "") -> JobPost:
    if job.status != JobStatus.SUSPENDED:
        raise JobsError("Only suspended jobs can be restored.")
    # A suspended job holds no active slot; the employer may have used it since,
    # so restoring re-runs the same gate as submission.
    employer = _lock_employer(job.employer)
    _require_active_job_slot(employer, job)
    _job_transition(job, JobStatus.PUBLISHED, actor=admin, reason=note)
    job.save(update_fields=["status", "updated_at"])
    audit.record(actor=admin, action="jobs.post.restored", target=job, summary=note[:255])
    return job


@transaction.atomic
def close_job(job: JobPost, *, actor, reason: str = "") -> JobPost:
    if job.status not in (JobStatus.PUBLISHED, JobStatus.PENDING_ADMIN_REVIEW, JobStatus.EXPIRED):
        raise JobsError(f"A job in status {job.status} cannot be closed.")
    _job_transition(job, JobStatus.CLOSED, actor=actor, reason=reason)
    job.closed_at = timezone.now()
    job.save(update_fields=["status", "closed_at", "updated_at"])
    audit.record(actor=actor, action="jobs.post.closed", target=job)
    return job


@transaction.atomic
def archive_job(job: JobPost, *, actor, reason: str = "") -> JobPost:
    if job.status not in (JobStatus.DRAFT, JobStatus.CLOSED, JobStatus.EXPIRED, JobStatus.REJECTED):
        raise JobsError(f"A job in status {job.status} cannot be archived.")
    _job_transition(job, JobStatus.ARCHIVED, actor=actor)
    job.save(update_fields=["status", "updated_at"])
    return job


def expire_featured_jobs() -> int:
    """Read-time normalisation of the featured window: `is_featured` is only
    authoritative together with `featured_until > now`. One indexed UPDATE."""
    return JobPost.objects.filter(is_featured=True, featured_until__lte=timezone.now()).update(
        is_featured=False, featured_until=None
    )


def expire_overdue_jobs() -> int:
    """Read-time strategy (ADR-036): called by public/employer listings; cheap indexed update.
    Also normalises expired featured windows so ordering and slot counts stay correct."""
    expire_featured_jobs()
    today = timezone.localdate()
    overdue = JobPost.objects.filter(status=JobStatus.PUBLISHED, application_deadline__lt=today)
    count = 0
    for job in overdue.iterator():
        with transaction.atomic():
            _job_transition(job, JobStatus.EXPIRED, actor=None, reason="deadline passed")
            job.save(update_fields=["status", "updated_at"])
            count += 1
    return count


@transaction.atomic
def set_featured(job: JobPost, featured: bool, *, actor, days: int = 30) -> JobPost:
    if featured:
        if job.status != JobStatus.PUBLISHED:
            raise JobsError("Only published jobs can be featured.")
        employer = _lock_employer(job.employer)
        expire_featured_jobs()
        ent = employer_entitlements(employer)
        ent.require(Keys.JOBS_FEATURED)
        current = (
            JobPost.objects.filter(
                employer=employer,
                is_featured=True,
                featured_until__gt=timezone.now(),
                status=JobStatus.PUBLISHED,
            )
            .exclude(pk=job.pk)
            .count()
        )
        ent.check_concurrent(Keys.JOBS_FEATURED_LIMIT, current=current)
        job.is_featured = True
        job.featured_until = timezone.now() + timedelta(days=days)
    else:
        job.is_featured = False
        job.featured_until = None
    job.save(update_fields=["is_featured", "featured_until", "updated_at"])
    audit.record(
        actor=actor, action="jobs.post.featured_set", target=job, data={"featured": featured}
    )
    return job


# ---- applications ----------------------------------------------------------


def build_snapshot(profile: JobSeekerProfile) -> dict:
    """Professional facts frozen at application time. Never contact data."""
    return {
        "professional_title": profile.professional_title,
        "profession": profile.profession,
        "general_specialty": profile.general_specialty.slug
        if profile.general_specialty_id
        else None,
        "detailed_specialty": profile.detailed_specialty,
        "degree": profile.degree,
        "institution_name": profile.institution_name,
        "graduation_year": profile.graduation_year,
        "years_of_experience": profile.years_of_experience,
        "professional_summary": profile.professional_summary[:2000],
        "governorate": profile.governorate.slug,
        "skills": list(profile.skills.values_list("name", flat=True)[:30]),
        "languages": [f"{lang.language} ({lang.level})" for lang in profile.languages.all()[:10]],
    }


@transaction.atomic
def apply_to_job(
    job: JobPost, profile: JobSeekerProfile, *, cover_text: str = ""
) -> JobApplication:
    if not job.is_open:
        raise NotOpen("This job is not open for applications.")
    if JobApplication.objects.filter(
        job=job, job_seeker=profile, status__in=ACTIVE_APPLICATION_STATUSES
    ).exists():
        raise AlreadyApplied("You have already applied to this job.")
    if detector.categories(cover_text):
        raise ContactLeak("Direct contact information is not allowed in recruitment content.")
    try:
        with transaction.atomic():
            application = JobApplication.objects.create(
                job=job,
                job_seeker=profile,
                cover_text=cover_text,
                snapshot=build_snapshot(profile),
            )
    except IntegrityError as exc:  # concurrent duplicate: one active application per job
        raise AlreadyApplied("You have already applied to this job.") from exc
    # The usage reference is this application attempt, not (job, seeker): a new
    # application after a withdrawal is a new attempt and consumes a new unit.
    # An HTTP retry is stopped above by the active-application check and a
    # concurrent duplicate by the unique constraint, so nothing double-charges.
    seeker_entitlements(profile).consume(
        Keys.APPLICATIONS_LIMIT, reference=f"apply:{application.pk}"
    )
    JobApplicationTransition.objects.create(
        application=application,
        from_status="",
        to_status=ApplicationStatus.SUBMITTED,
        actor=profile.account,
    )
    JobInvitation.objects.filter(
        job=job, job_seeker=profile, status=InvitationStatus.PENDING
    ).update(status=InvitationStatus.ACCEPTED, responded_at=timezone.now())
    return application


@transaction.atomic
def withdraw_application(application: JobApplication, *, actor, reason: str = "") -> JobApplication:
    if application.status not in SEEKER_WITHDRAWABLE:
        raise JobsError(f"An application in status {application.status} cannot be withdrawn.")
    JobApplicationTransition.objects.create(
        application=application,
        from_status=application.status,
        to_status=ApplicationStatus.WITHDRAWN,
        actor=actor,
        reason=reason,
    )
    application.status = ApplicationStatus.WITHDRAWN
    application.save(update_fields=["status", "updated_at"])
    return application


@transaction.atomic
def transition_application(
    application: JobApplication, to_status: str, *, actor, reason: str = ""
) -> JobApplication:
    allowed = EMPLOYER_APPLICATION_TRANSITIONS.get(application.status, ())
    if to_status not in allowed:
        raise JobsError(f"Cannot move an application from {application.status} to {to_status}.")
    JobApplicationTransition.objects.create(
        application=application,
        from_status=application.status,
        to_status=to_status,
        actor=actor,
        reason=reason,
    )
    application.status = to_status
    application.save(update_fields=["status", "updated_at"])
    return application


@transaction.atomic
def request_interview(
    application: JobApplication,
    *,
    actor,
    proposed_at,
    mode: str,
    location_text: str = "",
    note: str = "",
) -> InterviewRequest:
    if application.status not in (ApplicationStatus.SHORTLISTED, ApplicationStatus.INTERVIEW):
        raise JobsError("Interviews can be requested for shortlisted candidates.")
    if detector.categories(location_text) or detector.categories(note):
        raise ContactLeak("Direct contact information is not allowed in recruitment content.")
    interview = InterviewRequest.objects.create(
        application=application,
        proposed_at=proposed_at,
        mode=mode,
        location_text=location_text,
        employer_note=note,
        created_by=actor,
    )
    if application.status == ApplicationStatus.SHORTLISTED:
        transition_application(
            application, ApplicationStatus.INTERVIEW, actor=actor, reason="interview requested"
        )
    return interview


def respond_to_interview(
    interview: InterviewRequest, *, actor, accept: bool, response: str = ""
) -> InterviewRequest:
    if interview.status != InterviewStatus.PROPOSED:
        raise JobsError("This interview request was already answered.")
    if detector.categories(response):
        raise ContactLeak("Direct contact information is not allowed in recruitment content.")
    interview.status = InterviewStatus.ACCEPTED if accept else InterviewStatus.DECLINED
    interview.candidate_response = response
    interview.responded_at = timezone.now()
    interview.save(update_fields=["status", "candidate_response", "responded_at", "updated_at"])
    return interview


def send_message(
    application: JobApplication, *, sender, side: str, body: str
) -> RecruitmentMessage:
    if detector.categories(body):
        raise ContactLeak("Direct contact information is not allowed in recruitment content.")
    if application.status in (ApplicationStatus.WITHDRAWN, ApplicationStatus.REJECTED):
        raise JobsError("This application is closed.", code="application_closed")
    if side == MessageSide.EMPLOYER:
        employer_entitlements(application.job.employer).require(Keys.RECRUITMENT_MESSAGING)
    return RecruitmentMessage.objects.create(
        application=application, sender=sender, sender_side=side, body=body
    )


# ---- talent ----------------------------------------------------------------


def search_signature(params: dict) -> str:
    """Pagination/ordering are excluded so paging through results is one search."""
    material = {
        k: v
        for k, v in sorted(params.items())
        if k not in ("page", "page_size", "ordering") and v not in ("", None)
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:64]


@transaction.atomic
def record_talent_search(employer: Employer, params: dict, *, actor) -> bool:
    """Consumes one search only for a new (employer, signature, day). Returns True when charged."""
    ent = employer_entitlements(employer)
    ent.require(Keys.TALENT_SEARCH)
    signature = search_signature(params)
    day = timezone.localdate()
    # get_or_create is race-safe (savepoint + re-read), so two identical
    # concurrent requests charge exactly once.
    _, created = TalentSearchQuery.objects.get_or_create(
        employer=employer, signature=signature, day=day, defaults={"executed_by": actor}
    )
    if not created:
        return False
    ent.consume(Keys.TALENT_SEARCH_LIMIT, reference=f"talent:{employer.pk}:{day}:{signature}")
    return True


@transaction.atomic
def save_candidate(
    employer: Employer, profile: JobSeekerProfile, *, actor, note: str = ""
) -> SavedCandidate:
    employer_entitlements(employer).require(Keys.TALENT_SAVE)
    if (
        not profile.discoverable_by_employers
        and not JobApplication.objects.filter(job__employer=employer, job_seeker=profile).exists()
    ):
        raise JobsError("This candidate is not discoverable.", code="not_found")
    saved, created = SavedCandidate.objects.get_or_create(
        employer=employer, job_seeker=profile, defaults={"created_by": actor, "note": note}
    )
    if not created:
        raise JobsError("Candidate already saved.", code="already_saved")
    return saved


@transaction.atomic
def invite_candidate(
    employer: Employer, job: JobPost, profile: JobSeekerProfile, *, actor, message: str = ""
) -> JobInvitation:
    if job.employer_id != employer.pk:
        raise JobsError("Job does not belong to this organisation.", code="not_found")
    if not job.is_open:
        raise NotOpen("This job is not open for applications.")
    if not profile.discoverable_by_employers:
        raise JobsError("This candidate is not discoverable.", code="not_found")
    if detector.categories(message):
        raise ContactLeak("Direct contact information is not allowed in recruitment content.")
    if JobInvitation.objects.filter(
        job=job, job_seeker=profile, status=InvitationStatus.PENDING
    ).exists():
        raise AlreadyInvited("This candidate was already invited to this job.")
    if JobApplication.objects.filter(
        job=job, job_seeker=profile, status__in=ACTIVE_APPLICATION_STATUSES
    ).exists():
        raise AlreadyApplied("This candidate already applied to this job.")
    ent = employer_entitlements(employer)
    ent.require(Keys.TALENT_INVITE)
    try:
        with transaction.atomic():
            invitation = JobInvitation.objects.create(
                employer=employer,
                job=job,
                job_seeker=profile,
                created_by=actor,
                message=message,
                expires_at=timezone.now() + INVITATION_TTL,
            )
    except IntegrityError as exc:  # concurrent duplicate: one pending invitation per job
        raise AlreadyInvited("This candidate was already invited to this job.") from exc
    # Same rule as applications: the reference is this invitation, so a new
    # invitation after a declined/expired/cancelled one consumes a new unit.
    ent.consume(Keys.TALENT_INVITE_LIMIT, reference=f"invite:{invitation.pk}")
    return invitation


def respond_to_invitation(invitation: JobInvitation, *, accept: bool) -> JobInvitation:
    if invitation.status != InvitationStatus.PENDING:
        raise JobsError("This invitation was already answered.")
    if invitation.expires_at < timezone.now():
        invitation.status = InvitationStatus.EXPIRED
        invitation.save(update_fields=["status", "updated_at"])
        raise JobsError("This invitation has expired.", code="invitation_expired")
    invitation.status = InvitationStatus.ACCEPTED if accept else InvitationStatus.DECLINED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at", "updated_at"])
    return invitation


def cancel_invitation(invitation: JobInvitation, *, actor) -> JobInvitation:
    if invitation.status != InvitationStatus.PENDING:
        raise JobsError("Only pending invitations can be cancelled.")
    invitation.status = InvitationStatus.CANCELLED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=["status", "responded_at", "updated_at"])
    return invitation


__all__ = ["RecruitmentStatus"]
