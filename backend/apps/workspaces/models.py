"""Organization staff memberships (see types.py for the meaning and the capability matrix)."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel

from .types import GRANTABLE_ROLES, MemberStatus, OrgRole


class OrganizationMember(BaseModel):
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="org_memberships"
    )
    # Exactly one organization: a facility profile OR a business.
    facility = models.ForeignKey(
        "providers.ProviderProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="staff_memberships",
    )
    company = models.ForeignKey(
        "marketplace.MedicalCompany",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="staff_memberships",
    )
    role = models.CharField(max_length=16, choices=OrgRole.choices)
    status = models.CharField(
        max_length=16, choices=MemberStatus.choices, default=MemberStatus.ACTIVE
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workspaces_org_member"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(facility__isnull=False) & Q(company__isnull=True))
                | (Q(facility__isnull=True) & Q(company__isnull=False)),
                name="workspaces_member_one_org",
            ),
            models.CheckConstraint(
                condition=Q(role__in=[r.value for r in GRANTABLE_ROLES]),
                name="workspaces_member_grantable_role",
            ),
            models.UniqueConstraint(
                fields=["account", "facility"],
                condition=Q(status="ACTIVE", facility__isnull=False),
                name="workspaces_member_one_active_facility",
            ),
            models.UniqueConstraint(
                fields=["account", "company"],
                condition=Q(status="ACTIVE", company__isnull=False),
                name="workspaces_member_one_active_company",
            ),
        ]
        indexes = [models.Index(fields=["account", "status"], name="workspaces_member_acct_idx")]

    def __str__(self) -> str:
        return f"{self.account_id} {self.role} @ {self.facility_id or self.company_id}"
