"""Serialization building blocks of the workspace dashboard payload (stats, items, modules)."""

from __future__ import annotations

LIST_LIMIT = 5
LOW_STOCK = 5


# ---- building blocks --------------------------------------------------------------------------


def _stat(key: str, value) -> dict:
    return {"key": key, "value": value}


def _item(id, title, subtitle="", status="", status_group="", path="") -> dict:
    return {
        "id": str(id),
        "title": title,
        "subtitle": subtitle,
        "status": status,
        "status_group": status_group,
        "path": path,
    }


def _module(key, *, variant="", stats=(), items=(), link="") -> dict:
    return {
        "key": key,
        "variant": variant,
        "stats": list(stats),
        "items": list(items),
        "link": link,
    }


def _money(value, currency) -> str:
    return "" if value is None else f"{value:,.0f} {currency}"


# ---- shared modules ---------------------------------------------------------------------------
