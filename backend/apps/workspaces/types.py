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
    # Seller (business) specialist roles — docs/MARKETPLACE_COMMERCE.md §Seller roles
    PRODUCT_EDITOR = "PRODUCT_EDITOR", "Product editor"
    STOCK_MANAGER = "STOCK_MANAGER", "Stock manager"
    FULFILLMENT = "FULFILLMENT", "Fulfillment"
    FINANCE = "FINANCE", "Finance (read-only statements)"


# Same choice set as employer memberships (one OpenAPI enum, one meaning).
MemberStatus = JobsMemberStatus


# Roles that can be granted through a membership row (OWNER comes from ownership only).
GRANTABLE_ROLES = (
    OrgRole.MANAGER,
    OrgRole.STAFF,
    OrgRole.VIEWER,
    OrgRole.PRODUCT_EDITOR,
    OrgRole.STOCK_MANAGER,
    OrgRole.FULFILLMENT,
    OrgRole.FINANCE,
)
# Specialist roles exist only for businesses (sellers), never for facilities.
COMPANY_ONLY_ROLES = frozenset(
    {OrgRole.PRODUCT_EDITOR, OrgRole.STOCK_MANAGER, OrgRole.FULFILLMENT, OrgRole.FINANCE}
)

_O, _M, _S, _V = OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER
_PE, _SM, _FU, _FI = (
    OrgRole.PRODUCT_EDITOR,
    OrgRole.STOCK_MANAGER,
    OrgRole.FULFILLMENT,
    OrgRole.FINANCE,
)
_ALL_COMPANY = frozenset({_O, _M, _S, _V, _PE, _SM, _FU, _FI})

# Capability matrix: organization capability -> roles that hold it.
CAPABILITIES: dict[str, frozenset[str]] = {
    # facility
    "facility.view": frozenset({OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}),
    "facility.reservations.view": frozenset(
        {OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF, OrgRole.VIEWER}
    ),
    "facility.reservations.manage": frozenset({OrgRole.OWNER, OrgRole.MANAGER, OrgRole.STAFF}),
    # business (seller)
    "company.view": _ALL_COMPANY,
    "company.orders.view": frozenset({_O, _M, _S, _V, _FU, _FI, _SM}),
    "company.orders.manage": frozenset({_O, _M, _S, _FU}),  # accept, decline, ship
    "company.returns.manage": frozenset({_O, _M, _FU}),  # approve/reject, mark received
    "company.quotes.view": frozenset({_O, _M, _S, _V, _FI}),
    "company.quotes.respond": frozenset({_O, _M}),
    "company.products.view": _ALL_COMPANY,
    "company.products.edit": frozenset({_O, _M, _PE}),
    "company.stock.manage": frozenset({_O, _M, _SM}),
    "company.offers.manage": frozenset({_O, _M}),  # seller-funded coupons and offers
    "company.finance.view": frozenset({_O, _FI}),  # statement, payouts, commission
    "company.campaigns.view": frozenset({_O, _M}),
    # both
    "members.view": frozenset({OrgRole.OWNER, OrgRole.MANAGER}),
    "members.manage": frozenset({OrgRole.OWNER}),
    # Owner-only areas of the organization's own account (recruitment, sponsored placement,
    # the professional B2B catalogue and quotes the ORGANIZATION requests as a buyer).
    "org.owner_tools": frozenset({OrgRole.OWNER}),
}


def role_has(role: str | None, capability: str) -> bool:
    return role is not None and role in CAPABILITIES.get(capability, frozenset())
