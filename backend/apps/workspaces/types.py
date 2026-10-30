"""Organization staff roles and the capability matrix (docs/PERMISSIONS.md §Organizations).

An organization is an existing domain object — a facility (`ProviderProfile` of a facility type)
or a business (`MedicalCompany`). Its OWNER is the account that owns that object; nobody needs a
membership row to be owner. Other accounts get access only through an ACTIVE `OrganizationMember`
row of THAT organization: a role label never grants access to another organization's records.

This is distinct from `ProviderMembership` (practitioner works at a facility — public affiliation,
no access to the facility's records) and `EmployerMembership` (recruitment team). They are linked
in the workspace list but never conflated.
"""

from django.db import models

from apps.jobs.types import MemberStatus as JobsMemberStatus


class OrgKind(models.TextChoices):
    FACILITY = "FACILITY", "Facility"
    COMPANY = "COMPANY", "Business"


class OrgRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    MANAGER = "MANAGER", "Manager"
    STAFF = "STAFF", "Staff"
    VIEWER = "VIEWER", "Viewer"


# Same choice set as employer memberships (one OpenAPI enum, one meaning).
MemberStatus = JobsMemberStatus


# Roles that can be granted through a membership row (OWNER comes from ownership only).
GRANTABLE_ROLES = (OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER)

# Capability matrix: organization capability -> roles that hold it.
CAPABILITIES: dict[str, frozenset[str]] = {
    # facility
    "facility.view": frozenset({OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}),
    "facility.reservations.view": frozenset(
        {OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}
    ),
    "facility.reservations.manage": frozenset({OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF}),
    # business
    "company.view": frozenset({OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}),
    "company.orders.view": frozenset(
        {OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}
    ),
    "company.orders.manage": frozenset({OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF}),
    "company.quotes.view": frozenset(
        {OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}
    ),
    "company.quotes.respond": frozenset({OrgRole.OWNER, OrgRole.MANAGER}),
    # both
    "members.view": frozenset({OrgRole.OWNER, OrgRole.MANAGER}),
    "members.manage": frozenset({OrgRole.OWNER}),
}


def role_has(role: str | None, capability: str) -> bool:
    return role is not None and role in CAPABILITIES.get(capability, frozenset())
