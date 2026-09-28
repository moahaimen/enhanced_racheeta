"""The committed OpenAPI contract describes the marketplace endpoints with the
shapes the API actually returns (paginated collections, nullable price, the
backend-computed dashboard, and a write schema without targeting fields)."""

from pathlib import Path

import pytest
import yaml

SCHEMA = yaml.safe_load(
    Path(__file__).resolve().parents[4].joinpath("docs/api/openapi.yaml").read_text()
)


def _ok_ref(path, method="get"):
    content = SCHEMA["paths"][path][method]["responses"]
    code = "200" if "200" in content else "201"
    return content[code]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]


def _component(name):
    return SCHEMA["components"]["schemas"][name]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/marketplace/products",
        "/api/v1/marketplace/company/products",
        "/api/v1/admin/marketplace/companies",
    ],
)
def test_collections_are_paginated(path):
    props = _component(_ok_ref(path))["properties"]
    assert {"count", "next", "previous", "results"} <= set(props)


def test_product_price_is_nullable_and_dashboard_is_backend_computed():
    assert _component("ProductPublic")["properties"]["price"]["nullable"] is True
    dashboard = _component(_ok_ref("/api/v1/marketplace/company/dashboard"))["properties"]
    assert {
        "verification_status",
        "can_publish",
        "products_total",
        "products_active",
        "products_inactive",
        "products_exposable",
    } <= set(dashboard)


def test_the_product_write_schema_carries_no_targeting_or_state():
    props = set(_component("ProductWriteRequest")["properties"])
    assert props == {"category", "title", "description", "brand", "model_name", "price", "currency"}


def test_detail_endpoint_is_documented():
    assert _ok_ref("/api/v1/marketplace/products/{id}") == "ProductPublic"
