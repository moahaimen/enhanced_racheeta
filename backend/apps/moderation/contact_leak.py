"""ContactLeakDetector — keeps recruitment communication inside Racheeta.

Detects attempts to place direct contact channels in recruitment text:
phone numbers (Iraqi and international, with Arabic/Persian digits and
separators), e-mail addresses, WhatsApp / Telegram references, and URLs.
It explains which category triggered. It is deliberately simple and
transparent; it is not a censorship system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DIGIT_MAP = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
DIGIT_MAP.update({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")})


@dataclass(frozen=True)
class Finding:
    category: str  # PHONE | EMAIL | WHATSAPP | TELEGRAM | URL
    excerpt: str


EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+\s*(?:@|\(at\)|\[at\])\s*[A-Za-z0-9.-]+\s*(?:\.|\(dot\)|\[dot\])\s*[A-Za-z]{2,}",
    re.IGNORECASE,
)
URL_RE = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+\.(?:com|net|org|io|me|iq|co|info|link|site)(?:/\S*)?",
    re.IGNORECASE,
)
WHATSAPP_RE = re.compile(
    r"wa\.me|whats\s*app|whatsap|واتس\s*اب|واتساب|وتس\s*اب|وتساب", re.IGNORECASE
)
TELEGRAM_RE = re.compile(r"t\.me/|telegram|تلغرام|تلكرام|تيليجرام|تيليغرام|تلجرام", re.IGNORECASE)
# After digit normalisation: +964..., 00964..., 07xxxxxxxxx (11 digits) or any 10+ digit run.
PHONE_RE = re.compile(r"(?:\+|00)?964\d{9,10}|(?<!\d)07\d{9}(?!\d)|(?<!\d)\d{10,15}(?!\d)")
SEPARATORS_RE = re.compile(r"(?<=\d)[\s\-\.\(\)_]+(?=\d)")


def normalize(text: str) -> str:
    text = text.translate(DIGIT_MAP)
    # collapse separators that sit between digits so "077 0 123-4567" becomes one run
    prev = None
    while prev != text:
        prev = text
        text = SEPARATORS_RE.sub("", text)
    return text


class ContactLeakDetector:
    def scan(self, text: str | None) -> list[Finding]:
        if not text:
            return []
        findings: list[Finding] = []
        for match in EMAIL_RE.finditer(text):
            findings.append(Finding("EMAIL", match.group(0)))
        for match in WHATSAPP_RE.finditer(text):
            findings.append(Finding("WHATSAPP", match.group(0)))
        for match in TELEGRAM_RE.finditer(text):
            findings.append(Finding("TELEGRAM", match.group(0)))
        for match in URL_RE.finditer(EMAIL_RE.sub(" ", text)):
            findings.append(Finding("URL", match.group(0)))
        normalized = normalize(text)
        for match in PHONE_RE.finditer(normalized):
            findings.append(Finding("PHONE", match.group(0)))
        return findings

    def categories(self, text: str | None) -> list[str]:
        seen: list[str] = []
        for f in self.scan(text):
            if f.category not in seen:
                seen.append(f.category)
        return seen


detector = ContactLeakDetector()

CONTACT_NOT_ALLOWED = (
    "Direct contact information is not allowed in recruitment content. "
    "Use Racheeta's communication tools."
)


def validate_no_contact_info(value: str | None) -> str | None:
    """Serializer validator: raises a typed ValidationError naming the categories."""
    from rest_framework import serializers

    cats = detector.categories(value)
    if cats:
        raise serializers.ValidationError(
            f"{CONTACT_NOT_ALLOWED} ({', '.join(cats)})", code="contact_information_not_allowed"
        )
    return value
