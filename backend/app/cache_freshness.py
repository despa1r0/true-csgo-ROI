"""Shared freshness semantics for independently refreshed detail components."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


DETAIL_COMPONENTS = ("listings", "sales", "buy_orders")


def annotate_component_freshness(
    detail: dict[str, Any],
    *,
    ttl_seconds: int,
    minimum_version: int,
    components: Iterable[str] = DETAIL_COMPONENTS,
) -> dict[str, Any]:
    """Add freshness booleans using the database clock captured by the query."""
    component_names = tuple(components)
    checked_at = detail.pop("checked_at", None) or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    fresh_after = checked_at - timedelta(seconds=ttl_seconds)
    version_is_current = int(detail.get("details_version") or 0) >= minimum_version

    for component in component_names:
        fetched_at = detail.get(f"{component}_fetched_at")
        error = detail.get(f"{component}_error")
        detail[f"{component}_is_fresh"] = bool(
            version_is_current
            and fetched_at is not None
            and fetched_at.tzinfo is not None
            and fetched_at >= fresh_after
            and not error
        )
    detail["is_fresh"] = all(
        detail[f"{component}_is_fresh"] for component in component_names
    )
    return detail


def refreshed_component_timestamps(
    cached: dict[str, Any] | None,
    *,
    errors: dict[str, str | None],
    successful_at: datetime,
) -> dict[str, datetime | None]:
    """Advance only components whose provider request actually succeeded."""
    return {
        f"{component}_fetched_at": (
            successful_at
            if errors.get(component) is None
            else cached.get(f"{component}_fetched_at") if cached else None
        )
        for component in DETAIL_COMPONENTS
    }


def public_component_states(detail: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return additive, machine-readable component state for API consumers."""
    result: dict[str, dict[str, Any]] = {}
    for component in DETAIL_COMPONENTS:
        fetched_at = detail.get(f"{component}_fetched_at")
        error = detail.get(f"{component}_error")
        is_fresh = detail.get(f"{component}_is_fresh")
        if is_fresh is None:
            is_fresh = fetched_at is not None and not error
        status = "fresh" if is_fresh else "stale" if fetched_at is not None else "unavailable"
        result[component] = {
            "status": status,
            "fetched_at": fetched_at,
            "error": error,
        }
    return result
