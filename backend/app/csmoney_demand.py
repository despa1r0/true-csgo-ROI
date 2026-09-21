"""Observed sales signals for scheduling CS.MONEY variant refreshes.

The detail cache only contains variants requested elsewhere in the application.
The background probe gradually fills gaps through CSGO Market public history.
Counts here are observations, not a complete market-wide ranking.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .database import get_connection


SALES_WINDOW = timedelta(days=7)
DEFAULT_CACHE_MAX_AGE = timedelta(days=1)
MIN_RECHECK_INTERVAL = timedelta(days=1)


def get_observed_sales_priorities(
    limit: int = 200,
    *,
    now: datetime | None = None,
    max_cache_age: timedelta = DEFAULT_CACHE_MAX_AGE,
) -> list[dict[str, Any]]:
    """Rank cached variants by observed sales during the previous seven days.

    CSFloat is preferred when its fresh sample contains an in-window sale. If it
    has no usable in-window observation, a fresh CSGO Market sample is used.
    This function performs one database read and makes no external API calls.
    Missing variants are omitted rather than interpreted as zero-demand items.
    """
    if limit <= 0:
        return []
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT v.id AS variant_id, v.market_hash_name,
                   cf.sales AS csfloat_sales,
                   cf.sales_error AS csfloat_sales_error,
                   COALESCE(cf.sales_fetched_at, cf.fetched_at) AS csfloat_fetched_at,
                   cm.sales AS csgomarket_sales,
                   cm.sales_error AS csgomarket_sales_error,
                   COALESCE(cm.sales_fetched_at, cm.fetched_at) AS csgomarket_fetched_at,
                   ds.sales_source AS signal_source,
                   ds.sales_count_7d AS signal_count,
                   ds.status AS signal_status,
                   ds.checked_at AS signal_checked_at
            FROM skin_variants v
            LEFT JOIN marketplace_variant_details cf
              ON cf.variant_id = v.id AND cf.marketplace = 'CSFloat'
            LEFT JOIN marketplace_variant_details cm
              ON cm.variant_id = v.id AND cm.marketplace = 'CSGO Market'
            LEFT JOIN csmoney_demand_signals ds ON ds.variant_id = v.id
            WHERE v.market_hash_name IS NOT NULL
              AND v.market_hash_name <> ''
              AND (cf.variant_id IS NOT NULL OR cm.variant_id IS NOT NULL
                   OR ds.variant_id IS NOT NULL)
            """
        ).fetchall()
    return rank_cached_sales(rows, limit=limit, now=now, max_cache_age=max_cache_age)


def refresh_missing_demand_signals(
    *,
    batch_size: int = 20,
    max_requests: int = 5,
    now: datetime | None = None,
) -> dict[str, int]:
    """Gradually inspect unmeasured variants, with at most ``max_requests`` HTTP calls.

    Run this once per scheduling cycle, outside the request path. Every inspected
    variant is timestamped, including empty responses and errors, so the same
    variant is not requested again for at least a day. Positive counts are
    observations; null counts mean unknown demand, never zero demand.
    """
    if batch_size <= 0 or max_requests < 0:
        raise ValueError("batch_size must be positive and max_requests non-negative")
    checked_at = _normalize_now(now)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT v.id AS variant_id, v.market_hash_name,
                   cf.sales AS csfloat_sales,
                   cf.sales_error AS csfloat_sales_error,
                   COALESCE(cf.sales_fetched_at, cf.fetched_at) AS csfloat_fetched_at,
                   cm.sales AS csgomarket_sales,
                   cm.sales_error AS csgomarket_sales_error,
                   COALESCE(cm.sales_fetched_at, cm.fetched_at) AS csgomarket_fetched_at
            FROM skin_variants v
            LEFT JOIN marketplace_variant_details cf
              ON cf.variant_id = v.id AND cf.marketplace = 'CSFloat'
            LEFT JOIN marketplace_variant_details cm
              ON cm.variant_id = v.id AND cm.marketplace = 'CSGO Market'
            LEFT JOIN csmoney_demand_signals ds ON ds.variant_id = v.id
            WHERE v.market_hash_name IS NOT NULL
              AND v.market_hash_name <> ''
              AND (ds.checked_at IS NULL OR ds.checked_at <= %s)
            ORDER BY ds.checked_at NULLS FIRST, v.id
            LIMIT %s
            """,
            (checked_at - MIN_RECHECK_INTERVAL, batch_size),
        ).fetchall()

    stats = {"checked": 0, "requests": 0, "observed": 0, "unobserved": 0, "errors": 0}
    for row in rows:
        cached = rank_cached_sales([row], limit=1, now=checked_at)
        if cached:
            signal = cached[0]
            status, source, count, error = (
                "observed", signal["sales_source"], signal["sales_count_7d"], None
            )
        else:
            if stats["requests"] >= max_requests:
                break
            stats["requests"] += 1
            status, source, count, error = _fetch_csgomarket_signal(
                row["market_hash_name"], checked_at
            )
        _save_signal(row["variant_id"], source, count, status, error, checked_at)
        stats["checked"] += 1
        stats[status if status != "error" else "errors"] += 1
    return stats


def get_targeted_sales_priority(
    variant_id: str,
    *,
    now: datetime | None = None,
    max_cache_age: timedelta = DEFAULT_CACHE_MAX_AGE,
    fetch_csgomarket_on_miss: bool = False,
) -> dict[str, Any] | None:
    """Get one variant's signal, optionally trying one CSGO Market history call.

    The network fallback is meant for a specifically requested variant. It is
    deliberately opt-in and shares the daily probe timestamp with the crawler.
    """
    if not variant_id:
        return None
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT v.id AS variant_id, v.market_hash_name,
                   cf.sales AS csfloat_sales,
                   cf.sales_error AS csfloat_sales_error,
                   COALESCE(cf.sales_fetched_at, cf.fetched_at) AS csfloat_fetched_at,
                   cm.sales AS csgomarket_sales,
                   cm.sales_error AS csgomarket_sales_error,
                   COALESCE(cm.sales_fetched_at, cm.fetched_at) AS csgomarket_fetched_at,
                   ds.sales_source AS signal_source,
                   ds.sales_count_7d AS signal_count,
                   ds.status AS signal_status,
                   ds.checked_at AS signal_checked_at
            FROM skin_variants v
            LEFT JOIN marketplace_variant_details cf
              ON cf.variant_id = v.id AND cf.marketplace = 'CSFloat'
            LEFT JOIN marketplace_variant_details cm
              ON cm.variant_id = v.id AND cm.marketplace = 'CSGO Market'
            LEFT JOIN csmoney_demand_signals ds ON ds.variant_id = v.id
            WHERE v.id = %s
            """,
            (variant_id,),
        ).fetchone()
    if row is None:
        return None
    observed = rank_cached_sales([row], limit=1, now=now, max_cache_age=max_cache_age)
    if observed:
        return observed[0]
    if not fetch_csgomarket_on_miss:
        return None
    checked_at = _normalize_now(now)
    last_checked = _aware_datetime(row.get("signal_checked_at"))
    if last_checked is not None and checked_at - last_checked < MIN_RECHECK_INTERVAL:
        return None
    name = row.get("market_hash_name")
    if not isinstance(name, str) or not name:
        return None
    status, source, count, error = _fetch_csgomarket_signal(name, checked_at)
    _save_signal(variant_id, source, count, status, error, checked_at)
    if status != "observed":
        return None
    return {
        "variant_id": variant_id,
        "market_hash_name": name,
        "sales_count_7d": count,
        "sales_source": source,
    }


def rank_cached_sales(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int = 200,
    now: datetime | None = None,
    max_cache_age: timedelta = DEFAULT_CACHE_MAX_AGE,
) -> list[dict[str, Any]]:
    """Pure ranking step for database rows, exposed for deterministic tests."""
    if limit <= 0:
        return []
    if max_cache_age <= timedelta(0):
        raise ValueError("max_cache_age must be positive")
    now = _normalize_now(now)

    priorities: list[dict[str, Any]] = []
    for row in rows:
        variant_id = row.get("variant_id")
        name = row.get("market_hash_name")
        if not isinstance(variant_id, str) or not isinstance(name, str) or not name:
            continue
        for prefix, source in (("csfloat", "CSFloat"), ("csgomarket", "CSGO Market")):
            if row.get(f"{prefix}_sales_error"):
                continue
            fetched_at = _aware_datetime(row.get(f"{prefix}_fetched_at"))
            if fetched_at is None or fetched_at > now or now - fetched_at > max_cache_age:
                continue
            sales = row.get(f"{prefix}_sales")
            count = _count_recent_sales(sales, now)
            if count:
                priorities.append(
                    {
                        "variant_id": variant_id,
                        "market_hash_name": name,
                        "sales_count_7d": count,
                        "sales_source": source,
                    }
                )
                break
        else:
            checked_at = _aware_datetime(row.get("signal_checked_at"))
            count = row.get("signal_count")
            source = row.get("signal_source")
            if (
                row.get("signal_status") == "observed"
                and checked_at is not None
                and checked_at <= now
                and now - checked_at <= max_cache_age
                and isinstance(count, int)
                and count > 0
                and source in ("CSFloat", "CSGO Market")
            ):
                priorities.append(
                    {
                        "variant_id": variant_id,
                        "market_hash_name": name,
                        "sales_count_7d": count,
                        "sales_source": source,
                    }
                )
    priorities.sort(
        key=lambda entry: (
            -entry["sales_count_7d"],
            entry["sales_source"] != "CSFloat",
            entry["market_hash_name"],
            entry["variant_id"],
        )
    )
    return priorities[:limit]


def _count_recent_sales(sales: object, now: datetime) -> int:
    if not isinstance(sales, list):
        return 0
    since = now - SALES_WINDOW
    count = 0
    for sale in sales:
        if not isinstance(sale, dict):
            continue
        sold_at = _aware_datetime(sale.get("sold_at"))
        if sold_at is not None and since <= sold_at <= now:
            count += 1
    return count


def _fetch_csgomarket_signal(
    market_hash_name: str, now: datetime
) -> tuple[str, str, int | None, str | None]:
    from .csgomarket import CsgoMarketRequestError, get_sales_history

    try:
        sales = get_sales_history(market_hash_name, limit=200)
    except CsgoMarketRequestError as error:
        return "error", "CSGO Market", None, str(error)
    count = _count_recent_sales(sales, now)
    if not count:
        return "unobserved", "CSGO Market", None, None
    return "observed", "CSGO Market", count, None


def _save_signal(
    variant_id: str,
    source: str,
    count: int | None,
    status: str,
    error: str | None,
    checked_at: datetime,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO csmoney_demand_signals (
                variant_id, sales_source, sales_count_7d, status, last_error, checked_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (variant_id) DO UPDATE SET
                sales_source = EXCLUDED.sales_source,
                sales_count_7d = EXCLUDED.sales_count_7d,
                status = EXCLUDED.status,
                last_error = EXCLUDED.last_error,
                checked_at = EXCLUDED.checked_at
            """,
            (variant_id, source, count, status, error, checked_at),
        )


def _normalize_now(now: datetime | None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _aware_datetime(value: object) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)
