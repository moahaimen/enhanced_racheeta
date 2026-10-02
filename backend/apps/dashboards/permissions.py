"""Dashboard permission classes. Each resolves the caller's own state through `access` and
publishes it on the request; none reads an identifier from the client."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from . import access


class IsPatientAccount(BasePermission):
    message = "Only patient accounts have this dashboard."

    def has_permission(self, request, view) -> bool:
        return access.is_patient(request.user)


class IsPractitionerProvider(BasePermission):
    message = "Only practitioner provider accounts (doctor, nurse, therapist) have this dashboard."

    def has_permission(self, request, view) -> bool:
        profile = access.practitioner_profile_for(request.user)
        request.provider_profile = profile
        return profile is not None


class IsFacilityProvider(BasePermission):
    message = "Only facility provider accounts have this dashboard."

    def has_permission(self, request, view) -> bool:
        profile = access.facility_profile_for(request.user)
        request.provider_profile = profile
        return profile is not None


class HasCompanyProfile(BasePermission):
    message = "Only medical company accounts with a company profile have this dashboard."

    def has_permission(self, request, view) -> bool:
        company = access.company_for(request.user)
        request.medical_company = company
        return company is not None


class IsRecruitingOrganizationMember(BasePermission):
    """Any ACTIVE member of an organisation (OWNER, RECRUITER or VIEWER): the dashboard is
    read-only and shows only the member's own organisation."""

    message = "You are not a member of a recruiting organisation."

    def has_permission(self, request, view) -> bool:
        membership = access.recruiter_membership_for(request.user)
        request.employer_membership = membership
        return membership is not None
