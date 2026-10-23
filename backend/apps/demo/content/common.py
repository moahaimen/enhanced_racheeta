"""Shared constants for the demo dataset. Every person, organisation and place of business here is
FICTIONAL; the Iraqi governorates/cities are the platform's real reference data."""

EMAIL_DOMAIN = "demo.racheeta.invalid"  # reserved TLD: can never be a deliverable address
DEMO_NOTE_AR = "ملف توضيحي لأغراض العرض فقط."
DEMO_NOTE_EN = "Demonstration profile — fictional data for presentation only."


def email(key: str) -> str:
    return f"{key}@{EMAIL_DOMAIN}"


def phone(n: int) -> str:
    return f"0700 000 {n:04d}"


def bilingual(ar: str, en: str) -> str:
    return f"{ar} | {en}"


def about(ar: str, en: str) -> str:
    return f"{ar}\n\n{en}\n\n{DEMO_NOTE_AR} {DEMO_NOTE_EN}"
