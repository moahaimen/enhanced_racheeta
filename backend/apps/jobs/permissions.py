"""Organisation-scoped permissions. Ownership never comes from client ids:
views resolve the caller's active membership and scope every queryset."""

from rest_framework.permissions import BasePermission

from .services import membership_for
from .types import MemberRole


class IsEmployerMember(BasePermission):
    """Any active member of an organisation (OWNER, RECRUITER, VIEWER)."""

    message = "You are not a member of a recruiting organisation."

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        membership = membership_for(request.user)
        if membership is None:
            return False
        request.employer_membership = membership
        request.employer = membership.employer
        return True


class CanRecruit(IsEmployerMember):
    """OWNER or RECRUITER: may create/edit jobs, act on applicants, search talent."""

    message = "Only owners and recruiters can do this."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.employer_membership.role in (
            MemberRole.OWNER,
            MemberRole.RECRUITER,
        )


class IsEmployerOwner(IsEmployerMember):
    message = "Only the organisation owner can do this."

    def has_permission(self, request, view) -> bool:
        return (
            super().has_permission(request, view)
            and request.employer_membership.role == MemberRole.OWNER
        )


class HasJobSeekerProfile(BasePermission):
    message = "Create your professional profile first."

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        profile = getattr(request.user, "job_seeker_profile", None)
        if profile is None:
            return False
        request.job_seeker = profile
        return True
