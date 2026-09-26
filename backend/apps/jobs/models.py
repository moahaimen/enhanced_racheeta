"""Medical jobs & talent marketplace domain.

Employer (organisation) ─┬─ EmployerMembership (accounts with roles)
                         ├─ JobPost ─┬─ JobApplication ─┬─ JobApplicationTransition
                         │           │                  ├─ InterviewRequest
                         │           │                  └─ RecruitmentMessage
                         │           └─ JobInvitation
                         └─ SavedCandidate
JobSeekerProfile (one per account) ─ WorkExperience / Education / Skill / Language / Credential

Hard rules: no file fields anywhere; no Account contact data is copied into
recruitment models; billing is reached only through apps.billing services.
"""

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import BaseModel
from apps.geography.models import City, Governorate
from apps.providers.models import ProviderProfile
from apps.specialties.models import Specialty

from .types import (
    ApplicationStatus,
    Availability,
    CredentialKind,
    Degree,
    EmploymentType,
    InterviewMode,
    InterviewStatus,
    InvitationStatus,
    JobStatus,
    LanguageLevel,
    MemberRole,
    MemberStatus,
    MessageSide,
    OrganizationType,
    Profession,
    RecruitmentStatus,
    ShiftType,
    VerificationStatus,
    WorkMode,
)

# ---- employers --------------------------------------------------------------


class EmployerQuerySet(models.QuerySet):
    def public(self):
        """THE public-presence rule for an organisation, shared by the public
        employer page, the public rendering of a job's hiring organisation and
        the choice of organisations an agency may name: verified, allowed to
        recruit and discoverable. `Employer.is_public` is the row-level twin."""
        return self.filter(
            verification_status=VerificationStatus.VERIFIED,
            recruitment_status=RecruitmentStatus.ACTIVE,
            is_discoverable=True,
        )


class Employer(BaseModel):
    """A hiring organisation. When a Phase 2 facility profile exists, it is
    linked and remains authoritative for name/type/location display."""

    objects = EmployerQuerySet.as_manager()

    name = models.CharField(max_length=150, help_text="Recruitment display name")
    organization_type = models.CharField(max_length=32, choices=OrganizationType.choices)
    description = models.TextField(blank=True, default="")
    governorate = models.ForeignKey(Governorate, on_delete=models.PROTECT, related_name="employers")
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, related_name="employers", null=True, blank=True
    )
    provider_profile = models.OneToOneField(
        ProviderProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="employer"
    )
    is_recruitment_agency = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED
    )
    verification_note = models.TextField(blank=True, default="")
    verification_requested_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    recruitment_status = models.CharField(
        max_length=12, choices=RecruitmentStatus.choices, default=RecruitmentStatus.ACTIVE
    )
    is_discoverable = models.BooleanField(
        default=True, help_text="Show the organisation page publicly"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employers_created"
    )

    class Meta:
        db_table = "jobs_employer"
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=["verification_status", "recruitment_status"],
                name="jobs_employer_status_idx",
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def can_recruit(self) -> bool:
        return (
            self.verification_status == VerificationStatus.VERIFIED
            and self.recruitment_status == RecruitmentStatus.ACTIVE
        )

    @property
    def is_public(self) -> bool:
        """Row-level twin of `EmployerQuerySet.public()`."""
        return self.can_recruit and self.is_discoverable


class EmployerMembership(BaseModel):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="memberships")
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer_memberships"
    )
    role = models.CharField(max_length=10, choices=MemberRole.choices, default=MemberRole.RECRUITER)
    status = models.CharField(
        max_length=8, choices=MemberStatus.choices, default=MemberStatus.ACTIVE
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "jobs_employer_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(status="ACTIVE"),
                name="jobs_membership_one_active_per_account",
            ),
        ]
        indexes = [models.Index(fields=["employer", "status"], name="jobs_membership_employer_idx")]

    def __str__(self) -> str:
        return f"{self.account_id} @ {self.employer_id} ({self.role})"


# ---- job seekers ------------------------------------------------------------


class JobSeekerProfile(BaseModel):
    """The structured résumé. There are no file uploads by owner decision."""

    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_seeker_profile"
    )
    professional_title = models.CharField(max_length=150)
    profession = models.CharField(max_length=32, choices=Profession.choices)
    general_specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, null=True, blank=True, related_name="job_seekers"
    )
    detailed_specialty = models.CharField(max_length=150, blank=True, default="")
    degree = models.CharField(max_length=16, choices=Degree.choices)
    institution_name = models.CharField(max_length=150, blank=True, default="")
    graduation_year = models.PositiveSmallIntegerField(null=True, blank=True)
    years_of_experience = models.PositiveSmallIntegerField(default=0)
    professional_summary = models.TextField(blank=True, default="")
    governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, related_name="job_seekers"
    )
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, null=True, blank=True, related_name="job_seekers"
    )
    desired_governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    employment_preferences = ArrayField(
        models.CharField(max_length=16, choices=EmploymentType.choices), default=list, blank=True
    )
    availability = models.CharField(
        max_length=16, choices=Availability.choices, default=Availability.WITHIN_MONTH
    )
    salary_expectation_min = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    salary_currency = models.CharField(max_length=3, default="IQD")
    discoverable_by_employers = models.BooleanField(default=False)

    class Meta:
        db_table = "jobs_seeker_profile"
        indexes = [
            models.Index(
                fields=["discoverable_by_employers", "profession"], name="jobs_seeker_discover_idx"
            ),
            models.Index(fields=["governorate", "city"], name="jobs_seeker_geo_idx"),
            models.Index(
                fields=["degree", "years_of_experience"], name="jobs_seeker_degree_exp_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.professional_title


class WorkExperience(BaseModel):
    profile = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="experiences"
    )
    title = models.CharField(max_length=150)
    organization_name = models.CharField(max_length=150)
    governorate = models.ForeignKey(
        Governorate, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "jobs_seeker_experience"
        ordering = ["-start_date"]


class Education(BaseModel):
    profile = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="education"
    )
    degree = models.CharField(max_length=16, choices=Degree.choices)
    field_of_study = models.CharField(max_length=150)
    institution_name = models.CharField(max_length=150)
    start_year = models.PositiveSmallIntegerField(null=True, blank=True)
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "jobs_seeker_education"
        ordering = ["-end_year"]


class Skill(BaseModel):
    profile = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=80)
    name_normalized = models.CharField(max_length=80, db_index=True, editable=False)

    class Meta:
        db_table = "jobs_seeker_skill"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "name_normalized"], name="jobs_seeker_skill_unique"
            )
        ]

    def save(self, *args, **kwargs):
        self.name_normalized = " ".join(self.name.lower().split())
        super().save(*args, **kwargs)


class LanguageSkill(BaseModel):
    profile = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="languages"
    )
    language = models.CharField(max_length=40, help_text="e.g. Arabic, English, Kurdish")
    language_normalized = models.CharField(max_length=40, db_index=True, editable=False)
    level = models.CharField(max_length=12, choices=LanguageLevel.choices)

    class Meta:
        db_table = "jobs_seeker_language"
        ordering = ["language"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "language_normalized"], name="jobs_seeker_language_unique"
            )
        ]

    def save(self, *args, **kwargs):
        self.language_normalized = " ".join(self.language.lower().split())
        super().save(*args, **kwargs)


class Credential(BaseModel):
    """Licences and certifications as text records (no documents, no numbers)."""

    profile = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="credentials"
    )
    kind = models.CharField(max_length=14, choices=CredentialKind.choices)
    name = models.CharField(max_length=150)
    issuer = models.CharField(max_length=150, blank=True, default="")
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "jobs_seeker_credential"
        ordering = ["-year"]


# ---- job posts --------------------------------------------------------------


class JobPostQuerySet(models.QuerySet):
    def public(self):
        """What the public may see: published by a verified, active organisation
        and still open — a job whose deadline elapsed is excluded here as well
        as in search, whether or not a listing has normalised it to EXPIRED yet
        (same boundary as `is_open`: the deadline day is still open)."""
        return self.filter(
            status=JobStatus.PUBLISHED,
            employer__verification_status=VerificationStatus.VERIFIED,
            employer__recruitment_status=RecruitmentStatus.ACTIVE,
        ).filter(
            Q(application_deadline__isnull=True) | Q(application_deadline__gte=timezone.localdate())
        )

    def with_public_relations(self):
        """Everything JobCardSerializer / JobPublicSerializer read through
        EmployerPublicSerializer (for both the employer and, on agency jobs,
        the hiring employer): one query per page regardless of page size."""
        return self.select_related(
            "employer",
            "employer__governorate",
            "employer__city",
            "employer__provider_profile",
            "governorate",
            "city",
            "general_specialty",
            "hiring_employer",
            "hiring_employer__governorate",
            "hiring_employer__city",
            "hiring_employer__provider_profile",
        )


class JobPost(BaseModel):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="jobs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="jobs_created"
    )
    # agencies recruiting on behalf of another organisation
    hiring_employer = models.ForeignKey(
        Employer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs_hired_via_agency",
    )
    hiring_organization_name = models.CharField(max_length=150, blank=True, default="")
    title = models.CharField(max_length=150)
    profession = models.CharField(max_length=32, choices=Profession.choices)
    general_specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, null=True, blank=True, related_name="jobs"
    )
    detailed_specialty = models.CharField(max_length=150, blank=True, default="")
    description = models.TextField()
    responsibilities = models.TextField(blank=True, default="")
    requirements = models.TextField(blank=True, default="")
    minimum_degree = models.CharField(max_length=16, choices=Degree.choices, blank=True, default="")
    minimum_experience_years = models.PositiveSmallIntegerField(default=0)
    governorate = models.ForeignKey(Governorate, on_delete=models.PROTECT, related_name="jobs")
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, null=True, blank=True, related_name="jobs"
    )
    workplace_text = models.CharField(max_length=150, blank=True, default="")
    employment_type = models.CharField(max_length=16, choices=EmploymentType.choices)
    work_mode = models.CharField(max_length=8, choices=WorkMode.choices, default=WorkMode.ON_SITE)
    shift_type = models.CharField(max_length=10, choices=ShiftType.choices, blank=True, default="")
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default="IQD")
    salary_visible = models.BooleanField(default=False)
    number_of_openings = models.PositiveSmallIntegerField(default=1)
    application_deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=JobStatus.choices, default=JobStatus.DRAFT)
    moderation_note = models.TextField(blank=True, default="")
    moderation_flags = models.JSONField(
        default=list, blank=True, help_text="Contact-leak findings at submission"
    )
    is_featured = models.BooleanField(default=False)
    featured_until = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = JobPostQuerySet.as_manager()

    @property
    def is_actively_featured(self) -> bool:
        """The one authoritative rule: featured only while the paid window is open."""
        return bool(
            self.is_featured and self.featured_until and self.featured_until > timezone.now()
        )

    class Meta:
        db_table = "jobs_post"
        ordering = ["-is_featured", "-published_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(salary_min__isnull=True)
                | Q(salary_max__isnull=True)
                | Q(salary_min__lte=models.F("salary_max")),
                name="jobs_post_salary_range",
            ),
            models.CheckConstraint(
                condition=Q(number_of_openings__gte=1), name="jobs_post_openings_positive"
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-is_featured", "-published_at"], name="jobs_post_public_idx"
            ),
            models.Index(fields=["employer", "status"], name="jobs_post_employer_idx"),
            models.Index(fields=["profession", "governorate"], name="jobs_post_prof_geo_idx"),
            models.Index(fields=["application_deadline"], name="jobs_post_deadline_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_open(self) -> bool:
        if self.status != JobStatus.PUBLISHED or not self.employer.can_recruit:
            return False
        return (
            self.application_deadline is None or self.application_deadline >= timezone.localdate()
        )


class JobPostTransition(BaseModel):
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.CharField(max_length=24, blank=True, default="")
    to_status = models.CharField(max_length=24)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "jobs_post_transition"
        ordering = ["created_at"]


# ---- applications -----------------------------------------------------------


class JobApplication(BaseModel):
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="applications")
    job_seeker = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(
        max_length=12, choices=ApplicationStatus.choices, default=ApplicationStatus.SUBMITTED
    )
    cover_text = models.TextField(blank=True, default="")
    snapshot = models.JSONField(
        default=dict, help_text="Professional summary frozen at application time (no contact data)"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "jobs_application"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "job_seeker"],
                condition=Q(
                    status__in=["SUBMITTED", "REVIEWING", "SHORTLISTED", "INTERVIEW", "ACCEPTED"]
                ),
                name="jobs_application_one_active_per_job",
            ),
        ]
        indexes = [
            models.Index(fields=["job", "status"], name="jobs_application_job_idx"),
            models.Index(fields=["job_seeker", "status"], name="jobs_application_seeker_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.job_seeker_id} → {self.job_id} [{self.status}]"


class JobApplicationTransition(BaseModel):
    application = models.ForeignKey(
        JobApplication, on_delete=models.CASCADE, related_name="transitions"
    )
    from_status = models.CharField(max_length=12, blank=True, default="")
    to_status = models.CharField(max_length=12)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "jobs_application_transition"
        ordering = ["created_at"]


class InterviewRequest(BaseModel):
    application = models.ForeignKey(
        JobApplication, on_delete=models.CASCADE, related_name="interviews"
    )
    proposed_at = models.DateTimeField()
    mode = models.CharField(max_length=10, choices=InterviewMode.choices)
    location_text = models.CharField(max_length=255, blank=True, default="")
    employer_note = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(
        max_length=10, choices=InterviewStatus.choices, default=InterviewStatus.PROPOSED
    )
    candidate_response = models.CharField(max_length=500, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "jobs_interview_request"
        ordering = ["-created_at"]


class RecruitmentMessage(BaseModel):
    """Immutable, text-only, scoped to an application. No edit endpoint exists."""

    application = models.ForeignKey(
        JobApplication, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    sender_side = models.CharField(max_length=10, choices=MessageSide.choices)
    body = models.TextField()

    class Meta:
        db_table = "jobs_recruitment_message"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["application", "created_at"], name="jobs_message_app_idx")]


# ---- talent -----------------------------------------------------------------


class SavedCandidate(BaseModel):
    employer = models.ForeignKey(
        Employer, on_delete=models.CASCADE, related_name="saved_candidates"
    )
    job_seeker = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="saved_by"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    note = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Private to the employer; never shown to the candidate",
    )

    class Meta:
        db_table = "jobs_saved_candidate"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employer", "job_seeker"], name="jobs_saved_candidate_unique"
            )
        ]


class JobInvitation(BaseModel):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="invitations")
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="invitations")
    job_seeker = models.ForeignKey(
        JobSeekerProfile, on_delete=models.CASCADE, related_name="invitations"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    message = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(
        max_length=10, choices=InvitationStatus.choices, default=InvitationStatus.PENDING
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "jobs_invitation"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "job_seeker"],
                condition=Q(status="PENDING"),
                name="jobs_invitation_one_pending_per_job",
            )
        ]
        indexes = [models.Index(fields=["job_seeker", "status"], name="jobs_invitation_seeker_idx")]


class TalentSearchQuery(BaseModel):
    """One billable search = one distinct filter signature per employer per day."""

    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="talent_searches")
    signature = models.CharField(max_length=64)
    day = models.DateField()
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "jobs_talent_search_query"
        constraints = [
            models.UniqueConstraint(
                fields=["employer", "signature", "day"], name="jobs_talent_search_unique_per_day"
            )
        ]
