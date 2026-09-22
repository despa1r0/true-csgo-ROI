"""Persistence operations for marketplace price snapshots."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from ..database import get_connection


def load_skin_cache(
    skin_id: str, marketplace: str, ttl_seconds: int
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
                (marketplace, skin_id),
            ).fetchall()
        }
        sync = connection.execute(
            """
            SELECT fetched_at >= NOW() - (%s * INTERVAL '1 second') AS is_fresh
            FROM marketplace_syncs
            WHERE marketplace = %s
            """,
            (ttl_seconds, marketplace),
        ).fetchone()
    return variants, cached, bool(sync and sync["is_fresh"])


def store_csfloat_price_index(
    price_index: dict[str, dict[str, int]], *, marketplace: str
) -> None:
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
        rows = [_csfloat_index_row(variant, price_index) for variant in variants]
        for row in rows:
            row["marketplace"] = marketplace
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
            (marketplace,),
        )


def store_whitemarket_listing_rows(
    rows: list[dict[str, Any]], *, marketplace: str
) -> None:
    if not rows:
        return
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO marketplace_listings (
                    marketplace, variant_id, listing_id, price_cents, item_url,
                    float_value, quantity, is_available, fetched_at
                ) VALUES (
                    %(marketplace)s, %(variant_id)s, %(listing_id)s, %(price_cents)s,
                    %(item_url)s, %(float_value)s, %(quantity)s, %(is_available)s, NOW()
                )
                ON CONFLICT (marketplace, variant_id) DO UPDATE SET
                    listing_id = EXCLUDED.listing_id,
                    price_cents = EXCLUDED.price_cents,
                    item_url = EXCLUDED.item_url,
                    float_value = EXCLUDED.float_value,
                    quantity = EXCLUDED.quantity,
                    is_available = EXCLUDED.is_available,
                    fetched_at = NOW()
                """,
                [{**row, "marketplace": marketplace} for row in rows],
            )


def _csfloat_index_row(
    variant: dict[str, Any], price_index: dict[str, dict[str, int]]
) -> dict[str, Any]:
    market_hash_name = variant["market_hash_name"]
    entry = price_index.get(market_hash_name)
    return {
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
        "fetched_at": None,
    }
