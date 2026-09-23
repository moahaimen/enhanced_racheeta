"""Account use-cases. Views stay thin; business rules live here."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from . import emails
from .firebase import FirebaseIdentity, get_verifier
from .models import Account
from .roles import AccountRole
from .tokens import (  # noqa: F401 - re-exported for views
    decode_uid,
    email_verification_token,
    encode_uid,
    password_reset_token,
)

logger = logging.getLogger(__name__)


class InvalidToken(Exception):
    """Reset/verification link is invalid, expired or already used."""


class AlreadyVerified(Exception):
    pass


class EmailRequired(Exception):
    """Firebase identity carries no email address."""


class EmailNotVerified(Exception):
    """Firebase email is unverified but matches an existing account."""


class AccountInactive(Exception):
    pass


# ---- sessions --------------------------------------------------------------


def revoke_all_refresh_tokens(account: Account) -> int:
    """Blacklist every outstanding refresh token of the account."""
    count = 0
    for outstanding in OutstandingToken.objects.filter(user=account).iterator():
        _, created = BlacklistedToken.objects.get_or_create(token=outstanding)
        count += int(created)
    return count


# ---- password reset --------------------------------------------------------


def request_password_reset(email: str) -> None:
    """Send a reset link if an active account exists. Always returns silently."""
    normalized = Account.objects.normalize_email(email)
    account = Account.objects.filter(email=normalized, is_active=True).first()
    if account is None:
        logger.info("password reset requested for unknown or inactive email")
        return
    emails.send_password_reset_email(
        account, uid=encode_uid(account), token=password_reset_token.make_token(account)
    )
    logger.info("password reset email sent account=%s", account.pk)


@transaction.atomic
def confirm_password_reset(uid: str, token: str, new_password: str) -> Account:
    account = decode_uid(uid)
    if (
        account is None
        or not account.is_active
        or not password_reset_token.check_token(account, token)
    ):
        raise InvalidToken
    account.set_password(new_password)
    update_fields = ["password", "updated_at"]
    if account.email_verified_at is None:
        # Completing a reset proves control of the mailbox.
        account.email_verified_at = timezone.now()
        update_fields.append("email_verified_at")
    account.save(update_fields=update_fields)
    revoked = revoke_all_refresh_tokens(account)
    logger.info(
        "password reset completed account=%s refresh_tokens_revoked=%s", account.pk, revoked
    )
    return account


# ---- email verification ----------------------------------------------------


def request_email_verification(account: Account) -> None:
    if account.email_verified:
        raise AlreadyVerified
    emails.send_email_verification_email(
        account, uid=encode_uid(account), token=email_verification_token.make_token(account)
    )
    logger.info("email verification sent account=%s", account.pk)


def confirm_email_verification(uid: str, token: str) -> Account:
    account = decode_uid(uid)
    if account is None or not account.is_active:
        raise InvalidToken
    if account.email_verified:
        return account  # idempotent: the link was already used successfully
    if not email_verification_token.check_token(account, token):
        raise InvalidToken
    account.email_verified_at = timezone.now()
    account.save(update_fields=["email_verified_at", "updated_at"])
    logger.info("email verified account=%s", account.pk)
    return account


# ---- Firebase exchange -----------------------------------------------------


def _display_name(identity: FirebaseIdentity) -> str:
    if identity.name and identity.name.strip():
        return identity.name.strip()[:150]
    return (identity.email or "").split("@", 1)[0][:150] or "Racheeta user"


@transaction.atomic
def exchange_firebase_token(id_token: str, role: str | None = None) -> tuple[Account, bool]:
    """Verify a Firebase ID token server-side and return (account, created).

    Linking rules (see docs/AUTHENTICATION.md):
    * Existing account with this Firebase uid → sign in.
    * Otherwise an email is required.
    * Existing account with that email → link only if Firebase verified the
      email; an unverified email must never take over an existing account.
    * Otherwise create an account with an *unusable* password.
    """
    identity = get_verifier().verify(id_token)  # raises FirebaseTokenInvalid / NotConfigured

    account = Account.objects.filter(firebase_uid=identity.uid).first()
    if account is not None:
        if not account.is_active:
            raise AccountInactive
        return account, False

    if not identity.email:
        raise EmailRequired
    email = Account.objects.normalize_email(identity.email)

    account = Account.objects.filter(email=email).first()
    if account is not None:
        if not identity.email_verified:
            raise EmailNotVerified
        if not account.is_active:
            raise AccountInactive
        account.firebase_uid = identity.uid
        update_fields = ["firebase_uid", "updated_at"]
        if account.email_verified_at is None:
            account.email_verified_at = timezone.now()
            update_fields.append("email_verified_at")
        account.save(update_fields=update_fields)
        return account, False

    allowed = settings.RACHEETA["SELF_REGISTRATION_ROLES"]
    chosen_role = role if role in allowed else AccountRole.PATIENT
    phone = identity.phone_number or ""
    if phone and Account.objects.filter(phone_number=phone).exists():
        phone = ""  # never steal a phone number already attached elsewhere
    account = Account.objects.create_user(
        email=email,
        password=None,  # unusable password: Firebase accounts never get a fake one
        full_name=_display_name(identity),
        role=chosen_role,
        phone_number=phone,
        firebase_uid=identity.uid,
        email_verified_at=timezone.now() if identity.email_verified else None,
    )
    return account, True
