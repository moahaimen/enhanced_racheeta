import pytest
from django.core.exceptions import ValidationError

from apps.core.phone import normalize_iraqi_phone

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("07701234567", "07701234567"),
        ("0770 123 4567", "07701234567"),
        ("0750-123-4567", "07501234567"),
        ("+964 770 123 4567", "07701234567"),
        ("009647801234567", "07801234567"),
        ("9647901234567", "07901234567"),
        ("01 234 5678", "012345678"),
        ("040 123 4567", "0401234567"),
        ("", ""),
    ],
)
def test_accepted_iraqi_numbers_are_normalized(raw, expected):
    assert normalize_iraqi_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "0770123456",
        "077012345678",
        "07001234567",
        "0770abc4567",
        "+1 202 555 0100",
        "12345",
        "0870000000",
    ],
)
def test_rejected_numbers(raw):
    with pytest.raises(ValidationError):
        normalize_iraqi_phone(raw)


def test_landline_refused_where_a_mobile_is_required():
    with pytest.raises(ValidationError):
        normalize_iraqi_phone("012345678", allow_landline=False)


def test_registration_and_profile_validate_phone_and_name(api_client):
    base = {
        "email": "phone@example.com",
        "password": "Str0ng-Passw0rd!",
        "full_name": "Phone Person",
    }
    bad = api_client.post("/api/v1/auth/register", {**base, "phone_number": "12ab"})
    assert bad.status_code == 400 and "phone_number" in bad.json()["error"]["details"]
    assert (
        api_client.post("/api/v1/auth/register", {**base, "full_name": "12345"}).status_code == 400
    )
    ok = api_client.post("/api/v1/auth/register", {**base, "phone_number": "+964 770 123 4567"})
    assert ok.status_code == 201 and ok.json()["account"]["phone_number"] == "07701234567"
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {ok.json()['tokens']['access']}")
    assert (
        api_client.patch("/api/v1/me", {"phone_number": "0770"}, format="json").status_code == 400
    )
    assert (
        api_client.patch("/api/v1/me", {"phone_number": "0790 111 2233"}, format="json").json()[
            "phone_number"
        ]
        == "07901112233"
    )
