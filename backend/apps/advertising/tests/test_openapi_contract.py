"""The committed OpenAPI file is the contract for advertising: lifecycle, quote and
payment fields are read-only, companies cannot send money or state, the admin
decision schemas accept no amount, and owner/admin/provider views are separate."""

from pathlib import Path

import pytest
import yaml

from apps.advertising.types import CampaignStatus, PaymentStatus
from apps.providers.types import ProviderType

SCHEMA = yaml.safe_load(
    Path(__file__).resolve().parents[4].joinpath("docs/api/openapi.yaml").read_text()
)
COMPANY = "/api/v1/advertising/company"
ADMIN = "/api/v1/admin/advertising/campaigns"
SPONSORED = "/api/v1/advertising/marketplace"


def _c(name):
    return SCHEMA["components"]["schemas"][name]


def _ok_ref(path, method="get"):
    responses = SCHEMA["paths"][path][method]["responses"]
    code = "200" if "200" in responses else "201"
    return responses[code]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]


def _params(path):
    return {p["name"] for p in SCHEMA["paths"][path]["get"].get("parameters", [])}


def test_every_endpoint_is_described_with_its_methods():
    expected = {
        f"{COMPANY}/dashboard": {"get"},
        f"{COMPANY}/quote": {"post"},
        f"{COMPANY}/campaigns": {"get", "post"},
        f"{COMPANY}/campaigns/{{id}}": {"get", "patch"},  # no DELETE
        f"{COMPANY}/campaigns/{{id}}/submit": {"post"},
        f"{COMPANY}/campaigns/{{id}}/cancel": {"post"},
        SPONSORED: {"get"},
        ADMIN: {"get"},
        f"{ADMIN}/{{id}}": {"get"},
        f"{ADMIN}/{{id}}/verify-payment": {"post"},
        f"{ADMIN}/{{id}}/reject-payment": {"post"},
    }
    for path, methods in expected.items():
        assert {m for m in SCHEMA["paths"][path] if m != "parameters"} == methods, path


@pytest.mark.parametrize("path", [f"{COMPANY}/campaigns", SPONSORED, ADMIN])
def test_collections_are_paginated(path):
    assert {"count", "next", "previous", "results"} <= set(_c(_ok_ref(path))["properties"])


@pytest.mark.parametrize("name", ["CampaignOwner", "CampaignAdmin", "SponsoredCampaign"])
def test_server_representations_are_entirely_read_only(name):
    assert all(p.get("readOnly") for p in _c(name)["properties"].values()), name


def test_quote_snapshot_and_payment_are_read_only_and_nullable_on_the_campaign():
    props = _c("CampaignOwner")["properties"]
    assert props["quote"]["nullable"] is True and props["payment"]["nullable"] is True
    assert _c("QuoteSnapshot")["properties"].keys() == {
        "days", "daily_rate", "amount", "currency", "quoted_at",
    }  # fmt: skip
    assert set(_c("OwnerPayment")["properties"]) == {
        "status", "amount", "currency", "method", "reference", "created_at", "verified_at",
    }  # fmt: skip
    assert "admin_note" not in _c("OwnerPayment")["properties"]
    assert "admin_note" in _c("AdminPayment")["properties"]


def test_the_write_schemas_accept_only_owner_editable_data():
    editable = {
        "name",
        "product",
        "starts_on",
        "ends_on",
        "provider_types",
        "specialties",
        "governorates",
    }
    for name in ("CampaignWriteRequest", "PatchedCampaignWriteRequest"):
        assert set(_c(name)["properties"]) == editable, name
    assert set(_c("CampaignWriteRequest")["required"]) == {"name", "product"}
    for forbidden in (
        "status",
        "amount",
        "quoted_amount",
        "payment",
        "company",
        "is_paid",
        "currency",
    ):
        assert forbidden not in _c("CampaignWriteRequest")["properties"]


def test_the_admin_decision_schemas_take_no_amount_or_state():
    assert set(_c("PaymentVerificationRequest")["properties"]) == {"method", "reference", "note"}
    assert set(_c("PaymentVerificationRequest")["required"]) == {"method"}
    assert set(_c("PaymentRejectionRequest")["properties"]) == {"reason"}
    for name in ("PaymentVerificationRequest", "PaymentRejectionRequest"):
        assert not {"amount", "currency", "status", "company", "product"} & set(
            _c(name)["properties"]
        )


def test_the_quote_schemas():
    assert set(_c("QuoteDatesRequest")["properties"]) == {"starts_on", "ends_on"}
    assert set(_c("QuoteDatesRequest")["required"]) == {"starts_on", "ends_on"}
    assert set(_c(_ok_ref(f"{COMPANY}/quote", "post"))["properties"]) == {
        "days", "daily_rate", "total", "currency",
    }  # fmt: skip


def test_the_provider_ad_carries_no_commercial_field():
    props = set(_c("SponsoredCampaign")["properties"])
    assert props == {"id", "sponsored", "starts_on", "ends_on", "product"}
    assert _c("SponsoredCampaign")["properties"]["sponsored"]["type"] == "boolean"


def test_enums_are_controlled_vocabularies():
    assert _c("CampaignStatusEnum")["enum"] == sorted(CampaignStatus.values) or set(
        _c("CampaignStatusEnum")["enum"]
    ) == set(CampaignStatus.values)
    assert set(_c("CampaignPaymentStatusEnum")["enum"]) == set(PaymentStatus.values)
    assert set(_c("ProviderTypeEnum")["enum"]) == set(ProviderType.values)


def test_lists_document_only_the_filters_they_really_support():
    assert _params(SPONSORED) == {"page", "page_size"}  # the backend alone decides targeting
    assert "status" in _params(f"{COMPANY}/campaigns")
    assert {"status", "company", "payment_status"} <= _params(ADMIN)
