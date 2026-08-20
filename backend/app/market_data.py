"""CSFloat price synchronization backed by PostgreSQL."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from psycopg.types.json import Jsonb

from .csfloat import (
    CsfloatRequestError,
    get_active_listings,
    get_price_index,
    get_sales_history,
)
from .database import get_connection


MARKETPLACE = "CSFloat"
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_DETAILS_TTL_SECONDS = 120
LIQUIDITY_METHOD = (
    "Оценка: число продаж в доступной истории CSFloat / число активных лотов. "
    "Это ориентир, а не гарантия скорости продажи."
)


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def get_csfloat_prices(skin_id: str) -> dict[str, Any]:
    """Synchronize the global index when stale and return one skin's prices."""
    ttl_seconds = _positive_int_env("CSFLOAT_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS)
    variants, cached, sync_is_fresh = _load_skin_cache(skin_id, ttl_seconds)

    if sync_is_fresh:
        return _response(variants, cached, ttl_seconds, cached=True)

    try:
        price_index = get_price_index()
        _store_price_index(price_index)
    except CsfloatRequestError as error:
        return _response(
            variants,
            cached,
            ttl_seconds,
            cached=True,
            stale=True,
            error=str(error),
        )

    fetched_at = datetime.now(timezone.utc)
    fresh_rows = {
        variant["id"]: _index_row(variant, price_index, fetched_at)
        for variant in variants
    }
    return _response(variants, fresh_rows, ttl_seconds, cached=False)


def get_csfloat_variant_details(variant_id: str) -> dict[str, Any] | None:
    """Load ten listings and a sales-based liquidity estimate on demand."""
    ttl_seconds = _positive_int_env(
        "CSFLOAT_DETAILS_TTL_SECONDS", DEFAULT_DETAILS_TTL_SECONDS
    )
    context, cached = _load_variant_detail_cache(variant_id, ttl_seconds)
    if context is None:
        return None
    if cached and cached["is_fresh"]:
        return _detail_response(context, cached, cached=True, stale=False)

    listings: list[dict[str, object]] = []
    listings_error = None
    try:
        listings = get_active_listings(context["market_hash_name"], limit=10)
    except CsfloatRequestError as error:
        listings_error = str(error)

    sales_count = None
    sales_error = None
    try:
        sales_count = len(get_sales_history(context["market_hash_name"]))
    except CsfloatRequestError as error:
        sales_error = str(error)

    stale = False
    if listings_error and cached:
        listings = cached["listings"]
        stale = True

    liquidity_score, liquidity_label = calculate_liquidity(
        sales_count, context.get("active_listings")
    )
    if sales_error and cached:
        sales_count = cached["sales_count"]
        liquidity_score = cached["liquidity_score"]
        liquidity_label = cached["liquidity_label"]
        stale = True

    detail = {
        "sales_count": sales_count,
        "liquidity_score": liquidity_score,
        "liquidity_label": liquidity_label,
        "listings": listings,
        "listings_error": listings_error,
        "sales_error": sales_error,
        "fetched_at": datetime.now(timezone.utc),
    }
    _store_variant_details(variant_id, detail)
    return _detail_response(context, detail, cached=False, stale=stale)


def calculate_liquidity(
    sales_count: int | None, active_listings: int | None
) -> tuple[int | None, str]:
    """Return a transparent beta score from the available CSFloat sample."""
    if sales_count is None or active_listings is None:
        return None, "unavailable"
    score = min(100, round(sales_count / max(active_listings, 1) * 100))
    if score >= 60:
        return score, "high"
    if score >= 20:
        return score, "medium"
    return score, "low"


def _load_variant_detail_cache(
    variant_id: str, ttl_seconds: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    with get_connection() as connection:
        context = connection.execute(
            """
            SELECT v.id AS variant_id, v.market_hash_name, v.name,
                   p.price_cents, p.quantity AS active_listings, p.item_url
            FROM skin_variants v
            LEFT JOIN marketplace_listings p
              ON p.variant_id = v.id AND p.marketplace = %s
            WHERE v.id = %s
            """,
            (MARKETPLACE, variant_id),
        ).fetchone()
        if context is None:
            return None, None
        cached = connection.execute(
            """
            SELECT sales_count, liquidity_score, liquidity_label, listings,
                   listings_error, sales_error, fetched_at,
                   fetched_at >= NOW() - (%s * INTERVAL '1 second') AS is_fresh
            FROM marketplace_variant_details
            WHERE marketplace = %s AND variant_id = %s
            """,
            (ttl_seconds, MARKETPLACE, variant_id),
        ).fetchone()
    return dict(context), dict(cached) if cached else None


def _store_variant_details(variant_id: str, detail: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO marketplace_variant_details (
                marketplace, variant_id, sales_count, liquidity_score,
                liquidity_label, listings, listings_error, sales_error, fetched_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (marketplace, variant_id) DO UPDATE SET
                sales_count = EXCLUDED.sales_count,
                liquidity_score = EXCLUDED.liquidity_score,
                liquidity_label = EXCLUDED.liquidity_label,
                listings = EXCLUDED.listings,
                listings_error = EXCLUDED.listings_error,
                sales_error = EXCLUDED.sales_error,
                fetched_at = NOW()
            """,
            (
                MARKETPLACE,
                variant_id,
                detail["sales_count"],
                detail["liquidity_score"],
                detail["liquidity_label"],
                Jsonb(detail["listings"]),
                detail["listings_error"],
                detail["sales_error"],
            ),
        )


def _detail_response(
    context: dict[str, Any],
    detail: dict[str, Any],
    *,
    cached: bool,
    stale: bool,
) -> dict[str, Any]:
    item_url = context.get("item_url") or (
        f"https://csfloat.com/search?"
        f"{urlencode({'market_hash_name': context['market_hash_name']})}"
    )
    return {
        "marketplace": MARKETPLACE,
        "variant_id": context["variant_id"],
        "market_hash_name": context["market_hash_name"],
        "overview": {
            "price_cents": context.get("price_cents"),
            "active_listings": context.get("active_listings"),
            "item_url": item_url,
        },
        "stats": {
            "sales_count": detail.get("sales_count"),
            "sales_scope": "Доступная история CSFloat",
            "liquidity_score": detail.get("liquidity_score"),
            "liquidity_label": detail.get("liquidity_label") or "unavailable",
            "methodology": LIQUIDITY_METHOD,
        },
        "listings": detail.get("listings") or [],
        "listings_error": detail.get("listings_error"),
        "sales_error": detail.get("sales_error"),
        "fetched_at": detail.get("fetched_at"),
        "cached": cached,
        "stale": stale,
    }


def _load_skin_cache(
    skin_id: str, ttl_seconds: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], bool]:
    with get_connection() as connection:
        variants = list(
            connection.execute(
                """
                SELECT id, market_hash_name
                FROM skin_variants
                WHERE skin_id = %s AND market_hash_name IS NOT NULL
                ORDER BY id
                """,
                (skin_id,),
            ).fetchall()
        )
        cached = {
            row["variant_id"]: row
            for row in connection.execute(
                """
                SELECT variant_id, listing_id, price_cents, item_url, float_value,
                       quantity, is_available, fetched_at
                FROM marketplace_listings
                WHERE marketplace = %s
                  AND variant_id IN (
                      SELECT id FROM skin_variants WHERE skin_id = %s
                  )
                """,
                (MARKETPLACE, skin_id),
            ).fetchall()
        }
        sync = connection.execute(
            """
            SELECT fetched_at >= NOW() - (%s * INTERVAL '1 second') AS is_fresh
            FROM marketplace_syncs
            WHERE marketplace = %s
            """,
            (ttl_seconds, MARKETPLACE),
        ).fetchone()
    return variants, cached, bool(sync and sync["is_fresh"])


def _store_price_index(price_index: dict[str, dict[str, int]]) -> None:
    with get_connection() as connection:
        variants = list(
            connection.execute(
                """
                SELECT id, market_hash_name
                FROM skin_variants
                WHERE market_hash_name IS NOT NULL
                """
            ).fetchall()
        )
        rows = [_index_row(variant, price_index, None) for variant in variants]
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO marketplace_listings (
                    marketplace, variant_id, listing_id, price_cents, item_url,
                    float_value, quantity, is_available, fetched_at
                ) VALUES (
                    %(marketplace)s, %(variant_id)s, NULL, %(price_cents)s,
                    %(item_url)s, NULL, %(quantity)s, %(is_available)s, NOW()
                )
                ON CONFLICT (marketplace, variant_id) DO UPDATE SET
                    listing_id = NULL,
                    price_cents = EXCLUDED.price_cents,
                    item_url = EXCLUDED.item_url,
                    float_value = NULL,
                    quantity = EXCLUDED.quantity,
                    is_available = EXCLUDED.is_available,
                    fetched_at = NOW()
                """,
                rows,
            )
        connection.execute(
            """
            INSERT INTO marketplace_syncs (marketplace, fetched_at)
            VALUES (%s, NOW())
            ON CONFLICT (marketplace) DO UPDATE SET fetched_at = NOW()
            """,
            (MARKETPLACE,),
        )


def _index_row(
    variant: dict[str, Any],
    price_index: dict[str, dict[str, int]],
    fetched_at: datetime | None,
) -> dict[str, Any]:
    market_hash_name = variant["market_hash_name"]
    entry = price_index.get(market_hash_name)
    return {
        "marketplace": MARKETPLACE,
        "variant_id": variant["id"],
        "market_hash_name": market_hash_name,
        "listing_id": None,
        "price_cents": entry["price_cents"] if entry else None,
        "item_url": (
            f"https://csfloat.com/search?{urlencode({'market_hash_name': market_hash_name})}"
            if entry
            else None
        ),
        "float_value": None,
        "quantity": entry["quantity"] if entry else None,
        "is_available": entry is not None,
        "fetched_at": fetched_at,
    }


def _response(
    variants: list[dict[str, Any]],
    rows: dict[str, dict[str, Any]],
    ttl_seconds: int,
    *,
    cached: bool,
    stale: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    results = []
    for variant in variants:
        row = rows.get(variant["id"])
        listing = None
        if row and row["is_available"]:
            listing = {
                "marketplace": MARKETPLACE,
                "listing_id": row.get("listing_id"),
                "price_cents": row["price_cents"],
                "item_url": row["item_url"],
                "float_value": row.get("float_value"),
                "quantity": row.get("quantity"),
                "fetched_at": row.get("fetched_at"),
                "stale": stale,
            }
        results.append(
            {
                "variant_id": variant["id"],
                "market_hash_name": variant["market_hash_name"],
                "listing": listing,
                "cached": cached,
                "error": (
                    f"{error}. Показана последняя сохранённая цена."
                    if error and listing
                    else error
                ),
            }
        )
    return {
        "marketplace": MARKETPLACE,
        "cache_ttl_seconds": ttl_seconds,
        "variants": results,
    }
