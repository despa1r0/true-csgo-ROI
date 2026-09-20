"""CS.MONEY listing cache and refresh queue backed by PostgreSQL."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg.types.json import Jsonb

from .database import get_connection


MARKETPLACE = "CS.MONEY"
MARKETPLACE_ID = "csmoney"
DEFAULT_TTL_SECONDS = 1800
MAX_LISTINGS_PER_VARIANT = 10
WEAR_NAMES = {
    "factory-new": "Factory New",
    "minimal-wear": "Minimal Wear",
    "field-tested": "Field-Tested",
    "well-worn": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
}


def cache_ttl_seconds() -> int:
    try:
        value = int(os.getenv("CSMONEY_CACHE_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)))
    except ValueError:
        return DEFAULT_TTL_SECONDS
    return value if value > 0 else DEFAULT_TTL_SECONDS


def _fresh(state: dict[str, Any] | None, ttl_seconds: int) -> bool:
    fetched_at = state.get("fetched_at") if state else None
    return bool(fetched_at and fetched_at >= datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds))


def _refresh_allowed(state: dict[str, Any]) -> bool:
    attempted = state.get("last_attempt_at")
    return not state.get("last_error") or not attempted or attempted < datetime.now(timezone.utc) - timedelta(minutes=15)


def enqueue_variants(variant_ids: list[str], *, priority: int = 100) -> int:
    """Request refreshes without starting a browser in the API process."""
    unique_ids = list(dict.fromkeys(variant_ids))
    if not unique_ids:
        return 0
    with get_connection() as connection:
        rows = connection.execute(
            """
            INSERT INTO csmoney_refresh_jobs (variant_id, priority)
            SELECT id, %s FROM skin_variants WHERE id = ANY(%s)
            ON CONFLICT (variant_id) DO UPDATE SET
                priority = GREATEST(csmoney_refresh_jobs.priority, EXCLUDED.priority)
            RETURNING variant_id
            """,
            (priority, unique_ids),
        ).fetchall()
    return len(rows)


def claim_refresh_job(*, lease_seconds: int = 300) -> dict[str, Any] | None:
    """Atomically lease the highest-priority pending variant."""
    with get_connection() as connection:
        row = connection.execute(
            """
            WITH candidate AS (
                SELECT variant_id FROM csmoney_refresh_jobs
                WHERE lease_until IS NULL OR lease_until <= NOW()
                ORDER BY priority DESC, requested_at ASC
                FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE csmoney_refresh_jobs j
            SET lease_until = NOW() + (%s * INTERVAL '1 second'),
                attempts = attempts + 1
            FROM candidate c
            WHERE j.variant_id = c.variant_id
            RETURNING j.variant_id, j.priority, j.attempts
            """,
            (lease_seconds,),
        ).fetchone()
    return dict(row) if row else None


def complete_refresh_job(variant_id: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM csmoney_refresh_jobs WHERE variant_id = %s", (variant_id,)
        )


def defer_refresh_job(variant_id: str, *, seconds: int = 300) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE csmoney_refresh_jobs
            SET lease_until = NOW() + (%s * INTERVAL '1 second'),
                priority = LEAST(priority, 20)
            WHERE variant_id = %s
            """,
            (seconds, variant_id),
        )


def load_variant_context(variant_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT v.id AS variant_id, v.skin_id, v.market_hash_name,
                   v.wear_name, v.stattrak, v.souvenir, v.image_url,
                   s.name AS item_name, s.raw_data ->> 'phase' AS phase
            FROM skin_variants v JOIN skins s ON s.id = v.skin_id
            WHERE v.id = %s AND v.market_hash_name IS NOT NULL
            """,
            (variant_id,),
        ).fetchone()
    return dict(row) if row else None


def store_variant_capture(variant_id: str, capture: dict[str, Any]) -> int:
    """Replace one variant's top listings after a successful page capture.

    A full first page with zero exact matches cannot establish absence: keep
    prior listings and mark the attempted refresh incomplete in that case.
    """
    listings = capture["listings"]
    partial = bool(capture["is_partial"])
    page_items = int(capture["page_items"])
    if len(listings) > MAX_LISTINGS_PER_VARIANT:
        raise ValueError("CS.MONEY capture exceeds the ten-listing limit")
    with get_connection() as connection:
        if partial and not listings:
            connection.execute(
                """
                INSERT INTO csmoney_variant_state (
                    variant_id, fetched_at, last_attempt_at, page_items, exact_matches,
                    is_partial, last_error
                ) VALUES (%s, NULL, NOW(), %s, 0, TRUE, %s)
                ON CONFLICT (variant_id) DO UPDATE SET
                    fetched_at = NULL, last_attempt_at = NOW(), page_items = EXCLUDED.page_items,
                    exact_matches = 0, is_partial = TRUE,
                    last_error = EXCLUDED.last_error
                """,
                (variant_id, page_items, "First page has no matching listing; later pages were not checked"),
            )
            return 0

        connection.execute(
            "DELETE FROM marketplace_active_listings WHERE marketplace = %s AND variant_id = %s",
            (MARKETPLACE, variant_id),
        )
        if listings:
            rows = [
                {
                    "marketplace": MARKETPLACE,
                    "listing_id": listing["listing_id"],
                    "variant_id": variant_id,
                    "price_cents": listing["price_cents"],
                    "item_url": listing.get("item_url"),
                    "float_value": listing.get("float_value"),
                    "paint_seed": listing.get("paint_seed"),
                    "image_url": listing.get("image_url"),
                    "stickers": Jsonb(listing.get("stickers") or []),
                    "charms": Jsonb(listing.get("charms") or []),
                }
                for listing in listings
            ]
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO marketplace_active_listings (
                        marketplace, listing_id, variant_id, price_cents,
                        item_url, float_value, paint_seed, image_url,
                        stickers, charms, fetched_at
                    ) VALUES (
                        %(marketplace)s, %(listing_id)s, %(variant_id)s,
                        %(price_cents)s, %(item_url)s, %(float_value)s,
                        %(paint_seed)s, %(image_url)s, %(stickers)s,
                        %(charms)s, NOW()
                    )
                    ON CONFLICT (marketplace, listing_id) DO UPDATE SET
                        variant_id = EXCLUDED.variant_id,
                        price_cents = EXCLUDED.price_cents,
                        item_url = EXCLUDED.item_url,
                        float_value = EXCLUDED.float_value,
                        paint_seed = EXCLUDED.paint_seed,
                        image_url = EXCLUDED.image_url,
                        stickers = EXCLUDED.stickers,
                        charms = EXCLUDED.charms,
                        fetched_at = NOW()
                    """,
                    rows,
                )

        cheapest = listings[0] if listings else None
        connection.execute(
            """
            INSERT INTO marketplace_listings (
                marketplace, variant_id, listing_id, price_cents, item_url,
                float_value, quantity, is_available, fetched_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (marketplace, variant_id) DO UPDATE SET
                listing_id = EXCLUDED.listing_id,
                price_cents = EXCLUDED.price_cents,
                item_url = EXCLUDED.item_url,
                float_value = EXCLUDED.float_value,
                quantity = EXCLUDED.quantity,
                is_available = EXCLUDED.is_available,
                fetched_at = NOW()
            """,
            (
                MARKETPLACE, variant_id,
                cheapest["listing_id"] if cheapest else None,
                cheapest["price_cents"] if cheapest else None,
                cheapest.get("item_url") if cheapest else None,
                cheapest.get("float_value") if cheapest else None,
                len(listings), bool(listings),
            ),
        )
        connection.execute(
            """
            INSERT INTO csmoney_variant_state (
                variant_id, fetched_at, last_attempt_at, page_items,
                exact_matches, is_partial, last_error
            ) VALUES (%s, NOW(), NOW(), %s, %s, %s, NULL)
            ON CONFLICT (variant_id) DO UPDATE SET
                fetched_at = NOW(), last_attempt_at = NOW(),
                page_items = EXCLUDED.page_items,
                exact_matches = EXCLUDED.exact_matches,
                is_partial = EXCLUDED.is_partial, last_error = NULL
            """,
            (variant_id, page_items, int(capture["exact_matches"]), partial),
        )
    return len(listings)


def record_refresh_error(variant_id: str, message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO csmoney_variant_state (variant_id, last_attempt_at, last_error)
            VALUES (%s, NOW(), %s)
            ON CONFLICT (variant_id) DO UPDATE SET
                last_attempt_at = NOW(), last_error = EXCLUDED.last_error
            """,
            (variant_id, message[:500]),
        )


def get_csmoney_prices(skin_id: str) -> dict[str, Any]:
    """Read fresh price summaries and queue missing variants for a worker."""
    ttl = cache_ttl_seconds()
    with get_connection() as connection:
        rows = list(connection.execute(
            """
            SELECT v.id AS variant_id, v.market_hash_name,
                   p.listing_id, p.price_cents, p.item_url,
                   p.float_value, p.quantity, p.is_available,
                   st.fetched_at, st.last_attempt_at, st.last_error, st.is_partial
            FROM skin_variants v
            LEFT JOIN marketplace_listings p
              ON p.variant_id = v.id AND p.marketplace = %s
            LEFT JOIN csmoney_variant_state st ON st.variant_id = v.id
            WHERE v.skin_id = %s AND v.market_hash_name IS NOT NULL
            ORDER BY v.id
            """, (MARKETPLACE, skin_id)
        ).fetchall())
    stale_ids = [row["variant_id"] for row in rows if not _fresh(row, ttl) and _refresh_allowed(row)]
    if stale_ids:
        enqueue_variants(stale_ids, priority=100)
    results = []
    for row in rows:
        fresh = _fresh(row, ttl)
        listing = None
        if fresh and row["is_available"]:
            listing = {
                "marketplace": MARKETPLACE,
                "listing_id": row["listing_id"],
                "price_cents": row["price_cents"],
                "item_url": row["item_url"],
                "float_value": row["float_value"],
                "quantity": row["quantity"],
                "fetched_at": row["fetched_at"],
                "stale": False,
            }
        results.append({
            "variant_id": row["variant_id"],
            "market_hash_name": row["market_hash_name"],
            "listing": listing,
            "cached": True,
            "error": row["last_error"] if not fresh else None,
        })
    return {
        "marketplace": MARKETPLACE,
        "cache_ttl_seconds": ttl,
        "variants": results,
        "refresh_queued": bool(stale_ids),
    }


def _skin_context(skin_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    with get_connection() as connection:
        skin = connection.execute(
            "SELECT id, name, image_url FROM skins WHERE id = %s", (skin_id,)
        ).fetchone()
        if skin is None:
            return None, []
        variants = list(connection.execute(
            """
            SELECT v.id, v.market_hash_name, v.wear_name,
                   v.stattrak, v.souvenir, v.image_url,
                   st.fetched_at, st.is_partial, st.last_attempt_at, st.last_error
            FROM skin_variants v
            LEFT JOIN csmoney_variant_state st ON st.variant_id = v.id
            WHERE v.skin_id = %s AND v.market_hash_name IS NOT NULL
            ORDER BY v.id
            """, (skin_id,)
        ).fetchall())
    return dict(skin), [dict(row) for row in variants]


def get_csmoney_skin_listings(
    skin_id: str,
    *,
    sort_by: str = "lowest_price",
    wear: str | None = None,
    variant: str = "any",
    min_float: float | None = None,
    max_float: float | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = 30,
    only_variant_id: str | None = None,
) -> dict[str, Any] | None:
    skin, variants = _skin_context(skin_id)
    if skin is None:
        return None
    selected = [
        row for row in variants
        if (only_variant_id is None or row["id"] == only_variant_id)
        and (not wear or row["wear_name"] == WEAR_NAMES.get(wear))
        and (variant == "any"
             or (variant == "normal" and not row["stattrak"] and not row["souvenir"])
             or (variant == "stattrak" and row["stattrak"])
             or (variant == "souvenir" and row["souvenir"]))
    ]
    ttl = cache_ttl_seconds()
    stale_ids = [row["id"] for row in selected if not _fresh(row, ttl)]
    queue_ids = [row["id"] for row in selected if not _fresh(row, ttl) and _refresh_allowed(row)]
    if queue_ids:
        enqueue_variants(queue_ids, priority=100)
    selected_ids = [row["id"] for row in selected]
    if not selected_ids:
        rows: list[dict[str, Any]] = []
    else:
        with get_connection() as connection:
            rows = list(connection.execute(
                """
                SELECT listing_id, variant_id, price_cents, item_url,
                       float_value, paint_seed, image_url, stickers, charms,
                       fetched_at
                FROM marketplace_active_listings
                WHERE marketplace = %s AND variant_id = ANY(%s)
                ORDER BY price_cents, listing_id
                """, (MARKETPLACE, selected_ids)
            ).fetchall())
    selected_by_id = {row["id"]: row for row in selected}
    listings = []
    for row in rows:
        context = selected_by_id[row["variant_id"]]
        if has_stickers and not row["stickers"]:
            continue
        if has_charm and not row["charms"]:
            continue
        if min_float is not None and (row["float_value"] is None or row["float_value"] < min_float):
            continue
        if max_float is not None and (row["float_value"] is None or row["float_value"] > max_float):
            continue
        if min_price_cents is not None and row["price_cents"] < min_price_cents:
            continue
        if max_price_cents is not None and row["price_cents"] > max_price_cents:
            continue
        listings.append({
            "listing_id": row["listing_id"],
            "variant_id": row["variant_id"],
            "market_hash_name": context["market_hash_name"],
            "marketplace": MARKETPLACE,
            "marketplace_id": MARKETPLACE_ID,
            "price_cents": row["price_cents"],
            "item_url": row["item_url"],
            "float_value": row["float_value"],
            "paint_seed": row["paint_seed"],
            "image_url": row["image_url"] or context["image_url"] or skin["image_url"],
            "wear_name": context["wear_name"],
            "stattrak": context["stattrak"],
            "souvenir": context["souvenir"],
            "stickers": row["stickers"],
            "charms": row["charms"],
            "fetched_at": row["fetched_at"],
            "item_name": skin["name"],
        })
        if len(listings) >= limit:
            break
    fetched_dates = [row["fetched_at"] for row in selected if row["fetched_at"]]
    return {
        "marketplace": MARKETPLACE,
        "sort_by": "lowest_price",
        "requested_sort_by": sort_by,
        "listings": listings,
        "error": next((row["last_error"] for row in selected if row["last_error"]), None),
        "fetched_at": min(fetched_dates) if fetched_dates else None,
        "is_stale": bool(stale_ids),
        "is_partial": any(row["is_partial"] is not False for row in selected),
        "refresh_queued": bool(queue_ids),
    }


def get_csmoney_variant_details(variant_id: str) -> dict[str, Any] | None:
    context = load_variant_context(variant_id)
    if context is None:
        return None
    result = get_csmoney_skin_listings(
        context["skin_id"], limit=MAX_LISTINGS_PER_VARIANT,
        only_variant_id=variant_id,
    )
    assert result is not None
    listings = [row for row in result["listings"] if row["variant_id"] == variant_id]
    if len(listings) > MAX_LISTINGS_PER_VARIANT:
        listings = listings[:MAX_LISTINGS_PER_VARIANT]
    return {
        "marketplace": MARKETPLACE_ID,
        "variant_id": variant_id,
        "market_hash_name": context["market_hash_name"],
        "overview": {
            "price_cents": listings[0]["price_cents"] if listings else None,
            "active_listings": len(listings),
            "item_url": listings[0]["item_url"] if listings else None,
        },
        "stats": {"sales_count": None, "sales_per_day": None, "liquidity_score": None},
        "listings": listings,
        "sales": [],
        "fetched_at": result["fetched_at"],
        "cached": True,
        "stale": result["is_stale"],
        "is_partial": result["is_partial"],
        "refresh_queued": result["refresh_queued"],
        "listings_error": result["error"],
        "sales_error": "CS.MONEY does not provide sales history",
    }
