"""The committed OpenAPI file is the contract: every real-estate endpoint is
described with the shapes the API actually returns, enums are controlled, server
fields are read-only, and the write schemas carry no lifecycle or ownership."""

from pathlib import Path

import pytest
import yaml

from apps.real_estate.filters import ORDERINGS
from apps.real_estate.types import (
    ContactMethod,
    PropertyType,
    PublicationStatus,
    SellerType,
    SuitableUse,
    TransactionType,
)

SCHEMA = yaml.safe_load(
    Path(__file__).resolve().parents[4].joinpath("docs/api/openapi.yaml").read_text()
)
BASE = "/api/v1/real-estate"


def _component(name):
    return SCHEMA["components"]["schemas"][name]


def _ok_ref(path, method="get"):
    responses = SCHEMA["paths"][path][method]["responses"]
    code = "200" if "200" in responses else "201"
    return responses[code]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]


def _ref_name(prop):
    ref = prop.get("$ref") or prop["allOf"][0]["$ref"]
    return ref.rsplit("/", 1)[-1]


def test_every_endpoint_is_described_with_its_methods():
    expected = {
        f"{BASE}/listings": {"get"},
        f"{BASE}/listings/{{id}}": {"get"},
        f"{BASE}/owner": {"get", "post", "patch"},
        f"{BASE}/owner/dashboard": {"get"},
        f"{BASE}/owner/listings": {"get", "post"},
        f"{BASE}/owner/listings/{{id}}": {"get", "patch"},  # no DELETE: history is kept
        f"{BASE}/owner/listings/{{id}}/publish": {"post"},
        f"{BASE}/owner/listings/{{id}}/unpublish": {"post"},
    }
    for path, methods in expected.items():
        assert {m for m in SCHEMA["paths"][path] if m != "parameters"} == methods, path


@pytest.mark.parametrize("path", [f"{BASE}/listings", f"{BASE}/owner/listings"])
def test_collections_are_paginated(path):
    assert {"count", "next", "previous", "results"} <= set(_component(_ok_ref(path))["properties"])


def test_public_and_owner_representations_are_not_conflated():
    public = set(_component("PropertyListingPublic")["properties"])
    owner = set(_component("PropertyListingOwner")["properties"])
    assert (
        "seller" in public and {"publication_status", "is_public", "is_expired"} & public == set()
    )
    assert {"publication_status", "is_public", "is_expired"} <= owner and "seller" not in owner
    for forbidden in ("account", "account_id", "email", "is_staff", "role"):
        assert forbidden not in public | owner
    assert set(_component("SellerSummary")["properties"]) == {"id", "display_name", "seller_type"}


@pytest.mark.parametrize("name", ["PropertyListingPublic", "PropertyListingOwner", "SellerOwner"])
def test_server_representations_are_entirely_read_only(name):
    assert all(p.get("readOnly") for p in _component(name)["properties"].values()), name


def test_price_and_coordinates_are_nullable():
    for name in ("PropertyListingPublic", "PropertyListingOwner", "PropertyListingWriteRequest"):
        props = _component(name)["properties"]
        for field in ("price", "latitude", "longitude", "area_sqm"):
            assert props[field]["nullable"] is True, (name, field)


@pytest.mark.parametrize(
    "schema,field,enum",
    [
        ("PropertyTypeEnum", None, PropertyType),
        ("TransactionTypeEnum", None, TransactionType),
        ("SuitableUseEnum", None, SuitableUse),
        ("ContactMethodEnum", None, ContactMethod),
        ("PublicationStatusEnum", None, PublicationStatus),
        ("SellerTypeEnum", None, SellerType),
    ],
)
def test_enums_are_controlled_vocabularies(schema, field, enum):
    assert _component(schema)["enum"] == enum.values


def test_listing_fields_use_the_shared_enums():
    write = _component("PropertyListingWriteRequest")["properties"]
    assert _ref_name(write["property_type"]) == "PropertyTypeEnum"
    assert _ref_name(write["transaction_type"]) == "TransactionTypeEnum"
    assert _ref_name(write["contact_method"]) == "ContactMethodEnum"
    assert write["suitable_uses"]["items"]["$ref"].endswith("/SuitableUseEnum")
    owner = _component("PropertyListingOwner")["properties"]
    assert _ref_name(owner["publication_status"]) == "PublicationStatusEnum"


def test_write_schemas_accept_only_owner_editable_data():
    editable = {
        "title", "description", "property_type", "transaction_type", "governorate", "city",
        "district", "latitude", "longitude", "area_sqm", "price", "currency", "facilities",
        "contact_method", "contact_phone", "contact_email", "expires_at", "suitable_uses",
    }  # fmt: skip
    for name in ("PropertyListingWriteRequest", "PatchedPropertyListingWriteRequest"):
        assert set(_component(name)["properties"]) == editable, name
    assert set(_component("PropertyListingWriteRequest")["required"]) == {
        "title", "property_type", "transaction_type", "governorate",
    }  # fmt: skip
    seller = {"seller_type", "display_name", "about", "phone", "public_email"}
    assert set(_component("SellerWriteRequest")["properties"]) == seller


def test_dashboard_is_backend_computed():
    props = set(_component(_ok_ref(f"{BASE}/owner/dashboard"))["properties"])
    assert props == {
        "listings_total", "listings_draft", "listings_published", "listings_visible",
        "listings_expired", "listings_sale", "listings_rent",
    }  # fmt: skip


def test_public_list_documents_its_filters_and_safe_orderings():
    params = {p["name"]: p for p in SCHEMA["paths"][f"{BASE}/listings"]["get"]["parameters"]}
    assert {
        "transaction_type", "property_type", "governorate", "city", "suitable_use", "min_price",
        "max_price", "min_area", "max_area", "search", "ordering", "page", "page_size",
    } <= set(params)  # fmt: skip
    assert set(params["ordering"]["schema"]["enum"]) == set(ORDERINGS)
    assert "publication_status" not in params  # the public catalogue cannot be asked for drafts
    owner = {p["name"] for p in SCHEMA["paths"][f"{BASE}/owner/listings"]["get"]["parameters"]}
    assert "publication_status" in owner


def test_detail_endpoints_return_the_matching_representation():
    assert _ok_ref(f"{BASE}/listings/{{id}}") == "PropertyListingPublic"
    assert _ok_ref(f"{BASE}/owner/listings/{{id}}") == "PropertyListingOwner"
    assert _ok_ref(f"{BASE}/owner/listings/{{id}}/publish", "post") == "PropertyListingOwner"
    assert _ok_ref(f"{BASE}/owner/listings/{{id}}/unpublish", "post") == "PropertyListingOwner"
