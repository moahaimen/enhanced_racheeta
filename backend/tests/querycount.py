"""Helpers for the query-scaling tests (docs/PERFORMANCE.md).

These assert that the NUMBER of SQL statements an endpoint issues does not grow with the number of
rows it returns (the N+1 pattern). They never measure wall-clock time, so they are stable on a
shared CI runner.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext


def queries_for(client, url: str, *, expect_status: int = 200) -> tuple[int, dict]:
    """GET `url`, returning (number of SQL statements, decoded JSON body)."""
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    assert response.status_code == expect_status, response.content
    return len(captured), response.json()


def assert_flat(small: int, large: int, *, label: str) -> None:
    assert large <= small, (
        f"{label}: {small} queries for the small data set but {large} for the large one — "
        "the endpoint issues queries per row (N+1). Use select_related/prefetch_related."
    )
