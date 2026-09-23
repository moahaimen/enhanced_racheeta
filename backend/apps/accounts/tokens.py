"""Stateless, expiring, single-use tokens for email-based flows.

Both generators follow Django's PasswordResetTokenGenerator design: the token
is an HMAC (keyed by SECRET_KEY + a per-purpose salt) over a timestamp and a
snapshot of account state. It never contains the password. Because the state
snapshot changes when the flow completes (password hash changes; verification
timestamp is set), a token cannot be replayed after use. Expiry is enforced by
the embedded timestamp.

Tokens are sent to the address on the account only; the account is looked up
through an opaque base64 UUID (`uid`) that accompanies the token.
"""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode

from .models import Account


class PasswordResetToken(PasswordResetTokenGenerator):
    key_salt = "apps.accounts.tokens.PasswordResetToken"

    # Timeout comes from settings.PASSWORD_RESET_TIMEOUT (seconds).


class EmailVerificationToken(PasswordResetTokenGenerator):
    key_salt = "apps.accounts.tokens.EmailVerificationToken"

    def _make_hash_value(self, user, timestamp):
        verified = "" if user.email_verified_at is None else user.email_verified_at.isoformat()
        return f"{user.pk}{user.email}{verified}{timestamp}"

    @property
    def timeout_seconds(self) -> int:
        return int(settings.RACHEETA["EMAIL_VERIFICATION_TIMEOUT"].total_seconds())

    def check_token(self, user, token):
        # Django's algorithm with a purpose-specific timeout instead of
        # settings.PASSWORD_RESET_TIMEOUT.
        if not (user and token):
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(self._make_token_with_timestamp(user, ts, secret), token):
                break
        else:
            return False
        return (self._num_seconds(self._now()) - ts) <= self.timeout_seconds


password_reset_token = PasswordResetToken()
email_verification_token = EmailVerificationToken()


def encode_uid(account: Account) -> str:
    return urlsafe_base64_encode(force_bytes(str(account.pk)))


def decode_uid(uid: str) -> Account | None:
    """Return the account for an opaque uid, or None for anything invalid."""
    try:
        pk = urlsafe_base64_decode(uid).decode()
        return Account.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, Account.DoesNotExist):
        return None
