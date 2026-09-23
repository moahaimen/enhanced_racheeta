"""Provider use-cases: verification transitions and membership workflow."""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ProviderMembership, ProviderProfile
from .types import (
    ADMIN_VERIFICATION_TARGETS,
    VERIFICATION_REQUESTABLE_FROM,
    MembershipSide,
    MembershipStatus,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class InvalidTransition(Exception):
    pass


class NotAParty(Exception):
    pass


class DuplicateMembership(Exception):
    pass


# ---- verification ----------------------------------------------------------


def request_verification(profile: ProviderProfile) -> ProviderProfile:
    if profile.verification_status not in VERIFICATION_REQUESTABLE_FROM:
        raise InvalidTransition(
            f"Verification cannot be requested from status {profile.verification_status}."
        )
    now = timezone.now()
    profile.verification_status = VerificationStatus.PENDING
    profile.verification_requested_at = now
    profile.verification_changed_at = now
    profile.save(
        update_fields=[
            "verification_status",
            "verification_requested_at",
            "verification_changed_at",
            "updated_at",
        ]
    )
    logger.info("verification requested provider=%s", profile.pk)
    return profile


def set_verification(
    profile: ProviderProfile, status: str, note: str = "", *, by
) -> ProviderProfile:
    """Administrator decision. `by` is the acting account (for the log / future audit)."""
    if status not in ADMIN_VERIFICATION_TARGETS:
        raise InvalidTransition(f"{status} is not an administrator-settable status.")
    now = timezone.now()
    profile.verification_status = status
    profile.verification_note = note
    profile.verification_changed_at = now
    if status == VerificationStatus.VERIFIED:
        profile.verified_at = now
    profile.save(
        update_fields=[
            "verification_status",
            "verification_note",
            "verification_changed_at",
            "verified_at",
            "updated_at",
        ]
    )
    logger.info(
        "verification set provider=%s status=%s by=%s", profile.pk, status, getattr(by, "pk", None)
    )
    return profile


# ---- memberships -----------------------------------------------------------


@transaction.atomic
def create_membership(
    *, initiator: ProviderProfile, counterpart: ProviderProfile, role_title: str = ""
) -> ProviderMembership:
    """Practitioner requests to join a facility, or facility invites a practitioner."""
    if initiator.pk == counterpart.pk:
        raise InvalidTransition("A provider cannot be its own facility.")
    if initiator.is_practitioner and counterpart.is_facility:
        practitioner, facility, side = initiator, counterpart, MembershipSide.PRACTITIONER
    elif initiator.is_facility and counterpart.is_practitioner:
        practitioner, facility, side = counterpart, initiator, MembershipSide.FACILITY
    else:
        raise InvalidTransition("Memberships link a practitioner with a facility.")
    try:
        membership = ProviderMembership.objects.create(
            practitioner=practitioner,
            facility=facility,
            initiated_by=side,
            role_title=role_title,
            status=MembershipStatus.PENDING,
        )
    except IntegrityError as exc:
        raise DuplicateMembership from exc
    logger.info("membership created id=%s by=%s", membership.pk, side)
    return membership


def _require_party(membership: ProviderMembership, actor: ProviderProfile) -> str:
    side = membership.side_of(actor)
    if side is None:
        raise NotAParty
    return side


def accept_membership(membership: ProviderMembership, actor: ProviderProfile) -> ProviderMembership:
    side = _require_party(membership, actor)
    if membership.status != MembershipStatus.PENDING:
        raise InvalidTransition("Only pending memberships can be accepted.")
    if side == membership.initiated_by:
        raise InvalidTransition("The initiating side cannot accept its own request.")
    now = timezone.now()
    membership.status = MembershipStatus.ACTIVE
    membership.responded_at = now
    membership.joined_at = now
    membership.save(update_fields=["status", "responded_at", "joined_at", "updated_at"])
    return membership


def reject_membership(membership: ProviderMembership, actor: ProviderProfile) -> ProviderMembership:
    """The counterpart rejects, or the initiator withdraws; both end as REJECTED."""
    _require_party(membership, actor)
    if membership.status != MembershipStatus.PENDING:
        raise InvalidTransition("Only pending memberships can be rejected.")
    membership.status = MembershipStatus.REJECTED
    membership.responded_at = timezone.now()
    membership.save(update_fields=["status", "responded_at", "updated_at"])
    return membership


def end_membership(membership: ProviderMembership, actor: ProviderProfile) -> ProviderMembership:
    _require_party(membership, actor)
    if membership.status != MembershipStatus.ACTIVE:
        raise InvalidTransition("Only active memberships can be ended.")
    membership.status = MembershipStatus.ENDED
    membership.ended_at = timezone.now()
    membership.save(update_fields=["status", "ended_at", "updated_at"])
    return membership
