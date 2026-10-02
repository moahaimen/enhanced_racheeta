"""Shared aggregation helpers.

Every dashboard number is one PostgreSQL aggregate over rows that were already scoped to the
caller. Helpers here never see a request: callers pass an already-filtered queryset.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet

# Bounded lists: a dashboard response never grows with the data.
UPCOMING_LIMIT = 5
RECENT_LIMIT = 5


def status_counts(
    queryset: QuerySet,
    field: str,
    values: list[str] | tuple[str, ...],
    **extra: Any,
) -> dict[str, Any]:
    """`{"total", "by_status": {value: n}, **extra}` in ONE query.

    Every status is present (zero-filled) so a client never has to guess what a missing key
    means. `extra` are additional aggregate expressions evaluated in the same statement.
    `.order_by()` clears the model's default ordering, which would otherwise join the GROUP BY.
    """
    aggregates: dict[str, Any] = {"__total": Count("pk")}
    for value in values:
        aggregates[f"__s_{value}"] = Count("pk", filter=Q(**{field: value}))
    aggregates.update(extra)
    row = queryset.order_by().aggregate(**aggregates)
    result: dict[str, Any] = {
        "total": row.pop("__total"),
        "by_status": {value: row.pop(f"__s_{value}") for value in values},
    }
    result.update(row)
    return result
