"""Iraqi phone numbers: one rule for every phone field (accounts, providers, businesses,
property sellers and listings, store orders).

Accepted input (spaces, dashes and brackets are ignored):
  * mobile   07[3-9]X XXX XXXX     e.g. 0770 123 4567 (Asiacell 077x, Zain 078x/079x, Korek 075x)
  * landline 0[1-6]X... (9-10 digits) e.g. 01 234 5678 (Baghdad), 040 123 4567
  * the same with the country code: +964 / 00964 / 964 instead of the leading 0.

Stored in the national form without spaces ("07701234567") so equality and uniqueness are exact.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from rest_framework import serializers

MOBILE_RE = re.compile(r"^07[3-9]\d{8}$")
LANDLINE_RE = re.compile(r"^0[1-6]\d{7,8}$")
_SEPARATORS = re.compile(r"[\s\-().]")

MESSAGE_MOBILE = "Enter an Iraqi mobile number, e.g. 0770 123 4567 or +964 770 123 4567."
MESSAGE_ANY = "Enter an Iraqi phone number, e.g. 0770 123 4567 or 01 234 5678."


def normalize_iraqi_phone(value: str, *, allow_landline: bool = True) -> str:
    """National form ("07701234567"), or ValidationError. Empty stays empty."""
    raw = _SEPARATORS.sub("", value or "")
    if raw == "":
        return ""
    if raw.startswith("+964"):
        raw = "0" + raw[4:]
    elif raw.startswith("00964"):
        raw = "0" + raw[5:]
    elif raw.startswith("964") and len(raw) >= 12:
        raw = "0" + raw[3:]
    if not raw.isdigit():
        raise ValidationError(MESSAGE_MOBILE if not allow_landline else MESSAGE_ANY, code="phone")
    if MOBILE_RE.match(raw) or (allow_landline and LANDLINE_RE.match(raw)):
        return raw
    raise ValidationError(MESSAGE_MOBILE if not allow_landline else MESSAGE_ANY, code="phone")


class IraqiPhoneField(serializers.CharField):
    """Serializer field: validates and normalizes an Iraqi phone number."""

    def __init__(self, *, allow_landline: bool = True, **kwargs):
        kwargs.setdefault("max_length", 32)
        self.allow_landline = allow_landline
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_iraqi_phone(value, allow_landline=self.allow_landline)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages[0], code="phone") from exc
