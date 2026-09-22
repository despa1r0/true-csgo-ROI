"""Persistence operations for independently refreshed variant details."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from ..cache_freshness import annotate_component_freshness
from ..database import get_connection


def load_variant_detail_cache(
    variant_id: str,
    ttl_seconds: int,
    *,
    marketplace: str,
    minimum_version: int,
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
            (marketplace, variant_id),
        ).fetchone()
        if context is None:
            return None, None
        cached = connection.execute(
            """
            SELECT sales_count, liquidity_score, liquidity_label, listings, sales,
                   buy_orders, listings_error, sales_error, buy_orders_error,
                   listings_fetched_at, sales_fetched_at, buy_orders_fetched_at,
                   details_version, fetched_at, NOW() AS checked_at
            FROM marketplace_variant_details
            WHERE marketplace = %s AND variant_id = %s
            """,
            (marketplace, variant_id),
        ).fetchone()
    return (
        dict(context),
        annotate_component_freshness(
            dict(cached),
            ttl_seconds=ttl_seconds,
            minimum_version=minimum_version,
        )
        if cached
        else None,
    )


def store_variant_details(
    variant_id: str,
    detail: dict[str, Any],
    *,
    marketplace: str,
    details_version: int,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO marketplace_variant_details (
                marketplace, variant_id, sales_count, liquidity_score,
                liquidity_label, listings, sales, buy_orders, listings_error,
                sales_error, buy_orders_error, listings_fetched_at,
                sales_fetched_at, buy_orders_fetched_at, details_version, fetched_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (marketplace, variant_id) DO UPDATE SET
                sales_count = EXCLUDED.sales_count,
                liquidity_score = EXCLUDED.liquidity_score,
                liquidity_label = EXCLUDED.liquidity_label,
                listings = EXCLUDED.listings,
                sales = EXCLUDED.sales,
                buy_orders = EXCLUDED.buy_orders,
                listings_error = EXCLUDED.listings_error,
                sales_error = EXCLUDED.sales_error,
                buy_orders_error = EXCLUDED.buy_orders_error,
                listings_fetched_at = EXCLUDED.listings_fetched_at,
                sales_fetched_at = EXCLUDED.sales_fetched_at,
                buy_orders_fetched_at = EXCLUDED.buy_orders_fetched_at,
                details_version = EXCLUDED.details_version,
                fetched_at = NOW()
            """,
            (
                marketplace,
                variant_id,
                detail["sales_count"],
                detail["liquidity_score"],
                detail["liquidity_label"],
                Jsonb(detail["listings"]),
                Jsonb(detail["sales"]),
                Jsonb(detail["buy_orders"]),
                detail["listings_error"],
                detail["sales_error"],
                detail["buy_orders_error"],
                detail["listings_fetched_at"],
                detail["sales_fetched_at"],
                detail["buy_orders_fetched_at"],
                details_version,
            ),
        )


def load_buy_order_snapshot(
    variant_id: str, *, marketplace: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    with get_connection() as connection:
        context = connection.execute(
            "SELECT market_hash_name FROM skin_variants WHERE id = %s", (variant_id,)
        ).fetchone()
        if context is None:
            return None, None
        cached = connection.execute(
            """
            SELECT buy_orders, buy_orders_error, buy_orders_fetched_at,
                   details_version, NOW() AS checked_at
            FROM marketplace_variant_details
            WHERE marketplace = %s AND variant_id = %s
            """,
            (marketplace, variant_id),
        ).fetchone()
    return dict(context), dict(cached) if cached else None
