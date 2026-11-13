"""Tradeit.gg price index, store items and variant overview.

One text search by the catalogue item name covers every wear and StatTrak
variant of a skin, so a skin costs one request per cache period.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any

from .database import get_connection
from .marketplaces.tradeit import (
    TradeitRequestError,
    get_group_items,
    item_url,
    search_groups,
)
from .repositories.market_prices import store_listing_rows


MARKETPLACE = "Tradeit.gg"
MARKETPLACE_ID = "tradeit"
DEFAULT_CACHE_TTL_SECONDS = 600
WEAR_NAMES = {
    "factory-new": "Factory New",
    "minimal-wear": "Minimal Wear",
    "field-tested": "Field-Tested",
    "well-worn": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
}

# Group ids from the latest searches, keyed by exact item name.
_group_ids: dict[str, int] = {}
_group_ids_lock = threading.Lock()


def cache_ttl_seconds() -> int:
    try:
        value = int(os.getenv("TRADEIT_CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS)))
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS
    return value if value > 0 else DEFAULT_CACHE_TTL_SECONDS


def _remember_groups(groups: dict[str, dict[str, int]]) -> None:
    with _group_ids_lock:
        if len(_group_ids) > 20000:
            _group_ids.clear()
        for name, group in groups.items():
            _group_ids[name] = group["group_id"]


def _group_id(market_hash_name: str, search_name: str) -> int | None:
    with _group_ids_lock:
        known = _group_ids.get(market_hash_name)
    if known is not None:
        return known
    groups = search_groups(search_name)
    _remember_groups(groups)
    return (groups.get(market_hash_name) or {}).get("group_id")


def get_tradeit_prices(skin_id: str) -> dict[str, Any]:
    """Return the cached store price per variant, refreshing stale rows with one search."""
    ttl = cache_ttl_seconds()
    with get_connection() as connection:
        skin = connection.execute("SELECT name FROM skins WHERE id = %s", (skin_id,)).fetchone()
        variants = list(connection.execute(
            """
            SELECT id, market_hash_name FROM skin_variants
            WHERE skin_id = %s AND market_hash_name IS NOT NULL
            ORDER BY id
            """,
            (skin_id,),
        ).fetchall())
        cached = {
            row["variant_id"]: row
            for row in connection.execute(
                """
                SELECT variant_id, listing_id, price_cents, item_url, float_value,
                       quantity, is_available, fetched_at,
                       fetched_at >= NOW() - (%s * INTERVAL '1 second') AS is_fresh
                FROM marketplace_listings
                WHERE marketplace = %s
                  AND variant_id IN (SELECT id FROM skin_variants WHERE skin_id = %s)
                """,
                (ttl, MARKETPLACE, skin_id),
            ).fetchall()
        }

    stale = [row for row in variants if not (cached.get(row["id"]) or {}).get("is_fresh")]
    fresh_rows: dict[str, dict[str, Any]] = {}
    error: str | None = None
    if stale and skin is not None:
        try:
            groups = search_groups(skin["name"])
        except TradeitRequestError as request_error:
            error = str(request_error)
        else:
            _remember_groups(groups)
            fetched_at = datetime.now(timezone.utc)
            for row in stale:
                group = groups.get(row["market_hash_name"])
                fresh_rows[row["id"]] = {
                    "variant_id": row["id"],
                    "listing_id": None,
                    "price_cents": group["price_cents"] if group else None,
                    "item_url": item_url(row["market_hash_name"]) if group else None,
                    "float_value": None,
                    "quantity": group["quantity"] if group else None,
                    "is_available": group is not None,
                    "fetched_at": fetched_at,
                    "is_fresh": True,
                }
            store_listing_rows(list(fresh_rows.values()), marketplace=MARKETPLACE)

    rows = {**cached, **fresh_rows}
    results = []
    for variant in variants:
        row = rows.get(variant["id"])
        is_stale = not bool(row and row.get("is_fresh"))
        listing = None
        if row and row["is_available"]:
            listing = {
                "marketplace": MARKETPLACE,
                "listing_id": None,
                "price_cents": row["price_cents"],
                "item_url": row["item_url"],
                "float_value": None,
                "quantity": row.get("quantity"),
                "fetched_at": row.get("fetched_at"),
                "stale": is_stale,
                "source": "index",
            }
        results.append({
            "variant_id": variant["id"],
            "market_hash_name": variant["market_hash_name"],
            "listing": listing,
            "cached": variant["id"] not in fresh_rows,
            "error": (
                f"{error}. Показана последняя сохранённая цена."
                if error and listing else error
            ) if is_stale else None,
        })
    return {"marketplace": MARKETPLACE, "cache_ttl_seconds": ttl, "variants": results}


def get_tradeit_skin_listings(
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
) -> dict[str, Any] | None:
    """Individual store items for the variants selected by wear and kind."""
    with get_connection() as connection:
        skin = connection.execute(
            "SELECT id, name, image_url FROM skins WHERE id = %s", (skin_id,)
        ).fetchone()
        if skin is None:
            return None
        variants = list(connection.execute(
            """
            SELECT id, market_hash_name, wear_name, stattrak, souvenir, image_url
            FROM skin_variants
            WHERE skin_id = %s AND market_hash_name IS NOT NULL
            ORDER BY id
            """,
            (skin_id,),
        ).fetchall())
    selected = [] if has_charm else [  # the store payload carries no charm data
        row for row in variants
        if (not wear or row["wear_name"] == WEAR_NAMES.get(wear))
        and (variant == "any"
             or (variant == "normal" and not row["stattrak"] and not row["souvenir"])
             or (variant == "stattrak" and row["stattrak"])
             or (variant == "souvenir" and row["souvenir"]))
    ]
    listings: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in selected:
        try:
            group_id = _group_id(row["market_hash_name"], skin["name"])
            items = [] if group_id is None else get_group_items(
                group_id, row["market_hash_name"],
                min_float=min_float, max_float=max_float,
                min_price_cents=min_price_cents, max_price_cents=max_price_cents,
                has_stickers=has_stickers, limit=limit,
            )
        except TradeitRequestError as error:
            errors.append(str(error))
            continue
        for item in items:
            listings.append({
                **item,
                "variant_id": row["id"],
                "market_hash_name": row["market_hash_name"],
                "marketplace": MARKETPLACE,
                "marketplace_id": MARKETPLACE_ID,
                "wear_name": row["wear_name"],
                "stattrak": row["stattrak"],
                "souvenir": row["souvenir"],
                "image_url": item.get("image_url") or row["image_url"] or skin["image_url"],
                "item_name": skin["name"],
            })
    listings.sort(key=lambda listing: listing["price_cents"])
    return {
        "marketplace": MARKETPLACE,
        "sort_by": "lowest_price",
        "requested_sort_by": sort_by,
        "listings": listings[:limit],
        "error": errors[0] if errors and not listings else None,
        "partial_error": errors[0] if errors and listings else None,
    }


def get_tradeit_variant_details(variant_id: str) -> dict[str, Any] | None:
    """Live store snapshot. Tradeit.gg exposes neither sales history nor buy orders."""
    with get_connection() as connection:
        variant = connection.execute(
            """
            SELECT v.market_hash_name, v.image_url, s.name AS item_name
            FROM skin_variants v JOIN skins s ON s.id = v.skin_id
            WHERE v.id = %s AND v.market_hash_name IS NOT NULL
            """,
            (variant_id,),
        ).fetchone()
    if variant is None:
        return None
    title = variant["market_hash_name"]
    fetched_at = datetime.now(timezone.utc)
    listings: list[dict[str, object]] = []
    quantity: int | None = None
    error: str | None = None
    try:
        groups = search_groups(variant["item_name"])
        _remember_groups(groups)
        group = groups.get(title)
        if group is not None:
            quantity = group["quantity"]
            listings = get_group_items(group["group_id"], title, limit=10)
    except TradeitRequestError as request_error:
        error = str(request_error)
    for listing in listings:
        listing["variant_id"] = variant_id
        listing["market_hash_name"] = title
        listing["marketplace_id"] = MARKETPLACE_ID
        listing["image_url"] = listing.get("image_url") or variant["image_url"]
    unavailable = {"status": "unavailable", "fetched_at": None}
    return {
        "marketplace": MARKETPLACE_ID,
        "variant_id": variant_id,
        "market_hash_name": title,
        "overview": {
            "price_cents": listings[0]["price_cents"] if listings else None,
            "active_listings": quantity if listings else (None if error else 0),
            "item_url": item_url(title),
        },
        "stats": {"sales_count": None, "sales_per_day": None, "liquidity_score": None},
        "listings": listings,
        "sales": [],
        "listings_error": error,
        "sales_error": "Tradeit.gg не публикует историю продаж",
        "buy_orders_error": "Tradeit.gg не публикует заявки на покупку",
        "components": {
            "listings": {
                "status": "unavailable" if error else "fresh",
                "fetched_at": None if error else fetched_at,
                "error": error,
            },
            "sales": {**unavailable, "error": None},
            "buy_orders": {**unavailable, "error": None},
        },
        "fetched_at": fetched_at,
        "cached": False,
        "stale": False,
        "is_partial": error is not None,
    }
