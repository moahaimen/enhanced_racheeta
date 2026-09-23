import pytest
from rest_framework import serializers

from apps.moderation.contact_leak import validate_no_contact_info


def test_validator_raises_typed_error():
    with pytest.raises(serializers.ValidationError) as excinfo:
        validate_no_contact_info("call 07701234567")
    detail = excinfo.value.detail[0]
    assert detail.code == "contact_information_not_allowed"
    assert "PHONE" in str(detail)


def test_validator_passes_clean_text():
    assert (
        validate_no_contact_info("Registered nurse, 5 years ICU") == "Registered nurse, 5 years ICU"
    )
