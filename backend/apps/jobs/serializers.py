"""Purpose-built serializers. Public/professional views never include Account
contact data (email, phone), firebase ids, staff flags or permissions."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.geography.models import City, Governorate
from apps.geography.serializers import CitySerializer, GovernorateSerializer
from apps.moderation.contact_leak import validate_no_contact_info
from apps.providers.models import ProviderProfile
from apps.specialties.models import Specialty
from apps.specialties.serializers import SpecialtySerializer

from . import services
from .models import (
    Credential,
    Education,
    Employer,
    EmployerMembership,
    InterviewRequest,
    JobApplication,
    JobApplicationTransition,
    JobInvitation,
    JobPost,
    JobPostTransition,
    JobSeekerProfile,
    LanguageSkill,
    RecruitmentMessage,
    SavedCandidate,
    Skill,
    WorkExperience,
)
from .types import EmploymentType, InterviewMode, OrganizationType

# What an administrator verified: frozen for owners once review starts.
IDENTITY_FIELDS = (
    "name",
    "organization_type",
    "provider_profile",
    "is_recruitment_agency",
    "governorate",
)
IDENTITY_LOCKED_STATUSES = ("PENDING", "VERIFIED")

ADMIN_ONLY_EMPLOYER_FIELDS = frozenset(
    {
        "verification_status",
        "verification_note",
        "verified_at",
        "recruitment_status",
        "created_by",
        "id",
    }
)
ADMIN_ONLY_JOB_FIELDS = frozenset(
    {
        "status",
        "moderation_note",
        "moderation_flags",
        "is_featured",
        "featured_until",
        "published_at",
        "submitted_at",
        "closed_at",
        "employer",
        "created_by",
        "id",
    }
)


class ForbidFieldsMixin:
    forbidden: frozenset[str] = frozenset()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        sent = set(getattr(self, "initial_data", {}) or {})
        bad = sorted(sent & self.forbidden)
        if bad:
            raise serializers.ValidationError(
                {f: ["This field cannot be set by a client."] for f in bad},
                code="field_not_allowed",
            )
        return attrs


def _validate_city(attrs, instance):
    governorate = attrs.get("governorate", getattr(instance, "governorate", None))
    city = (
        attrs.get("city", getattr(instance, "city", None)) if "city" in attrs or instance else None
    )
    if "city" in attrs:
        city = attrs["city"]
    if city is not None and governorate is not None and city.governorate_id != governorate.pk:
        raise serializers.ValidationError(
            {"city": ["This city does not belong to the selected governorate."]}
        )


# ---- employers --------------------------------------------------------------


class EmployerPublicSerializer(serializers.ModelSerializer):
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    is_verified = serializers.SerializerMethodField()
    provider_profile_id = serializers.UUIDField(
        source="provider_profile.id", read_only=True, default=None
    )

    class Meta:
        model = Employer
        fields = (
            "id",
            "name",
            "organization_type",
            "description",
            "governorate",
            "city",
            "is_recruitment_agency",
            "is_verified",
            "provider_profile_id",
        )
        read_only_fields = fields

    def get_is_verified(self, obj) -> bool:
        return obj.verification_status == "VERIFIED"


class EmployerOwnerSerializer(EmployerPublicSerializer):
    active_jobs = serializers.SerializerMethodField()

    class Meta(EmployerPublicSerializer.Meta):
        fields = EmployerPublicSerializer.Meta.fields + (
            "active_jobs",
            "verification_status",
            "verification_note",
            "verification_requested_at",
            "verified_at",
            "recruitment_status",
            "is_discoverable",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField())
    def get_active_jobs(self, obj) -> int:
        """Authoritative server count for the `jobs.active_limit` gate (not a page count)."""
        annotated = getattr(obj, "active_jobs", None)
        if annotated is not None:
            return annotated
        return services._active_job_count(obj)


class EmployerWriteSerializer(ForbidFieldsMixin, serializers.ModelSerializer):
    forbidden = ADMIN_ONLY_EMPLOYER_FIELDS
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    provider_profile = serializers.PrimaryKeyRelatedField(
        queryset=ProviderProfile.objects.all(), allow_null=True, required=False
    )
    description = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    name = serializers.CharField(max_length=150, validators=[validate_no_contact_info])

    class Meta:
        model = Employer
        fields = (
            "name",
            "organization_type",
            "description",
            "governorate",
            "city",
            "provider_profile",
            "is_recruitment_agency",
            "is_discoverable",
        )

    def validate_provider_profile(self, profile):
        if profile is None:
            return None
        request = self.context["request"]
        if profile.account_id != request.user.pk:
            raise serializers.ValidationError("You can only link a provider profile you own.")
        if not profile.is_facility:
            raise serializers.ValidationError(
                "Only facility profiles can be linked to an employer."
            )
        if (
            Employer.objects.filter(provider_profile=profile)
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise serializers.ValidationError(
                "This provider profile is already linked to an organisation."
            )
        return profile

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _validate_city(attrs, self.instance)
        self._enforce_identity_lock(attrs)
        return attrs

    def _enforce_identity_lock(self, attrs) -> None:
        """Once an organisation is under review or verified, the fields that
        define *what* was verified are frozen for owners (backend rule; the web
        only mirrors it). Changing them needs a Racheeta administrator."""
        employer = self.instance
        if employer is None or employer.verification_status not in IDENTITY_LOCKED_STATUSES:
            return
        errors = {}
        for field in IDENTITY_FIELDS:
            if field in attrs and attrs[field] != getattr(employer, field):
                errors[field] = serializers.ErrorDetail(
                    "This field is locked after verification. Ask Racheeta administration "
                    "to change it.",
                    code="identity_locked",
                )
        if errors:
            raise serializers.ValidationError(errors)


class EmployerMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="account.full_name", read_only=True)

    class Meta:
        model = EmployerMembership
        fields = ("id", "full_name", "role", "status", "created_at")
        read_only_fields = fields


class MemberAddSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[("RECRUITER", "Recruiter"), ("VIEWER", "Viewer")])


class ProviderReferenceSerializer(serializers.ModelSerializer):
    """Read-only reference to the linked facility profile for administrator
    review: what the reviewer is about to freeze as the organisation's identity.
    No contact data, no owner identity."""

    class Meta:
        model = ProviderProfile
        fields = ("id", "display_name", "provider_type", "verification_status")
        read_only_fields = fields


class EmployerAdminSerializer(EmployerOwnerSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    provider_profile = ProviderReferenceSerializer(read_only=True)

    class Meta(EmployerOwnerSerializer.Meta):
        fields = EmployerOwnerSerializer.Meta.fields + ("created_by_email", "provider_profile")
        read_only_fields = fields


VERIFICATION_DECISION_CHOICES = [
    ("VERIFIED", "Verified"),
    ("REJECTED", "Rejected"),
    ("SUSPENDED", "Suspended"),
    ("UNVERIFIED", "Unverified"),
]


class EmployerVerificationDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=VERIFICATION_DECISION_CHOICES)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class RecruitmentReasonSerializer(serializers.Serializer):
    # Free text the other party may later read (withdrawal reasons end up in the
    # transition history shown to the employer): contact-checked.
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )


# ---- job seeker profile -----------------------------------------------------


class WorkExperienceSerializer(serializers.ModelSerializer):
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.all(), allow_null=True, required=False
    )
    title = serializers.CharField(max_length=150, validators=[validate_no_contact_info])
    organization_name = serializers.CharField(max_length=150, validators=[validate_no_contact_info])
    description = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_no_contact_info]
    )

    class Meta:
        model = WorkExperience
        fields = (
            "id",
            "title",
            "organization_name",
            "governorate",
            "start_date",
            "end_date",
            "is_current",
            "description",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if end and start and end < start:
            raise serializers.ValidationError(
                {"end_date": ["End date must be after the start date."]}
            )
        return attrs


class EducationSerializer(serializers.ModelSerializer):
    field_of_study = serializers.CharField(max_length=150, validators=[validate_no_contact_info])
    institution_name = serializers.CharField(max_length=150, validators=[validate_no_contact_info])

    class Meta:
        model = Education
        fields = ("id", "degree", "field_of_study", "institution_name", "start_year", "end_year")
        read_only_fields = ("id",)


class SkillSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=80, validators=[validate_no_contact_info])

    class Meta:
        model = Skill
        fields = ("id", "name")
        read_only_fields = ("id",)

    def validate_name(self, value: str) -> str:
        profile = getattr(self.context.get("request"), "job_seeker", None)
        normalized = " ".join(value.lower().split())
        if (
            profile is not None
            and Skill.objects.filter(profile=profile, name_normalized=normalized)
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise serializers.ValidationError("This skill is already listed.", code="duplicate")
        return value.strip()


class LanguageSkillSerializer(serializers.ModelSerializer):
    language = serializers.CharField(
        max_length=40,
        validators=[validate_no_contact_info],
        help_text="e.g. Arabic, English, Kurdish",
    )

    class Meta:
        model = LanguageSkill
        fields = ("id", "language", "level")
        read_only_fields = ("id",)

    def validate_language(self, value: str) -> str:
        profile = getattr(self.context.get("request"), "job_seeker", None)
        normalized = " ".join(value.lower().split())
        if (
            profile is not None
            and LanguageSkill.objects.filter(profile=profile, language_normalized=normalized)
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise serializers.ValidationError("This language is already listed.", code="duplicate")
        return value.strip()


class CredentialSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=150, validators=[validate_no_contact_info])
    issuer = serializers.CharField(
        max_length=150, required=False, allow_blank=True, validators=[validate_no_contact_info]
    )

    class Meta:
        model = Credential
        fields = ("id", "kind", "name", "issuer", "year")
        read_only_fields = ("id",)


class JobSeekerProfileSerializer(serializers.ModelSerializer):
    """Owner view: full structured résumé, no contact data (that lives on /me)."""

    general_specialty = SpecialtySerializer(read_only=True)
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    desired_governorate = GovernorateSerializer(read_only=True)
    experiences = WorkExperienceSerializer(many=True, read_only=True)
    education = EducationSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    languages = LanguageSkillSerializer(many=True, read_only=True)
    credentials = CredentialSerializer(many=True, read_only=True)

    class Meta:
        model = JobSeekerProfile
        fields = (
            "id",
            "professional_title",
            "profession",
            "general_specialty",
            "detailed_specialty",
            "degree",
            "institution_name",
            "graduation_year",
            "years_of_experience",
            "professional_summary",
            "governorate",
            "city",
            "desired_governorate",
            "employment_preferences",
            "availability",
            "salary_expectation_min",
            "salary_currency",
            "discoverable_by_employers",
            "experiences",
            "education",
            "skills",
            "languages",
            "credentials",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class JobSeekerProfileWriteSerializer(ForbidFieldsMixin, serializers.ModelSerializer):
    forbidden = frozenset({"account", "id"})
    general_specialty = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True), allow_null=True, required=False
    )
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    desired_governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True), allow_null=True, required=False
    )
    employment_preferences = serializers.ListField(
        child=serializers.ChoiceField(choices=EmploymentType.choices), required=False
    )
    professional_title = serializers.CharField(
        max_length=150, validators=[validate_no_contact_info]
    )
    detailed_specialty = serializers.CharField(
        max_length=150, required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    institution_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    professional_summary = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_no_contact_info]
    )

    class Meta:
        model = JobSeekerProfile
        fields = (
            "professional_title",
            "profession",
            "general_specialty",
            "detailed_specialty",
            "degree",
            "institution_name",
            "graduation_year",
            "years_of_experience",
            "professional_summary",
            "governorate",
            "city",
            "desired_governorate",
            "employment_preferences",
            "availability",
            "salary_expectation_min",
            "salary_currency",
            "discoverable_by_employers",
        )

    def validate_graduation_year(self, value):
        if value is not None and not (1950 <= value <= timezone.localdate().year + 1):
            raise serializers.ValidationError("Enter a valid graduation year.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _validate_city(attrs, self.instance)
        return attrs


class TalentCardSerializer(serializers.ModelSerializer):
    """What an entitled employer sees in talent search. No identity/contact data."""

    general_specialty = SpecialtySerializer(read_only=True)
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    skills = serializers.SerializerMethodField()
    languages = LanguageSkillSerializer(many=True, read_only=True)

    class Meta:
        model = JobSeekerProfile
        fields = (
            "id",
            "professional_title",
            "profession",
            "general_specialty",
            "detailed_specialty",
            "degree",
            "years_of_experience",
            "governorate",
            "city",
            "availability",
            "employment_preferences",
            "skills",
            "languages",
        )
        read_only_fields = fields

    def get_skills(self, obj) -> list[str]:
        return [s.name for s in obj.skills.all()]


class TalentDetailSerializer(TalentCardSerializer):
    experiences = WorkExperienceSerializer(many=True, read_only=True)
    education = EducationSerializer(many=True, read_only=True)
    credentials = CredentialSerializer(many=True, read_only=True)
    desired_governorate = GovernorateSerializer(read_only=True)
    is_saved = serializers.SerializerMethodField()
    saved_candidate_id = serializers.SerializerMethodField()

    class Meta(TalentCardSerializer.Meta):
        fields = TalentCardSerializer.Meta.fields + (
            "institution_name",
            "graduation_year",
            "professional_summary",
            "desired_governorate",
            "salary_expectation_min",
            "salary_currency",
            "experiences",
            "education",
            "credentials",
            "is_saved",
            "saved_candidate_id",
        )
        read_only_fields = fields

    def _own_saved_id(self, obj):
        """The requesting employer's own SavedCandidate id (never another
        organisation's), cached per object so both fields cost one query."""
        cache = self.context.setdefault("_saved_ids", {})
        if obj.pk not in cache:
            employer = self.context.get("employer")
            cache[obj.pk] = (
                SavedCandidate.objects.filter(employer=employer, job_seeker=obj)
                .values_list("id", flat=True)
                .first()
                if employer
                else None
            )
        return cache[obj.pk]

    def get_is_saved(self, obj) -> bool:
        return self._own_saved_id(obj) is not None

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_saved_candidate_id(self, obj):
        return self._own_saved_id(obj)


# ---- job posts --------------------------------------------------------------


class JobCardSerializer(serializers.ModelSerializer):
    employer = EmployerPublicSerializer(read_only=True)
    hiring_employer = EmployerPublicSerializer(read_only=True, allow_null=True)
    governorate = GovernorateSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    general_specialty = SpecialtySerializer(read_only=True)
    salary_min = serializers.SerializerMethodField()
    salary_max = serializers.SerializerMethodField()
    is_featured = serializers.SerializerMethodField()

    class Meta:
        model = JobPost
        fields = (
            "id",
            "title",
            "employer",
            "hiring_employer",
            "hiring_organization_name",
            "profession",
            "general_specialty",
            "detailed_specialty",
            "governorate",
            "city",
            "employment_type",
            "work_mode",
            "shift_type",
            "minimum_degree",
            "minimum_experience_years",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_visible",
            "is_featured",
            "published_at",
            "application_deadline",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_featured(self, obj) -> bool:
        return obj.is_actively_featured

    def to_representation(self, obj):
        data = super().to_representation(obj)
        # Public surfaces render the hiring organisation only while it has a
        # public presence itself (verified, discoverable): naming a hidden or
        # no-longer-verified organisation must not publish its profile.
        if self.context.get("public") and data.get("hiring_employer") is not None:
            he = obj.hiring_employer
            if not (he.is_discoverable and he.verification_status == "VERIFIED"):
                data["hiring_employer"] = None
        return data

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_salary_min(self, obj):
        return str(obj.salary_min) if obj.salary_visible and obj.salary_min is not None else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_salary_max(self, obj):
        return str(obj.salary_max) if obj.salary_visible and obj.salary_max is not None else None


class JobPublicSerializer(JobCardSerializer):
    is_open = serializers.BooleanField(read_only=True)

    class Meta(JobCardSerializer.Meta):
        fields = JobCardSerializer.Meta.fields + (
            "description",
            "responsibilities",
            "requirements",
            "workplace_text",
            "number_of_openings",
            "is_open",
        )
        read_only_fields = fields


class JobTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPostTransition
        fields = ("from_status", "to_status", "reason", "created_at")
        read_only_fields = fields


class JobEmployerSerializer(JobPublicSerializer):
    """Employer view: real salary values, status, moderation, counts."""

    salary_min = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    salary_max = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    applications_count = serializers.IntegerField(read_only=True, default=0)
    transitions = JobTransitionSerializer(many=True, read_only=True)

    class Meta(JobPublicSerializer.Meta):
        fields = JobPublicSerializer.Meta.fields + (
            "status",
            "moderation_note",
            "moderation_flags",
            "featured_until",
            "submitted_at",
            "closed_at",
            "applications_count",
            "transitions",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class JobWriteSerializer(ForbidFieldsMixin, serializers.ModelSerializer):
    forbidden = ADMIN_ONLY_JOB_FIELDS
    general_specialty = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True), allow_null=True, required=False
    )
    governorate = serializers.PrimaryKeyRelatedField(
        queryset=Governorate.objects.filter(is_active=True)
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(is_active=True), allow_null=True, required=False
    )
    hiring_employer = serializers.PrimaryKeyRelatedField(
        # Only an organisation with a public presence can be named publicly.
        queryset=Employer.objects.filter(verification_status="VERIFIED", is_discoverable=True),
        allow_null=True,
        required=False,
    )
    title = serializers.CharField(max_length=150, validators=[validate_no_contact_info])
    detailed_specialty = serializers.CharField(
        max_length=150, required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    description = serializers.CharField(validators=[validate_no_contact_info])
    responsibilities = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    requirements = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    workplace_text = serializers.CharField(
        max_length=150, required=False, allow_blank=True, validators=[validate_no_contact_info]
    )
    hiring_organization_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, validators=[validate_no_contact_info]
    )

    class Meta:
        model = JobPost
        fields = (
            "title",
            "profession",
            "general_specialty",
            "detailed_specialty",
            "description",
            "responsibilities",
            "requirements",
            "minimum_degree",
            "minimum_experience_years",
            "governorate",
            "city",
            "workplace_text",
            "employment_type",
            "work_mode",
            "shift_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_visible",
            "number_of_openings",
            "application_deadline",
            "hiring_employer",
            "hiring_organization_name",
        )

    def validate_application_deadline(self, value):
        if value is not None and value < timezone.localdate():
            raise serializers.ValidationError("The deadline must be in the future.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _validate_city(attrs, self.instance)
        smin = attrs.get("salary_min", getattr(self.instance, "salary_min", None))
        smax = attrs.get("salary_max", getattr(self.instance, "salary_max", None))
        if smin is not None and smax is not None and smin > smax:
            raise serializers.ValidationError(
                {"salary_max": ["Maximum salary must be at least the minimum."]}
            )
        employer = self.context.get("employer")
        if employer is not None and not employer.is_recruitment_agency:
            # Validate the RESULTING job, not only the fields in this request: a
            # draft created while the organisation was an agency must clear its
            # hiring fields once the organisation is no longer one.
            resulting = {
                f: attrs[f] if f in attrs else getattr(self.instance, f, None)
                for f in ("hiring_employer", "hiring_organization_name")
            }
            errors = {
                f: [
                    serializers.ErrorDetail(
                        "Only recruitment agencies can hire on behalf of another organisation; "
                        "clear this field.",
                        code="not_an_agency",
                    )
                ]
                for f, v in resulting.items()
                if v
            }
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class JobAdminSerializer(JobEmployerSerializer):
    employer = EmployerAdminSerializer(read_only=True)
    contact_findings = serializers.SerializerMethodField()

    class Meta(JobEmployerSerializer.Meta):
        fields = JobEmployerSerializer.Meta.fields + ("contact_findings",)
        read_only_fields = fields

    def get_contact_findings(self, obj) -> list[dict]:
        from .services import contact_flags

        return contact_flags(obj)


class AdminDecisionSerializer(serializers.Serializer):
    # Persisted as JobPostTransition.reason (max_length=500): validate to the
    # same bound so an over-long note is a 400, never a database error.
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class FeaturedSerializer(serializers.Serializer):
    featured = serializers.BooleanField()
    days = serializers.IntegerField(required=False, min_value=1, max_value=90, default=30)


# ---- applications -----------------------------------------------------------


class ApplicationTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobApplicationTransition
        fields = ("from_status", "to_status", "reason", "created_at")
        read_only_fields = fields


class InterviewRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewRequest
        fields = (
            "id",
            "proposed_at",
            "mode",
            "location_text",
            "employer_note",
            "status",
            "candidate_response",
            "responded_at",
            "created_at",
        )
        read_only_fields = fields


class InterviewCreateSerializer(serializers.Serializer):
    proposed_at = serializers.DateTimeField()
    mode = serializers.ChoiceField(choices=InterviewMode.choices)
    location_text = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )
    note = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )

    def validate_proposed_at(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("The interview time must be in the future.")
        return value


class InterviewResponseSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    response = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecruitmentMessage
        fields = ("id", "sender_side", "body", "created_at")
        read_only_fields = fields


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, validators=[validate_no_contact_info])


class ApplicationSeekerSerializer(serializers.ModelSerializer):
    """Job seeker's own application."""

    job = JobCardSerializer(read_only=True)
    transitions = ApplicationTransitionSerializer(many=True, read_only=True)
    interviews = InterviewRequestSerializer(many=True, read_only=True)

    class Meta:
        model = JobApplication
        fields = (
            "id",
            "job",
            "status",
            "cover_text",
            "snapshot",
            "submitted_at",
            "transitions",
            "interviews",
        )
        read_only_fields = fields


class ApplySerializer(serializers.Serializer):
    cover_text = serializers.CharField(
        max_length=2000,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )


class ApplicationEmployerSerializer(serializers.ModelSerializer):
    """Employer's view of an applicant: snapshot + current professional profile.
    Never contact data."""

    job_id = serializers.UUIDField(source="job.id", read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)
    candidate = TalentCardSerializer(source="job_seeker", read_only=True)
    transitions = ApplicationTransitionSerializer(many=True, read_only=True)
    interviews = InterviewRequestSerializer(many=True, read_only=True)

    class Meta:
        model = JobApplication
        fields = (
            "id",
            "job_id",
            "job_title",
            "status",
            "cover_text",
            "snapshot",
            "candidate",
            "submitted_at",
            "transitions",
            "interviews",
        )
        read_only_fields = fields


class ApplicationTransitionRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            ("REVIEWING", "Reviewing"),
            ("SHORTLISTED", "Shortlisted"),
            ("ACCEPTED", "Accepted"),
            ("REJECTED", "Rejected"),
        ]
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )


# ---- talent actions -----------------------------------------------------------


class SavedCandidateSerializer(serializers.ModelSerializer):
    candidate = TalentCardSerializer(source="job_seeker", read_only=True)

    class Meta:
        model = SavedCandidate
        fields = ("id", "candidate", "note", "created_at")
        read_only_fields = ("id", "candidate", "created_at")


class SaveCandidateSerializer(serializers.Serializer):
    job_seeker = serializers.UUIDField()
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class InvitationSerializer(serializers.ModelSerializer):
    job = JobCardSerializer(read_only=True)
    candidate = TalentCardSerializer(source="job_seeker", read_only=True, allow_null=True)

    class Meta:
        model = JobInvitation
        fields = (
            "id",
            "job",
            "candidate",
            "message",
            "status",
            "responded_at",
            "expires_at",
            "created_at",
        )
        read_only_fields = fields


class InvitationSeekerSerializer(serializers.ModelSerializer):
    job = JobCardSerializer(read_only=True)

    class Meta:
        model = JobInvitation
        fields = ("id", "job", "message", "status", "expires_at", "created_at")
        read_only_fields = fields


class InviteSerializer(serializers.Serializer):
    job = serializers.UUIDField()
    job_seeker = serializers.UUIDField()
    message = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        validators=[validate_no_contact_info],
    )


class InvitationResponseSerializer(serializers.Serializer):
    accept = serializers.BooleanField()


__all__ = ["OrganizationType"]
