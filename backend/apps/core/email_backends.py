"""Email transport over the Resend HTTPS API (`EMAIL_PROVIDER=resend`).

Racheeta sends transactional mail through Django's email-backend interface (`send_mail`). The
existing transport is Django's SMTP/console backend selected by `EMAIL_URL`; this module adds a
second transport next to it without touching any call site:

    apps.accounts.emails.send_mail(...)  ->  settings.EMAIL_BACKEND
                                               |- Django SMTP/console   (EMAIL_PROVIDER=django)
                                               `- ResendEmailBackend    (EMAIL_PROVIDER=resend)

Why HTTPS instead of SMTP: Railway may block outbound SMTP ports (587), while HTTPS/443 always
works. Standard library only (no SDK, no new dependency, ADR-062). Hard rules kept here:

* HTTPS endpoint only; every request has a finite timeout (`settings.EMAIL_TIMEOUT`);
* redirects are never followed (a redirect would re-send the Authorization header elsewhere);
* the API key and the message content (links, tokens, addresses) never appear in an exception
  message or a log line; a failure carries only the HTTP status and Resend's error *name*;
* unsupported features (attachments) fail loudly instead of being silently dropped.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
USER_AGENT = "racheeta-backend/1.0 (+resend-https)"
_MAX_RESPONSE_BYTES = 65536
_SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class ResendEmailError(Exception):
    """The message was not accepted by Resend. The text is safe to log (no key, no content)."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D102
        return None  # turns every 3xx into an HTTPError instead of resending the credential


_opener = urllib.request.build_opener(_NoRedirect)


def _has_control(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


class ResendEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently: bool = False, api_key: str | None = None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key if api_key is not None else getattr(settings, "RESEND_API_KEY", "")
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", None) or 10

    # -- BaseEmailBackend ---------------------------------------------------------------------
    def send_messages(self, email_messages) -> int:
        sent = 0
        for message in email_messages or ():
            try:
                self._send(message)
            except Exception:
                if not self.fail_silently:
                    raise
                continue
            sent += 1
        return sent

    # -- internals ----------------------------------------------------------------------------
    def _payload(self, message) -> dict:
        if message.attachments:
            raise ResendEmailError("attachments are not supported by the Resend transport")
        sender = message.from_email or settings.DEFAULT_FROM_EMAIL
        recipients = list(message.to)
        if not sender or not recipients:
            raise ResendEmailError("a message needs a sender and at least one recipient")
        fields = [sender, message.subject, *recipients, *message.cc, *message.bcc]
        fields += list(message.reply_to)
        if any(_has_control(value) for value in fields):
            raise ResendEmailError("header values must not contain control characters")
        payload: dict = {"from": sender, "to": recipients, "subject": message.subject}
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        html = None
        if getattr(message, "content_subtype", "plain") == "html":
            html = message.body
        else:
            payload["text"] = message.body
        for content, mimetype in getattr(message, "alternatives", ()):
            if mimetype == "text/html":
                html = content
        if html is not None:
            payload["html"] = html
        return payload

    def _send(self, message) -> None:
        key = self.api_key
        if not key or _has_control(key) or key != key.strip():
            raise ResendEmailError("RESEND_API_KEY is missing or malformed")
        request = urllib.request.Request(  # noqa: S310 - fixed https URL constant
            RESEND_API_URL,
            data=json.dumps(self._payload(message)).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                # Resend's edge rejects the default python-urllib agent.
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with _opener.open(request, timeout=self.timeout) as response:  # noqa: S310
                status = response.status
                raw = response.read(_MAX_RESPONSE_BYTES)
        except urllib.error.HTTPError as exc:
            raise ResendEmailError(self._describe_http_error(exc)) from None
        except TimeoutError:
            raise ResendEmailError(f"Resend request timed out after {self.timeout}s") from None
        except (urllib.error.URLError, OSError) as exc:
            # The reason (e.g. "connection refused", "certificate verify failed") is useful and
            # contains no secret; the URL and headers are not part of it.
            reason = getattr(exc, "reason", exc)
            raise ResendEmailError(f"Resend request failed: {type(reason).__name__}") from None
        if status not in (200, 201):
            raise ResendEmailError(f"Resend answered unexpected HTTP {status}")
        try:
            body = json.loads(raw)
            message_id = body["id"]
        except (ValueError, KeyError, TypeError):
            raise ResendEmailError("Resend answered with an unexpected body") from None
        if not isinstance(message_id, str) or not message_id:
            raise ResendEmailError("Resend answered with an unexpected body")
        logger.info("email accepted by resend id=%s", message_id[:64])

    @staticmethod
    def _describe_http_error(exc: urllib.error.HTTPError) -> str:
        name = ""
        try:
            data = json.loads(exc.read(_MAX_RESPONSE_BYTES))
            candidate = data.get("name") if isinstance(data, dict) else None
            if isinstance(candidate, str) and _SAFE_NAME.fullmatch(candidate):
                name = f" ({candidate})"
        except Exception:  # noqa: BLE001 - the error body is optional detail only
            logger.debug("resend error body not parseable")
        return f"Resend rejected the request: HTTP {exc.code}{name}"
