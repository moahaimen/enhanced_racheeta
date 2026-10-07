"""The public property catalogue must not issue queries per listing (docs/PERFORMANCE.md)."""

import pytest

from tests.querycount import assert_flat, queries_for

from .conftest import PUBLIC_LISTINGS


@pytest.mark.django_db
def test_public_catalogue_query_count_does_not_grow_with_rows(published):
    from rest_framework.test import APIClient

    client = APIClient()
    for _ in range(3):
        published()
    small, body = queries_for(client, PUBLIC_LISTINGS)
    assert body["count"] == 3

    for _ in range(12):
        published()
    large, body = queries_for(client, PUBLIC_LISTINGS)
    assert body["count"] == 15
    assert_flat(small, large, label=f"GET {PUBLIC_LISTINGS}")


@pytest.mark.django_db
def test_public_catalogue_is_paginated_and_bounded(published):
    from rest_framework.test import APIClient

    for _ in range(25):
        published()
    _, body = queries_for(APIClient(), PUBLIC_LISTINGS)
    assert body["count"] == 25
    assert len(body["results"]) == 20
    assert body["next"]
