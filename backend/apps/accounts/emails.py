"""Transactional emails for account flows.

Provider integration point: Django's email backend (`EMAIL_URL`). Development
uses the console backend; production must configure SMTP or an API-backed
backend (docs/AUTHENTICATION.md → "Email provider"). Nothing here logs the
links or tokens.
"""

from django.conf import settings
from django.core.mail import send_mail

from .models import Account

_PASSWORD_RESET = {
    "ar": (
        "إعادة تعيين كلمة المرور — رشيتة",
        "مرحباً {name}،\n\n"
        "لإعادة تعيين كلمة المرور افتح الرابط التالي خلال {minutes} دقيقة:\n\n{link}\n\n"
        "إذا لم تطلب ذلك فتجاهل هذه الرسالة.\n",
    ),
    "en": (
        "Reset your Racheeta password",
        "Hello {name},\n\n"
        "Open this link within {minutes} minutes to choose a new password:\n\n{link}\n\n"
        "If you did not request this, ignore this email.\n",
    ),
}

_EMAIL_VERIFICATION = {
    "ar": (
        "تأكيد البريد الإلكتروني — رشيتة",
        "مرحباً {name}،\n\n"
        "لتأكيد بريدك الإلكتروني افتح الرابط التالي خلال {hours} ساعة:\n\n{link}\n",
    ),
    "en": (
        "Verify your Racheeta email address",
        "Hello {name},\n\n"
        "Open this link within {hours} hours to verify your email address:\n\n{link}\n",
    ),
}


def _lang(account: Account) -> str:
    return account.preferred_language if account.preferred_language in ("ar", "en") else "ar"


def frontend_link(path: str, **query: str) -> str:
    from urllib.parse import urlencode

    base = settings.RACHEETA["FRONTEND_URL"]
    return f"{base}{path}?{urlencode(query)}"


def send_password_reset_email(account: Account, uid: str, token: str) -> None:
    subject, body = _PASSWORD_RESET[_lang(account)]
    link = frontend_link("/reset-password", uid=uid, token=token)
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    send_mail(
        subject,
        body.format(name=account.full_name, link=link, minutes=minutes),
        settings.DEFAULT_FROM_EMAIL,
        [account.email],
        fail_silently=False,
    )


def send_email_verification_email(account: Account, uid: str, token: str) -> None:
    subject, body = _EMAIL_VERIFICATION[_lang(account)]
    link = frontend_link("/verify-email", uid=uid, token=token)
    hours = int(settings.RACHEETA["EMAIL_VERIFICATION_TIMEOUT"].total_seconds() // 3600)
    send_mail(
        subject,
        body.format(name=account.full_name, link=link, hours=hours),
        settings.DEFAULT_FROM_EMAIL,
        [account.email],
        fail_silently=False,
    )
