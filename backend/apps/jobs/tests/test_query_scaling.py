"""The public jobs list must not issue queries per job (docs/PERFORMANCE.md)."""

import pytest

from tests.querycount import assert_flat, queries_for

LIST = "/api/v1/jobs"


@pytest.mark.django_db
def test_public_job_list_query_count_does_not_grow_with_rows(
    api_client, employer_factory, job_factory
):
    employers = [employer_factory(name=f"Hospital {i}") for i in range(2)]
    for i in range(3):
        job_factory(employers[i % 2])
    small, body = queries_for(api_client, LIST)
    assert body["count"] == 3

    for i in range(12):
        job_factory(employers[i % 2])
    large, body = queries_for(api_client, LIST)
    assert body["count"] == 15
    assert_flat(small, large, label="GET /api/v1/jobs")


@pytest.mark.django_db
def test_public_job_list_is_paginated_and_bounded(api_client, employer, job_factory):
    for _ in range(25):
        job_factory(employer)
    _, body = queries_for(api_client, LIST)
    assert body["count"] == 25
    assert len(body["results"]) == 20  # StandardPagination PAGE_SIZE, never the whole table
    assert body["next"]
