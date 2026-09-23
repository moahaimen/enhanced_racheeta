import pytest

from apps.moderation.contact_leak import detector, normalize


@pytest.mark.parametrize(
    "text,category",
    [
        ("Call 07701234567 now", "PHONE"),
        ("Call 0770 123 4567 now", "PHONE"),
        ("اتصل على ٠٧٧٠١٢٣٤٥٦٧", "PHONE"),
        ("+964 770 123 4567", "PHONE"),
        ("00964-770-123-4567", "PHONE"),
        ("(0770) 123-4567", "PHONE"),
        ("send CV to person@example.com", "EMAIL"),
        ("mail me at person (at) example (dot) com", "EMAIL"),
        ("wa.me/9647701234567", "WHATSAPP"),
        ("WhatsApp us", "WHATSAPP"),
        ("راسلنا واتساب", "WHATSAPP"),
        ("t.me/recruiter", "TELEGRAM"),
        ("تلغرام: recruiter", "TELEGRAM"),
        ("visit https://jobs.example.com/apply", "URL"),
        ("visit www.example.com", "URL"),
        ("our site example.com/careers", "URL"),
    ],
)
def test_detects_contact_channels(text, category):
    assert category in detector.categories(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Salary 1,500,000 IQD per month",
        "Graduated 2018, 5 years of experience",
        "2020-2024 worked in Baghdad Teaching Hospital",
        "ICU with 24 beds and 12 nurses per shift",
        "Shift from 08:00 to 16:00",
        "خبرة ٥ سنوات، راتب ١٢٠٠٠٠٠ دينار",
        "Licence issued 2019 by the Ministry of Health",
    ],
)
def test_ordinary_text_is_not_blocked(text):
    assert detector.categories(text) == []


def test_normalize_collapses_separators_and_digits():
    assert normalize("٠٧٧٠ ١٢٣-٤٥٦٧") == "07701234567"
    assert normalize("+964 (770) 123 4567") == "+9647701234567"


def test_findings_explain_category_and_excerpt():
    findings = detector.scan("Email a@b.com or call 07701234567")
    assert {f.category for f in findings} == {"EMAIL", "PHONE"}
    assert any(f.excerpt == "a@b.com" for f in findings)
