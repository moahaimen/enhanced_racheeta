from django.db import IntegrityError, transaction
from django.db.models import Count, Q, UniqueConstraint
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, generics, status
from rest_framework.exceptions import (
    APIException,
    ErrorDetail,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Account
from apps.accounts.permissions import IsAdminAccount
from apps.billing.serializers import (
    BillingSummarySerializer,
    SubscriptionRequestSerializer,
    SubscriptionSerializer,
)
from apps.billing.services import SubscriptionError, request_subscription
from apps.billing.types import Keys
from apps.billing.views import billing_summary

from . import services
from .filters import JobFilter, TalentFilter
from .models import (
    Credential,
    Education,
    Employer,
    EmployerMembership,
    InterviewRequest,
    JobApplication,
    JobInvitation,
    JobPost,
    JobSeekerProfile,
    LanguageSkill,
    RecruitmentMessage,
    SavedCandidate,
    Skill,
    WorkExperience,
)
from .permissions import CanRecruit, HasJobSeekerProfile, IsEmployerMember, IsEmployerOwner
from .serializers import (
    AdminDecisionSerializer,
    ApplicationEmployerSerializer,
    ApplicationSeekerSerializer,
    ApplicationTransitionRequestSerializer,
    ApplySerializer,
    CredentialSerializer,
    EducationSerializer,
    EmployerAdminSerializer,
    EmployerMemberSerializer,
    EmployerOwnerSerializer,
    EmployerPublicSerializer,
    EmployerVerificationDecisionSerializer,
    EmployerWriteSerializer,
    FeaturedSerializer,
    InterviewCreateSerializer,
    InterviewRequestSerializer,
    InterviewResponseSerializer,
    InvitationResponseSerializer,
    InvitationSeekerSerializer,
    InvitationSerializer,
    InviteSerializer,
    JobAdminSerializer,
    JobCardSerializer,
    JobEmployerSerializer,
    JobPublicSerializer,
    JobSeekerProfileSerializer,
    JobSeekerProfileWriteSerializer,
    JobWriteSerializer,
    LanguageSkillSerializer,
    MemberAddSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    RecruitmentReasonSerializer,
    SaveCandidateSerializer,
    SavedCandidateSerializer,
    SkillSerializer,
    TalentCardSerializer,
    TalentDetailSerializer,
    WorkExperienceSerializer,
)
from .types import ApplicationStatus, MemberStatus, MessageSide

# ---- error mapping ---------------------------------------------------------


class JobsAPIError(APIException):
    status_code = status.HTTP_409_CONFLICT


MESSAGE_THREAD_LIMIT = 200

STATUS_FOR_CODE = {
    "job_not_open": status.HTTP_409_CONFLICT,
    "already_applied": status.HTTP_409_CONFLICT,
    "already_invited": status.HTTP_409_CONFLICT,
    "already_saved": status.HTTP_409_CONFLICT,
    "already_member": status.HTTP_409_CONFLICT,
    "organization_not_verified": status.HTTP_403_FORBIDDEN,
    "contact_information_not_allowed": status.HTTP_400_BAD_REQUEST,
    "invalid_transition": status.HTTP_400_BAD_REQUEST,
    "invalid_role": status.HTTP_400_BAD_REQUEST,
    "invitation_expired": status.HTTP_409_CONFLICT,
    "invitation_unavailable": status.HTTP_409_CONFLICT,
    "deadline_passed": status.HTTP_409_CONFLICT,
    "not_an_agency": status.HTTP_400_BAD_REQUEST,
    "application_closed": status.HTTP_409_CONFLICT,
    "not_found": status.HTTP_404_NOT_FOUND,
}


def raise_api(exc: services.JobsError):
    err = JobsAPIError(str(exc) or exc.code, code=exc.code)
    err.status_code = STATUS_FOR_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST)
    raise err from exc


class _Throttled:
    throttle_classes = [ScopedRateThrottle]


# Scoped throttling for unsafe methods only.
#
# A quota named after an action (creating a job, sending an invitation) must be
# spent by that action alone. Declaring the scope at class level on a view that
# also serves GET makes listing and pagination burn the write quota, so an
# employer who refreshes the workspace is eventually 429'd on both reading and
# creating. Safe methods fall back to the project defaults: `throttle_classes`
# is deliberately NOT set here, so the lookup falls through to APIView (i.e.
# DEFAULT_THROTTLE_CLASSES) and no global throttle is removed.
#
# No docstring: drf-spectacular would publish it as the endpoint description.
class _ThrottledOnWrite:
    def get_throttles(self):
        if self.request.method in SAFE_METHODS:
            return super().get_throttles()
        return [ScopedRateThrottle()]


# ---- public jobs -----------------------------------------------------------


@extend_schema(
    tags=["jobs"],
    summary="Public job search (published jobs of verified employers)",
    parameters=[
        OpenApiParameter("q", str),
        OpenApiParameter("profession", str),
        OpenApiParameter("specialty", str),
        OpenApiParameter("governorate", str),
        OpenApiParameter("city", str),
        OpenApiParameter("employment_type", str),
        OpenApiParameter("work_mode", str),
        OpenApiParameter("shift_type", str),
        OpenApiParameter("degree", str),
        OpenApiParameter("min_experience", int),
        OpenApiParameter("max_experience", int),
        OpenApiParameter("salary_available", bool),
        OpenApiParameter(
            "ordering", str, description="-published_at (default: featured first, then newest)"
        ),
    ],
)
class JobListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = JobCardSerializer

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = JobFilter
    ordering_fields = ["published_at", "application_deadline"]
    ordering = ["-is_featured", "-published_at"]
    queryset = JobPost.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobPost.objects.none()
        services.expire_overdue_jobs()
        return JobPost.objects.public().with_public_relations()


@extend_schema(tags=["jobs"], summary="Public job details")
class JobDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = JobPublicSerializer

    def get_queryset(self):
        return JobPost.objects.public().with_public_relations()


@extend_schema(tags=["jobs"], summary="Public employer page")
class EmployerPublicView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = EmployerPublicSerializer
    queryset = Employer.objects.public().select_related("governorate", "city", "provider_profile")


# ---- job seeker: profile -------------------------------------------------


def _own_seeker(request) -> JobSeekerProfile:
    try:
        return (
            JobSeekerProfile.objects.select_related(
                "general_specialty", "governorate", "city", "desired_governorate"
            )
            .prefetch_related("experiences", "education", "skills", "languages", "credentials")
            .get(account=request.user)
        )
    except JobSeekerProfile.DoesNotExist as exc:
        raise NotFound("You have not created a professional profile yet.") from exc


@extend_schema(tags=["job-seeker"])
class MySeekerProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = JobSeekerProfileSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(
        responses={200: JobSeekerProfileSerializer},
        summary="My professional profile (structured résumé)",
    )
    def get(self, request):
        return Response(JobSeekerProfileSerializer(_own_seeker(request)).data)

    @extend_schema(
        request=JobSeekerProfileWriteSerializer,
        responses={201: JobSeekerProfileSerializer},
        summary="Create my professional profile",
    )
    def post(self, request):
        serializer = JobSeekerProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        duplicate = ValidationError(
            {"non_field_errors": ["You already have a professional profile."]},
            code="already_exists",
        )
        with transaction.atomic():
            # One profile per account: serialise on the account row (the policy
            # every account-scoped uniqueness check uses), re-check, and map the
            # constraint itself to the same typed error for the residual race.
            services._lock_account(request.user)
            if JobSeekerProfile.objects.filter(account=request.user).exists():
                raise duplicate
            try:
                with transaction.atomic():
                    serializer.save(account=request.user)
            except IntegrityError as exc:
                if "jobs_seeker_profile_account_id" not in str(exc):
                    raise
                raise duplicate from exc
        return Response(
            JobSeekerProfileSerializer(_own_seeker(request)).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=JobSeekerProfileWriteSerializer,
        responses={200: JobSeekerProfileSerializer},
        summary="Update my professional profile",
    )
    def patch(self, request):
        profile = _own_seeker(request)
        serializer = JobSeekerProfileWriteSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            # Only the submitted fields, on the locked row: never a stale instance.
            services.update_seeker_profile(profile, dict(serializer.validated_data))
        except services.FieldsInvalid as exc:
            raise ValidationError(exc.errors) from exc
        return Response(JobSeekerProfileSerializer(_own_seeker(request)).data)


def _duplicate_or_raise(exc: IntegrityError, model) -> None:
    """Only the model's own uniqueness constraints are an expected business
    conflict (typed `duplicate`); any other IntegrityError propagates."""
    names = {c.name for c in model._meta.constraints if isinstance(c, UniqueConstraint)}
    if not any(name in str(exc) for name in names):
        raise exc
    raise ValidationError(
        {"non_field_errors": ["This entry is already listed."]}, code="duplicate"
    ) from exc


def _child_views(model, ser, related: str, tag_summary: str):
    @extend_schema(tags=["job-seeker"], summary=f"My {tag_summary}")
    class ListCreate(generics.ListCreateAPIView):
        permission_classes = [HasJobSeekerProfile]
        serializer_class = ser
        pagination_class = None

        queryset = model.objects.none()

        def get_queryset(self):
            if getattr(self, "swagger_fake_view", False):
                return model.objects.none()
            return model.objects.filter(profile=self.request.job_seeker)

        def perform_create(self, serializer):
            try:
                with transaction.atomic():
                    serializer.save(profile=self.request.job_seeker)
            except IntegrityError as exc:  # concurrent duplicate: typed, never a 500
                _duplicate_or_raise(exc, model)

    @extend_schema(tags=["job-seeker"], summary=f"One of my {tag_summary}")
    class Detail(generics.RetrieveUpdateDestroyAPIView):
        permission_classes = [HasJobSeekerProfile]
        serializer_class = ser
        http_method_names = ["get", "patch", "delete", "head", "options"]
        queryset = model.objects.none()

        def get_queryset(self):
            if getattr(self, "swagger_fake_view", False):
                return model.objects.none()
            return model.objects.filter(profile=self.request.job_seeker)

        def perform_update(self, serializer):
            # Two renames to the same value pass the serializer check together;
            # the constraint decides, and the loser gets the typed duplicate.
            # The row is locked and refreshed first so the save writes the
            # submitted fields over the COMMITTED row, never over a stale copy.
            try:
                with transaction.atomic():
                    locked = model.objects.select_for_update().get(pk=serializer.instance.pk)
                    serializer.instance.__dict__.update(
                        {k: v for k, v in locked.__dict__.items() if k != "_state"}
                    )
                    serializer.save()
            except IntegrityError as exc:
                _duplicate_or_raise(exc, model)

    ListCreate.__name__ = f"My{model.__name__}ListView"
    Detail.__name__ = f"My{model.__name__}DetailView"
    return ListCreate, Detail


MyExperienceListView, MyExperienceDetailView = _child_views(
    WorkExperience, WorkExperienceSerializer, "experiences", "work experience"
)
MyEducationListView, MyEducationDetailView = _child_views(
    Education, EducationSerializer, "education", "education records"
)
MySkillListView, MySkillDetailView = _child_views(Skill, SkillSerializer, "skills", "skills")
MyLanguageListView, MyLanguageDetailView = _child_views(
    LanguageSkill, LanguageSkillSerializer, "languages", "languages"
)
MyCredentialListView, MyCredentialDetailView = _child_views(
    Credential, CredentialSerializer, "credentials", "licences and certifications"
)


# ---- job seeker: applications --------------------------------------------


@extend_schema(tags=["job-seeker"])
class ApplyView(_Throttled, APIView):
    permission_classes = [HasJobSeekerProfile]
    throttle_scope = "jobs_apply"
    serializer_class = ApplySerializer

    @extend_schema(
        request=ApplySerializer,
        responses={201: ApplicationSeekerSerializer},
        summary="Apply to an open job",
    )
    def post(self, request, pk):
        job = get_object_or_404(JobPost.objects.public().select_related("employer"), pk=pk)
        serializer = ApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            application = services.apply_to_job(
                job, request.job_seeker, cover_text=serializer.validated_data.get("cover_text", "")
            )
        except services.JobsError as exc:
            raise_api(exc)
        application = (
            JobApplication.objects.select_related(
                "job", "job__employer", "job__governorate", "job__city", "job__general_specialty"
            )
            .prefetch_related("transitions", "interviews")
            .get(pk=application.pk)
        )
        return Response(
            ApplicationSeekerSerializer(application).data, status=status.HTTP_201_CREATED
        )


def _seeker_applications(request):
    return (
        JobApplication.objects.filter(job_seeker=request.job_seeker)
        .select_related(
            "job",
            "job__employer",
            "job__employer__governorate",
            "job__employer__city",
            "job__governorate",
            "job__city",
            "job__general_specialty",
            "job__hiring_employer",
        )
        .prefetch_related("transitions", "interviews")
    )


@extend_schema(tags=["job-seeker"], summary="My applications")
class MyApplicationListView(generics.ListAPIView):
    permission_classes = [HasJobSeekerProfile]
    serializer_class = ApplicationSeekerSerializer
    queryset = JobApplication.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobApplication.objects.none()
        return _seeker_applications(self.request)


@extend_schema(tags=["job-seeker"], summary="One of my applications")
class MyApplicationDetailView(generics.RetrieveAPIView):
    permission_classes = [HasJobSeekerProfile]
    serializer_class = ApplicationSeekerSerializer
    queryset = JobApplication.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobApplication.objects.none()
        return _seeker_applications(self.request)


@extend_schema(tags=["job-seeker"], summary="Withdraw my application")
class MyApplicationWithdrawView(APIView):
    permission_classes = [HasJobSeekerProfile]
    serializer_class = RecruitmentReasonSerializer

    @extend_schema(
        request=RecruitmentReasonSerializer, responses={200: ApplicationSeekerSerializer}
    )
    def post(self, request, pk):
        application = get_object_or_404(
            JobApplication.objects.filter(job_seeker=request.job_seeker), pk=pk
        )
        serializer = RecruitmentReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.withdraw_application(
                application, actor=request.user, reason=serializer.validated_data.get("reason", "")
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(ApplicationSeekerSerializer(_seeker_applications(request).get(pk=pk)).data)


@extend_schema(tags=["job-seeker"], summary="Respond to an interview request")
class MyInterviewResponseView(APIView):
    permission_classes = [HasJobSeekerProfile]
    serializer_class = InterviewResponseSerializer

    @extend_schema(request=InterviewResponseSerializer, responses={200: InterviewRequestSerializer})
    def post(self, request, pk):
        interview = get_object_or_404(
            InterviewRequest.objects.filter(application__job_seeker=request.job_seeker), pk=pk
        )
        serializer = InterviewResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.respond_to_interview(
                interview,
                actor=request.user,
                accept=serializer.validated_data["accept"],
                response=serializer.validated_data.get("response", ""),
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(InterviewRequestSerializer(interview).data)


@extend_schema(tags=["job-seeker"], summary="Invitations I received")
class MyInvitationListView(generics.ListAPIView):
    permission_classes = [HasJobSeekerProfile]
    serializer_class = InvitationSeekerSerializer
    queryset = JobInvitation.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobInvitation.objects.none()
        services.expire_overdue_invitations(job_seeker=self.request.job_seeker)
        return JobInvitation.objects.filter(job_seeker=self.request.job_seeker).select_related(
            "job",
            "job__employer",
            "job__employer__governorate",
            "job__employer__city",
            "job__governorate",
            "job__city",
            "job__general_specialty",
            "job__hiring_employer",
        )


@extend_schema(
    tags=["job-seeker"],
    summary="Accept or decline an invitation (accepting does not apply automatically)",
)
class MyInvitationResponseView(APIView):
    permission_classes = [HasJobSeekerProfile]
    serializer_class = InvitationResponseSerializer

    @extend_schema(
        request=InvitationResponseSerializer, responses={200: InvitationSeekerSerializer}
    )
    def post(self, request, pk):
        invitation = get_object_or_404(
            JobInvitation.objects.filter(job_seeker=request.job_seeker).select_related(
                "job", "job__employer"
            ),
            pk=pk,
        )
        serializer = InvitationResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.respond_to_invitation(invitation, accept=serializer.validated_data["accept"])
        except services.JobsError as exc:
            raise_api(exc)
        return Response(InvitationSeekerSerializer(invitation).data)


# ---- messages (both sides) ---------------------------------------------------


def _application_for_party(request) -> tuple[JobApplication, str]:
    """Resolve an application the caller is a party to; return (application, side)."""
    pk = request.parser_context["kwargs"]["pk"]
    application = get_object_or_404(
        JobApplication.objects.select_related("job", "job__employer", "job_seeker"), pk=pk
    )
    if application.job_seeker.account_id == request.user.pk:
        return application, MessageSide.CANDIDATE
    membership = services.membership_for(request.user)
    if (
        membership is not None
        and membership.employer_id == application.job.employer_id
        and membership.role in ("OWNER", "RECRUITER")
    ):
        # Employer-side messaging is part of applicant review: same gate.
        _require_recruiting(membership.employer)
        services.employer_entitlements(membership.employer).require(Keys.JOBS_APPLICATION_REVIEW)
        return application, MessageSide.EMPLOYER
    raise NotFound


@extend_schema(tags=["recruitment"])
class ApplicationMessagesView(_Throttled, APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "recruitment_messages"
    serializer_class = MessageCreateSerializer

    @extend_schema(
        responses={200: MessageSerializer(many=True)},
        summary="Messages of an application (parties only)",
    )
    def get(self, request, pk):
        application, _ = _application_for_party(request)
        # Bounded thread: the NEWEST messages, returned in chronological order.
        newest_first = RecruitmentMessage.objects.filter(application=application).order_by(
            "-created_at", "-id"
        )[:MESSAGE_THREAD_LIMIT]
        messages = list(reversed(list(newest_first)))
        return Response(MessageSerializer(messages, many=True).data)

    @extend_schema(
        request=MessageCreateSerializer,
        responses={201: MessageSerializer},
        summary="Send a text-only recruitment message",
    )
    def post(self, request, pk):
        application, side = _application_for_party(request)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = services.send_message(
                application, sender=request.user, side=side, body=serializer.validated_data["body"]
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


# ---- employer: organisation ------------------------------------------------


@extend_schema(tags=["employer"])
class MyEmployerView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmployerOwnerSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(responses={200: EmployerOwnerSerializer}, summary="My organisation")
    def get(self, request):
        membership = services.membership_for(request.user)
        if membership is None:
            raise NotFound("You do not belong to an organisation yet.")
        data = EmployerOwnerSerializer(membership.employer).data
        data["my_role"] = membership.role
        return Response(data)

    @extend_schema(
        request=EmployerWriteSerializer,
        responses={201: EmployerOwnerSerializer},
        summary="Create my organisation (becoming its owner)",
    )
    def post(self, request):
        serializer = EmployerWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            employer = services.create_employer(request.user, **serializer.validated_data)
        except services.JobsError as exc:
            raise_api(exc)
        data = EmployerOwnerSerializer(
            Employer.objects.select_related("governorate", "city", "provider_profile").get(
                pk=employer.pk
            )
        ).data
        data["my_role"] = "OWNER"
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=EmployerWriteSerializer,
        responses={200: EmployerOwnerSerializer},
        summary="Update my organisation (owner)",
    )
    def patch(self, request):
        membership = services.membership_for(request.user)
        if membership is None:
            raise NotFound("You do not belong to an organisation yet.")
        if membership.role != "OWNER":
            raise PermissionDenied("Only the organisation owner can edit it.")
        serializer = EmployerWriteSerializer(
            membership.employer, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            services.update_employer(
                membership.employer, dict(serializer.validated_data), actor=request.user
            )
        except services.FieldsInvalid as exc:
            raise ValidationError(exc.errors) from exc  # same shape as the serializer's check
        except services.IdentityLocked as exc:
            raise ValidationError(
                {
                    field: ErrorDetail(
                        "This field is locked after verification. Ask Racheeta "
                        "administration to change it.",
                        code="identity_locked",
                    )
                    for field in exc.fields
                }
            ) from exc
        data = EmployerOwnerSerializer(
            Employer.objects.select_related("governorate", "city", "provider_profile").get(
                pk=membership.employer_id
            )
        ).data
        data["my_role"] = membership.role
        return Response(data)


@extend_schema(tags=["employer"], summary="Request verification of my organisation (owner)")
class MyEmployerVerificationRequestView(APIView):
    permission_classes = [IsEmployerOwner]
    serializer_class = None

    @extend_schema(request=None, responses={200: EmployerOwnerSerializer})
    def post(self, request):
        try:
            services.request_employer_verification(request.employer, actor=request.user)
        except services.JobsError as exc:
            raise_api(exc)
        return Response(
            EmployerOwnerSerializer(
                Employer.objects.select_related("governorate", "city", "provider_profile").get(
                    pk=request.employer.pk
                )
            ).data
        )


@extend_schema(tags=["employer"])
class MyEmployerMembersView(APIView):
    permission_classes = [IsEmployerMember]
    serializer_class = MemberAddSerializer

    @extend_schema(
        responses={200: EmployerMemberSerializer(many=True)}, summary="Members of my organisation"
    )
    def get(self, request):
        members = EmployerMembership.objects.filter(
            employer=request.employer, status=MemberStatus.ACTIVE
        ).select_related("account")
        return Response(EmployerMemberSerializer(members, many=True).data)

    @extend_schema(
        request=MemberAddSerializer,
        responses={201: EmployerMemberSerializer},
        summary="Add a recruiter/viewer by email (owner; seat-limited)",
    )
    def post(self, request):
        if request.employer_membership.role != "OWNER":
            raise PermissionDenied("Only the organisation owner can add members.")
        serializer = MemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = Account.objects.filter(
            email=Account.objects.normalize_email(serializer.validated_data["email"]),
            is_active=True,
        ).first()
        if account is None:
            raise ValidationError(
                {"email": ["No active account with this email."]}, code="not_found"
            )
        try:
            membership = services.add_member(
                request.employer, account, serializer.validated_data["role"], actor=request.user
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(EmployerMemberSerializer(membership).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["employer"], summary="End a membership (owner)")
class MyEmployerMemberEndView(APIView):
    permission_classes = [IsEmployerOwner]
    serializer_class = None

    @extend_schema(request=None, responses={200: EmployerMemberSerializer})
    def post(self, request, pk):
        membership = get_object_or_404(
            EmployerMembership.objects.filter(
                employer=request.employer, status=MemberStatus.ACTIVE
            ).select_related("account"),
            pk=pk,
        )
        try:
            services.end_membership(membership, actor=request.user)
        except services.JobsError as exc:
            raise_api(exc)
        return Response(EmployerMemberSerializer(membership).data)


# ---- employer: billing -------------------------------------------------------


@extend_schema(tags=["employer"], summary="My organisation's plan, subscription and usage")
class MyEmployerBillingView(APIView):
    permission_classes = [IsEmployerMember]
    serializer_class = BillingSummarySerializer

    @extend_schema(responses={200: BillingSummarySerializer})
    def get(self, request):
        ent = services.employer_entitlements(request.employer)
        return Response(BillingSummarySerializer(billing_summary(ent)).data)


@extend_schema(
    tags=["employer"], summary="Request a plan (owner). Activation is a manual administrator step."
)
class MyEmployerSubscriptionRequestView(APIView):
    permission_classes = [IsEmployerOwner]
    serializer_class = SubscriptionRequestSerializer

    @extend_schema(request=SubscriptionRequestSerializer, responses={201: SubscriptionSerializer})
    def post(self, request):
        serializer = SubscriptionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ent = services.employer_entitlements(request.employer)
        try:
            sub = request_subscription(
                ent.billing_account,
                serializer.validated_data["plan"],
                requested_by=request.user,
                note=serializer.validated_data.get("note", ""),
            )
        except SubscriptionError as exc:
            raise ValidationError({"plan": [str(exc)]}, code="invalid_request") from exc
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)


# ---- employer: jobs ----------------------------------------------------------


def _employer_jobs(request):
    return (
        JobPost.objects.filter(employer=request.employer)
        .with_public_relations()
        .annotate(
            applications_count=Count(
                "applications",
                filter=Q(applications__status__in=list(ApplicationStatus.values))
                & ~Q(applications__status="WITHDRAWN"),
            )
        )
        .prefetch_related("transitions")
    )


@extend_schema(tags=["employer"])
class EmployerJobListView(_ThrottledOnWrite, generics.ListCreateAPIView):
    permission_classes = [IsEmployerMember]
    serializer_class = JobEmployerSerializer
    # POST only: listing and paginating the workspace must not spend the
    # job-creation quota (see _ThrottledOnWrite).
    throttle_scope = "jobs_create"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {"status": ["exact"]}

    queryset = JobPost.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobPost.objects.none()
        services.expire_overdue_jobs()
        return _employer_jobs(self.request)

    @extend_schema(summary="My organisation's jobs (all statuses)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=JobWriteSerializer,
        responses={201: JobEmployerSerializer},
        summary="Create a job draft (owner/recruiter)",
    )
    def post(self, request, *args, **kwargs):
        if request.employer_membership.role not in ("OWNER", "RECRUITER"):
            raise PermissionDenied("Viewers cannot create jobs.")
        serializer = JobWriteSerializer(data=request.data, context={"employer": request.employer})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            job = serializer.save(employer=request.employer, created_by=request.user)
        return Response(
            JobEmployerSerializer(_employer_jobs(request).get(pk=job.pk)).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["employer"])
class EmployerJobDetailView(APIView):
    permission_classes = [IsEmployerMember]
    serializer_class = JobEmployerSerializer
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: JobEmployerSerializer}, summary="One of my organisation's jobs")
    def get(self, request, pk):
        return Response(
            JobEmployerSerializer(get_object_or_404(_employer_jobs(request), pk=pk)).data
        )

    @extend_schema(
        request=JobWriteSerializer,
        responses={200: JobEmployerSerializer},
        summary="Edit a job (DRAFT/REJECTED, or PUBLISHED for owner/recruiter)",
    )
    def patch(self, request, pk):
        if request.employer_membership.role not in ("OWNER", "RECRUITER"):
            raise PermissionDenied("Viewers cannot edit jobs.")
        job = get_object_or_404(JobPost.objects.filter(employer=request.employer), pk=pk)
        if job.status not in services.EDITABLE_JOB_STATUSES:  # early exit; the lock decides
            raise JobsAPIError(
                "Only draft or rejected jobs can be edited. Close and recreate a published job.",
                code="job_locked",
            )
        serializer = JobWriteSerializer(
            job, data=request.data, partial=True, context={"employer": request.employer}
        )
        serializer.is_valid(raise_exception=True)
        try:
            services.edit_job(job, dict(serializer.validated_data), actor=request.user)
        except services.FieldsInvalid as exc:
            raise ValidationError(exc.errors) from exc  # same shape as the serializer's check
        except services.JobsError as exc:
            raise_api(exc)  # the documented status per code (e.g. not_an_agency → 400)
        return Response(JobEmployerSerializer(_employer_jobs(request).get(pk=pk)).data)


def _job_action(
    fn_name: str,
    summary: str,
    roles=("OWNER", "RECRUITER"),
    serializer=RecruitmentReasonSerializer,
    kw="reason",
):
    @extend_schema(tags=["employer"], summary=summary)
    class View(APIView):
        permission_classes = [IsEmployerMember]
        serializer_class = serializer

        @extend_schema(request=serializer, responses={200: JobEmployerSerializer})
        def post(self, request, pk):
            if request.employer_membership.role not in roles:
                raise PermissionDenied("Your role does not allow this action.")
            job = get_object_or_404(
                JobPost.objects.filter(employer=request.employer).select_related("employer"), pk=pk
            )
            ser = serializer(data=request.data)
            ser.is_valid(raise_exception=True)
            fn = getattr(services, fn_name)
            try:
                if fn_name == "set_featured":
                    fn(
                        job,
                        ser.validated_data["featured"],
                        actor=request.user,
                        days=ser.validated_data.get("days", 30),
                    )
                elif fn_name == "submit_job_for_review":
                    fn(job, actor=request.user)
                else:
                    fn(job, actor=request.user, **{kw: ser.validated_data.get(kw, "")})
            except services.JobsError as exc:
                raise_api(exc)
            return Response(JobEmployerSerializer(_employer_jobs(request).get(pk=pk)).data)

    View.__name__ = f"EmployerJob{fn_name.title().replace('_', '')}View"
    return View


class _NoBody(RecruitmentReasonSerializer):
    pass


EmployerJobSubmitView = _job_action(
    "submit_job_for_review",
    "Submit a draft for administrator review (commercial + contact-leak gates)",
    serializer=_NoBody,
)
EmployerJobCloseView = _job_action("close_job", "Close a job")
EmployerJobArchiveView = _job_action(
    "archive_job", "Archive a draft/closed/expired/rejected job", serializer=_NoBody
)
EmployerJobFeatureView = _job_action(
    "set_featured",
    "Feature / unfeature a published job (entitlement-gated)",
    serializer=FeaturedSerializer,
)


# ---- employer: applicants ----------------------------------------------------


def _require_recruiting(employer) -> None:
    """A suspended organisation (verification or recruitment) keeps its data but
    cannot run recruitment workflows. Typed 403, never a silent pass."""
    if not employer.can_recruit:
        raise_api(services.OrganizationNotVerified("The organisation must be verified and active."))


def _require_application_review(request) -> None:
    """One gate for every employer-side endpoint that exposes or changes
    applicant data (list, detail, transitions, interviews, employer messages):
    the organisation must still be allowed to recruit AND the plan must carry
    jobs.application_review. Ownership scoping is separate and always applied."""
    _require_recruiting(request.employer)
    services.employer_entitlements(request.employer).require(Keys.JOBS_APPLICATION_REVIEW)


def _employer_applications(request):
    _require_application_review(request)
    return (
        JobApplication.objects.filter(job__employer=request.employer)
        .select_related(
            "job",
            "job_seeker",
            "job_seeker__general_specialty",
            "job_seeker__governorate",
            "job_seeker__city",
        )
        .prefetch_related(
            "transitions", "interviews", "job_seeker__skills", "job_seeker__languages"
        )
    )


@extend_schema(
    tags=["employer"],
    summary="Applicants of one of my jobs",
    parameters=[OpenApiParameter("status", str)],
)
class EmployerJobApplicationsView(generics.ListAPIView):
    permission_classes = [IsEmployerMember]
    serializer_class = ApplicationEmployerSerializer
    queryset = JobApplication.objects.none()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        "status": ["exact"],
        "job_seeker__profession": ["exact"],
        "job_seeker__degree": ["exact"],
        "job_seeker__governorate": ["exact"],
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobApplication.objects.none()
        job = get_object_or_404(
            JobPost.objects.filter(employer=self.request.employer), pk=self.kwargs["pk"]
        )
        return _employer_applications(self.request).filter(job=job)


@extend_schema(tags=["employer"], summary="One applicant (my organisation's jobs only)")
class EmployerApplicationDetailView(generics.RetrieveAPIView):
    permission_classes = [IsEmployerMember]
    serializer_class = ApplicationEmployerSerializer
    queryset = JobApplication.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobApplication.objects.none()
        return _employer_applications(self.request)


@extend_schema(
    tags=["employer"], summary="Move an applicant to REVIEWING / SHORTLISTED / ACCEPTED / REJECTED"
)
class EmployerApplicationTransitionView(APIView):
    permission_classes = [CanRecruit]
    serializer_class = ApplicationTransitionRequestSerializer

    @extend_schema(
        request=ApplicationTransitionRequestSerializer,
        responses={200: ApplicationEmployerSerializer},
    )
    def post(self, request, pk):
        application = get_object_or_404(_employer_applications(request), pk=pk)
        serializer = ApplicationTransitionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.transition_application(
                application,
                serializer.validated_data["status"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(
            ApplicationEmployerSerializer(_employer_applications(request).get(pk=pk)).data
        )


@extend_schema(tags=["employer"], summary="Request an interview (shortlisted applicants)")
class EmployerInterviewRequestView(APIView):
    permission_classes = [CanRecruit]
    serializer_class = InterviewCreateSerializer

    @extend_schema(request=InterviewCreateSerializer, responses={201: InterviewRequestSerializer})
    def post(self, request, pk):
        application = get_object_or_404(_employer_applications(request), pk=pk)
        serializer = InterviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            interview = services.request_interview(
                application,
                actor=request.user,
                proposed_at=d["proposed_at"],
                mode=d["mode"],
                location_text=d.get("location_text", ""),
                note=d.get("note", ""),
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(InterviewRequestSerializer(interview).data, status=status.HTTP_201_CREATED)


# ---- employer: talent ---------------------------------------------------------


def _require_talent_access(request, key: str | None) -> None:
    """Paid recruitment data (candidate cards) is readable only by a verified,
    active organisation whose plan still carries the capability — on reads as
    well as writes, so losing the plan closes the lists too. `key=None` when
    the caller's service already requires the capability (talent search)."""
    if not request.employer.can_recruit:
        raise_api(services.OrganizationNotVerified("The organisation must be verified and active."))
    if key is not None:
        services.employer_entitlements(request.employer).require(key)


def _visible_candidates(employer):
    """THE candidate visibility rule for one employer, shared by talent detail
    and the saved-candidates list: an active account that is currently
    discoverable, or that applied to one of this employer's jobs."""
    return (
        JobSeekerProfile.objects.filter(account__is_active=True)
        .filter(Q(discoverable_by_employers=True) | Q(applications__job__employer=employer))
        .distinct()
    )


def _talent_queryset():
    return (
        JobSeekerProfile.objects.filter(discoverable_by_employers=True, account__is_active=True)
        .select_related("general_specialty", "governorate", "city", "desired_governorate")
        .prefetch_related("skills", "languages")
        .order_by("-updated_at", "id")
    )


@extend_schema(
    tags=["talent"],
    summary=(
        "Talent search (entitled employers). One distinct filter set per day counts as one "
        "search; paging is free."
    ),
    parameters=[
        OpenApiParameter("q", str),
        OpenApiParameter("profession", str),
        OpenApiParameter("specialty", str),
        OpenApiParameter("degree", str, description="minimum degree"),
        OpenApiParameter("min_experience", int),
        OpenApiParameter("max_experience", int),
        OpenApiParameter("governorate", str),
        OpenApiParameter("city", str),
        OpenApiParameter("skill", str),
        OpenApiParameter("language", str),
        OpenApiParameter("language_level", str),
        OpenApiParameter("availability", str),
        OpenApiParameter("employment_type", str),
    ],
)
class TalentSearchView(_Throttled, generics.ListAPIView):
    permission_classes = [CanRecruit]
    serializer_class = TalentCardSerializer
    throttle_scope = "talent_search"
    filter_backends = [DjangoFilterBackend]
    filterset_class = TalentFilter
    queryset = JobSeekerProfile.objects.none()

    def list(self, request, *args, **kwargs):
        _require_talent_access(request, None)  # record_talent_search requires talent.search
        # Never charge a request that cannot execute: validate the filter set first.
        filterset = self.filterset_class(
            request.query_params, queryset=self.get_queryset(), request=request
        )
        if not filterset.is_valid():
            raise ValidationError(filterset.errors)
        services.record_talent_search(
            request.employer, dict(request.query_params.items()), actor=request.user
        )
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        return _talent_queryset()


@extend_schema(
    tags=["talent"],
    summary="Candidate professional profile (discoverable, or applied to one of my jobs)",
)
class TalentDetailView(APIView):
    permission_classes = [CanRecruit]
    serializer_class = TalentDetailSerializer

    @extend_schema(responses={200: TalentDetailSerializer})
    def get(self, request, pk):
        _require_talent_access(request, Keys.TALENT_SEARCH)
        qs = _visible_candidates(request.employer)
        profile = get_object_or_404(
            qs.select_related(
                "account", "general_specialty", "governorate", "city", "desired_governorate"
            ).prefetch_related("skills", "languages", "experiences", "education", "credentials"),
            pk=pk,
        )
        return Response(
            TalentDetailSerializer(profile, context={"employer": request.employer}).data
        )


@extend_schema(tags=["talent"])
class SavedCandidateListView(generics.ListCreateAPIView):
    """Saved candidates, newest first, on the standard paginated envelope.
    The relation stays stored when a candidate hides their profile; the
    professional card is returned only while `_visible_candidates` allows it."""

    permission_classes = [CanRecruit]
    serializer_class = SavedCandidateSerializer
    queryset = SavedCandidate.objects.none()
    filter_backends = []  # fixed newest-first order; no client ordering/filtering

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SavedCandidate.objects.none()
        _require_talent_access(self.request, Keys.TALENT_SAVE)
        return (
            SavedCandidate.objects.filter(
                employer=self.request.employer,
                job_seeker__in=_visible_candidates(self.request.employer),
            )
            .select_related(
                "job_seeker",
                "job_seeker__general_specialty",
                "job_seeker__governorate",
                "job_seeker__city",
            )
            .prefetch_related("job_seeker__skills", "job_seeker__languages")
            .order_by("-created_at", "-id")
        )

    @extend_schema(summary="My organisation's saved candidates (paginated, newest first)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=SaveCandidateSerializer,
        responses={201: SavedCandidateSerializer},
        summary="Save a candidate (private note never shown to the candidate)",
    )
    def post(self, request, *args, **kwargs):
        _require_talent_access(request, Keys.TALENT_SAVE)  # same gate as GET
        serializer = SaveCandidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_object_or_404(JobSeekerProfile, pk=serializer.validated_data["job_seeker"])
        try:
            saved = services.save_candidate(
                request.employer,
                profile,
                actor=request.user,
                note=serializer.validated_data.get("note", ""),
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(SavedCandidateSerializer(saved).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["talent"], summary="Remove a saved candidate")
class SavedCandidateDeleteView(APIView):
    permission_classes = [CanRecruit]
    serializer_class = None

    def delete(self, request, pk):
        _require_talent_access(
            request, Keys.TALENT_SAVE
        )  # suspended: lists and actions closed alike
        saved = get_object_or_404(SavedCandidate.objects.filter(employer=request.employer), pk=pk)
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["talent"])
class InvitationListView(_ThrottledOnWrite, generics.ListCreateAPIView):
    """Invitations sent by my organisation, newest first, on the standard
    paginated envelope. The rows stay stored when a candidate hides their
    profile; a row is listed (and its candidate card serialised) only while the
    shared visibility rule `_visible_candidates` allows it, so `count` is the
    number of rows the employer may actually see."""

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "internal": True}

    permission_classes = [CanRecruit]
    # POST only: reading the sent-invitations list must not spend the
    # invitation quota (see _ThrottledOnWrite).
    throttle_scope = "talent_invite"
    serializer_class = InvitationSerializer
    queryset = JobInvitation.objects.none()
    filter_backends = []  # fixed newest-first order; no client ordering/filtering

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return JobInvitation.objects.none()
        _require_talent_access(self.request, Keys.TALENT_INVITE)
        services.expire_overdue_invitations(employer=self.request.employer)
        return (
            JobInvitation.objects.filter(
                employer=self.request.employer,
                job_seeker__in=_visible_candidates(self.request.employer),
            )
            .select_related(
                "job",
                "job__employer",
                "job__governorate",
                "job__city",
                "job__general_specialty",
                "job_seeker",
                "job_seeker__general_specialty",
                "job_seeker__governorate",
                "job_seeker__city",
            )
            .prefetch_related("job_seeker__skills", "job_seeker__languages")
            .order_by("-created_at", "-id")
        )

    @extend_schema(summary="Invitations sent by my organisation (paginated, newest first)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=InviteSerializer,
        responses={201: InvitationSerializer},
        summary="Invite a discoverable candidate to apply to one of my open jobs (quota-consuming)",
    )
    def post(self, request, *args, **kwargs):
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        job = get_object_or_404(
            JobPost.objects.filter(employer=request.employer).select_related("employer"),
            pk=d["job"],
        )
        profile = get_object_or_404(JobSeekerProfile, pk=d["job_seeker"])
        try:
            invitation = services.invite_candidate(
                request.employer, job, profile, actor=request.user, message=d.get("message", "")
            )
        except services.JobsError as exc:
            raise_api(exc)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["talent"], summary="Cancel a pending invitation")
class InvitationCancelView(APIView):
    permission_classes = [CanRecruit]
    serializer_class = None

    @extend_schema(request=None, responses={200: InvitationSerializer})
    def post(self, request, pk):
        _require_talent_access(request, Keys.TALENT_INVITE)  # same gate as sending/listing
        invitation = get_object_or_404(
            JobInvitation.objects.filter(employer=request.employer).select_related(
                "job", "job_seeker"
            ),
            pk=pk,
        )
        try:
            services.cancel_invitation(invitation, actor=request.user)
        except services.JobsError as exc:
            raise_api(exc)
        data = InvitationSerializer(invitation, context={"internal": True}).data
        # THE candidate visibility rule applies here as on the list: a candidate
        # who is no longer discoverable and never applied is not rendered.
        if not _visible_candidates(request.employer).filter(pk=invitation.job_seeker_id).exists():
            data["candidate"] = None
        return Response(data)


# ---- administrators ---------------------------------------------------------


@extend_schema(tags=["admin"], summary="Employers (administrators)")
class AdminEmployerListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = EmployerAdminSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        "verification_status": ["exact"],
        "recruitment_status": ["exact"],
        "organization_type": ["exact"],
    }
    search_fields = ["name", "created_by__email"]
    queryset = Employer.objects.select_related(
        "governorate", "city", "provider_profile", "created_by"
    ).annotate(
        active_jobs=Count("jobs", filter=Q(jobs__status__in=["PENDING_ADMIN_REVIEW", "PUBLISHED"]))
    )


@extend_schema(tags=["admin"], summary="Set an employer's verification status")
class AdminEmployerVerificationView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = EmployerVerificationDecisionSerializer

    @extend_schema(
        request=EmployerVerificationDecisionSerializer, responses={200: EmployerAdminSerializer}
    )
    def post(self, request, pk):
        employer = get_object_or_404(Employer, pk=pk)
        serializer = EmployerVerificationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_employer_verification(
            employer,
            serializer.validated_data["status"],
            admin=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(EmployerAdminSerializer(AdminEmployerListView.queryset.get(pk=pk)).data)


@extend_schema(tags=["admin"], summary="Suspend or reactivate an employer's recruitment")
class AdminEmployerRecruitmentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = RecruitmentReasonSerializer

    @extend_schema(
        request=RecruitmentReasonSerializer,
        responses={200: EmployerAdminSerializer},
        parameters=[OpenApiParameter("status", str, description="ACTIVE or SUSPENDED")],
    )
    def post(self, request, pk, status_value):
        if status_value not in ("ACTIVE", "SUSPENDED"):
            raise ValidationError({"status": ["ACTIVE or SUSPENDED"]})
        employer = get_object_or_404(Employer, pk=pk)
        serializer = RecruitmentReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_employer_recruitment_status(
            employer,
            status_value,
            admin=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(EmployerAdminSerializer(AdminEmployerListView.queryset.get(pk=pk)).data)


def _admin_jobs():
    return (
        JobPost.objects.select_related(
            "employer",
            "employer__governorate",
            "employer__city",
            "employer__provider_profile",
            "employer__created_by",
            "governorate",
            "city",
            "general_specialty",
            "hiring_employer",
        )
        .annotate(applications_count=Count("applications"))
        .prefetch_related("transitions")
    )


@extend_schema(tags=["admin"], summary="Jobs for review (administrators)")
class AdminJobListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = JobAdminSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {"status": ["exact"], "employer": ["exact"]}

    def get_queryset(self):
        return _admin_jobs().order_by("-submitted_at", "-created_at")


@extend_schema(tags=["admin"], summary="Job details for review")
class AdminJobDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminAccount]
    serializer_class = JobAdminSerializer

    def get_queryset(self):
        return _admin_jobs()


def _admin_job_action(fn_name: str, summary: str, serializer=AdminDecisionSerializer, kw="note"):
    @extend_schema(tags=["admin"], summary=summary)
    class View(APIView):
        permission_classes = [IsAuthenticated, IsAdminAccount]
        serializer_class = serializer

        @extend_schema(request=serializer, responses={200: JobAdminSerializer})
        def post(self, request, pk):
            job = get_object_or_404(JobPost.objects.select_related("employer"), pk=pk)
            ser = serializer(data=request.data)
            ser.is_valid(raise_exception=True)
            value = ser.validated_data.get(kw, "")
            if fn_name in ("reject_job", "suspend_job") and not value:
                raise ValidationError({kw: ["A reason is required."]})
            try:
                getattr(services, fn_name)(job, admin=request.user, **{kw: value})
            except services.JobsError as exc:
                raise_api(exc)
            return Response(JobAdminSerializer(_admin_jobs().get(pk=pk)).data)

    View.__name__ = f"AdminJob{fn_name.title().replace('_', '')}View"
    return View


AdminJobApproveView = _admin_job_action("approve_job", "Approve a pending job (publishes it)")
AdminJobRejectView = _admin_job_action(
    "reject_job",
    "Reject a pending job with a reason",
    serializer=RecruitmentReasonSerializer,
    kw="reason",
)
AdminJobSuspendView = _admin_job_action(
    "suspend_job",
    "Suspend a published job with a reason",
    serializer=RecruitmentReasonSerializer,
    kw="reason",
)
AdminJobRestoreView = _admin_job_action("restore_job", "Restore a suspended job")
