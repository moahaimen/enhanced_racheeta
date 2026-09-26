from django.urls import path

from . import views

urlpatterns = [
    # public
    path("jobs", views.JobListView.as_view(), name="jobs-list"),
    path("employers/<uuid:pk>", views.EmployerPublicView.as_view(), name="employers-public"),
    # job seeker
    path("jobs/me/profile", views.MySeekerProfileView.as_view(), name="seeker-profile"),
    path(
        "jobs/me/profile/experiences",
        views.MyExperienceListView.as_view(),
        name="seeker-experiences",
    ),
    path(
        "jobs/me/profile/experiences/<uuid:pk>",
        views.MyExperienceDetailView.as_view(),
        name="seeker-experience",
    ),
    path("jobs/me/profile/education", views.MyEducationListView.as_view(), name="seeker-education"),
    path(
        "jobs/me/profile/education/<uuid:pk>",
        views.MyEducationDetailView.as_view(),
        name="seeker-education-item",
    ),
    path("jobs/me/profile/skills", views.MySkillListView.as_view(), name="seeker-skills"),
    path(
        "jobs/me/profile/skills/<uuid:pk>", views.MySkillDetailView.as_view(), name="seeker-skill"
    ),
    path("jobs/me/profile/languages", views.MyLanguageListView.as_view(), name="seeker-languages"),
    path(
        "jobs/me/profile/languages/<uuid:pk>",
        views.MyLanguageDetailView.as_view(),
        name="seeker-language",
    ),
    path(
        "jobs/me/profile/credentials",
        views.MyCredentialListView.as_view(),
        name="seeker-credentials",
    ),
    path(
        "jobs/me/profile/credentials/<uuid:pk>",
        views.MyCredentialDetailView.as_view(),
        name="seeker-credential",
    ),
    path("jobs/me/applications", views.MyApplicationListView.as_view(), name="seeker-applications"),
    path(
        "jobs/me/applications/<uuid:pk>",
        views.MyApplicationDetailView.as_view(),
        name="seeker-application",
    ),
    path(
        "jobs/me/applications/<uuid:pk>/withdraw",
        views.MyApplicationWithdrawView.as_view(),
        name="seeker-application-withdraw",
    ),
    path(
        "jobs/me/interviews/<uuid:pk>/respond",
        views.MyInterviewResponseView.as_view(),
        name="seeker-interview-respond",
    ),
    path("jobs/me/invitations", views.MyInvitationListView.as_view(), name="seeker-invitations"),
    path(
        "jobs/me/invitations/<uuid:pk>/respond",
        views.MyInvitationResponseView.as_view(),
        name="seeker-invitation-respond",
    ),
    # recruitment messages (parties of an application)
    path(
        "recruitment/applications/<uuid:pk>/messages",
        views.ApplicationMessagesView.as_view(),
        name="recruitment-messages",
    ),
    # employer
    path("jobs/employer", views.MyEmployerView.as_view(), name="employer-me"),
    path(
        "jobs/employer/verification/request",
        views.MyEmployerVerificationRequestView.as_view(),
        name="employer-verification-request",
    ),
    path("jobs/employer/members", views.MyEmployerMembersView.as_view(), name="employer-members"),
    path(
        "jobs/employer/members/<uuid:pk>/end",
        views.MyEmployerMemberEndView.as_view(),
        name="employer-member-end",
    ),
    path("jobs/employer/billing", views.MyEmployerBillingView.as_view(), name="employer-billing"),
    path(
        "jobs/employer/billing/request",
        views.MyEmployerSubscriptionRequestView.as_view(),
        name="employer-billing-request",
    ),
    path("jobs/employer/jobs", views.EmployerJobListView.as_view(), name="employer-jobs"),
    path(
        "jobs/employer/jobs/<uuid:pk>", views.EmployerJobDetailView.as_view(), name="employer-job"
    ),
    path(
        "jobs/employer/jobs/<uuid:pk>/submit",
        views.EmployerJobSubmitView.as_view(),
        name="employer-job-submit",
    ),
    path(
        "jobs/employer/jobs/<uuid:pk>/close",
        views.EmployerJobCloseView.as_view(),
        name="employer-job-close",
    ),
    path(
        "jobs/employer/jobs/<uuid:pk>/archive",
        views.EmployerJobArchiveView.as_view(),
        name="employer-job-archive",
    ),
    path(
        "jobs/employer/jobs/<uuid:pk>/feature",
        views.EmployerJobFeatureView.as_view(),
        name="employer-job-feature",
    ),
    path(
        "jobs/employer/jobs/<uuid:pk>/applications",
        views.EmployerJobApplicationsView.as_view(),
        name="employer-job-applications",
    ),
    path(
        "jobs/employer/applications/<uuid:pk>",
        views.EmployerApplicationDetailView.as_view(),
        name="employer-application",
    ),
    path(
        "jobs/employer/applications/<uuid:pk>/transition",
        views.EmployerApplicationTransitionView.as_view(),
        name="employer-application-transition",
    ),
    path(
        "jobs/employer/applications/<uuid:pk>/interviews",
        views.EmployerInterviewRequestView.as_view(),
        name="employer-application-interview",
    ),
    # talent
    path("talent", views.TalentSearchView.as_view(), name="talent-search"),
    path("talent/saved", views.SavedCandidateListView.as_view(), name="talent-saved"),
    path(
        "talent/saved/<uuid:pk>",
        views.SavedCandidateDeleteView.as_view(),
        name="talent-saved-delete",
    ),
    path("talent/invitations", views.InvitationListView.as_view(), name="talent-invitations"),
    path(
        "talent/invitations/<uuid:pk>/cancel",
        views.InvitationCancelView.as_view(),
        name="talent-invitation-cancel",
    ),
    path("talent/<uuid:pk>", views.TalentDetailView.as_view(), name="talent-detail"),
    # administrators
    path(
        "admin/recruitment/employers", views.AdminEmployerListView.as_view(), name="admin-employers"
    ),
    path(
        "admin/recruitment/employers/<uuid:pk>/verification",
        views.AdminEmployerVerificationView.as_view(),
        name="admin-employer-verification",
    ),
    path(
        "admin/recruitment/employers/<uuid:pk>/recruitment/<str:status_value>",
        views.AdminEmployerRecruitmentStatusView.as_view(),
        name="admin-employer-recruitment",
    ),
    path("admin/recruitment/jobs", views.AdminJobListView.as_view(), name="admin-jobs"),
    path("admin/recruitment/jobs/<uuid:pk>", views.AdminJobDetailView.as_view(), name="admin-job"),
    path(
        "admin/recruitment/jobs/<uuid:pk>/approve",
        views.AdminJobApproveView.as_view(),
        name="admin-job-approve",
    ),
    path(
        "admin/recruitment/jobs/<uuid:pk>/reject",
        views.AdminJobRejectView.as_view(),
        name="admin-job-reject",
    ),
    path(
        "admin/recruitment/jobs/<uuid:pk>/suspend",
        views.AdminJobSuspendView.as_view(),
        name="admin-job-suspend",
    ),
    path(
        "admin/recruitment/jobs/<uuid:pk>/restore",
        views.AdminJobRestoreView.as_view(),
        name="admin-job-restore",
    ),
    # public job detail + apply (after the /jobs/me and /jobs/employer prefixes)
    path("jobs/<uuid:pk>", views.JobDetailView.as_view(), name="jobs-detail"),
    path("jobs/<uuid:pk>/apply", views.ApplyView.as_view(), name="jobs-apply"),
]
