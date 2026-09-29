"""Phase 6 acceptance review (commit 4087175): categories expose `can_publish`
— an active category with at least one active audience rule — as read-only,
backend-derived reference state (annotated in SQL, one statement per page), so
the company UI offers Publish only where the publication gate can succeed. The
gate itself (services._locked_publishable_category) stays authoritative."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.marketplace.models import ProductAudience, ProductCategory
from apps.providers.types import ProviderType

from .conftest import client_for

pytestmark = pytest.mark.django_db
CATEGORIES = "/api/v1/marketplace/categories"
COMPANY_PRODUCTS = "/api/v1/marketplace/company/products"
CATALOG = "/api/v1/marketplace/products"


def _rows():
    return {row["slug"]: row for row in APIClient().get(CATEGORIES).json()}


def test_category_with_an_active_audience_can_publish(category_factory):
    category_factory(slug="ready", rules=[(ProviderType.DOCTOR, None)])
    assert _rows()["ready"]["can_publish"] is True


def test_category_without_audiences_cannot_publish(category_factory):
    category_factory(slug="empty")
    assert _rows()["empty"]["can_publish"] is False


def test_category_with_only_inactive_audiences_cannot_publish(category_factory, dentistry):
    category = category_factory(slug="paused", rules=[("", dentistry)])
    category.audiences.update(is_active=False)
    assert _rows()["paused"]["can_publish"] is False
    ProductAudience.objects.filter(category=category).update(is_active=True)
    assert _rows()["paused"]["can_publish"] is True  # derived at read time, no caching


def test_endpoint_stays_active_categories_only(category_factory):
    category_factory(slug="shown", rules=[(ProviderType.DOCTOR, None)])
    category_factory(slug="hidden", is_active=False, rules=[(ProviderType.DOCTOR, None)])
    assert set(_rows()) == {"shown"}


def test_no_client_write_path_sets_can_publish(category_factory, company_factory):
    category = category_factory(slug="empty")
    assert APIClient().post(CATEGORIES, {"can_publish": True}).status_code in (401, 405)
    client = client_for(company_factory().account)
    resp = client.post(
        COMPANY_PRODUCTS,
        {"category": str(category.pk), "title": "Chair", "can_publish": True},
        format="json",
    )
    assert resp.status_code == 201, resp.json()  # unknown key ignored, never applied
    assert resp.json()["category"]["can_publish"] is False
    assert not hasattr(ProductCategory.objects.get(pk=category.pk), "can_publish")


def test_publishability_is_one_statement_regardless_of_category_count(category_factory):
    for i in range(3):
        category_factory(slug=f"c{i}", rules=[(ProviderType.DOCTOR, None)] if i else [])
    with CaptureQueriesContext(connection) as few:
        APIClient().get(CATEGORIES)
    for i in range(3, 9):
        category_factory(slug=f"c{i}")
    with CaptureQueriesContext(connection) as many:
        rows = APIClient().get(CATEGORIES).json()
    assert len(rows) == 9 and len(few) == len(many) == 1
    assert "EXISTS" in many.captured_queries[0]["sql"].upper()


def test_nested_category_carries_publishability_without_per_row_queries(
    company_factory, category_factory, product_factory
):
    company = company_factory()
    ready = category_factory(slug="ready", rules=[(ProviderType.DOCTOR, None)])
    empty = category_factory(slug="empty")
    product_factory(company, ready, is_active=False)
    product_factory(company, empty, is_active=False)
    client = client_for(company.account)
    with CaptureQueriesContext(connection) as two:
        by_slug = {
            row["category"]["slug"]: row["category"]["can_publish"]
            for row in client.get(COMPANY_PRODUCTS).json()["results"]
        }
    assert by_slug == {"ready": True, "empty": False}
    for _ in range(6):
        product_factory(company, empty, is_active=False)
    with CaptureQueriesContext(connection) as eight:
        assert client.get(COMPANY_PRODUCTS).json()["count"] == 8
    assert len(two) == len(eight)


def test_targeted_catalogue_categories_are_publishable_by_construction(
    company_factory, category_factory, product_factory, provider_factory
):
    product = product_factory(
        company_factory(), category_factory(rules=[(ProviderType.LABORATORY, None)])
    )
    client = client_for(provider_factory(provider_type=ProviderType.LABORATORY).account)
    assert client.get(CATALOG).json()["results"][0]["category"]["can_publish"] is True
    assert client.get(f"{CATALOG}/{product.pk}").json()["category"]["can_publish"] is True
