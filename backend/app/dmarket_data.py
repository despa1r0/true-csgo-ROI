"""DMarket price index, listings and variant analytics.

The price index comes from the public aggregated-prices endpoint: one request
covers every variant of a skin, and the same response carries the best bid, so
quick-flip quotes need no extra calls. Listings, targets and sales history are
loaded live and only when API keys are configured.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from .analytics.liquidity import LIQUIDITY_METHOD, calculate_liquidity
from .database import get_connection
from .marketplaces.dmarket import (
    KEYS_MISSING_MESSAGE,
    DmarketRequestError,
    get_active_listings,
    get_aggregated_prices,
    get_buy_orders,
    get_sales_history,
    item_url,
    keys_configured,
)
from .repositories.market_prices import store_listing_rows


MARKETPLACE = "DMarket"
MARKETPLACE_ID = "dmarket"
DEFAULT_CACHE_TTL_SECONDS = 300
WEAR_NAMES = {
    "factory-new": "Factory New",
    "minimal-wear": "Minimal Wear",
    "field-tested": "Field-Tested",
    "well-worn": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
}

# Best bids from the latest aggregated responses, keyed by exact title.
_bid_cache: dict[str, tuple[float, int | None, int]] = {}
_bid_cache_lock = threading.Lock()


def cache_ttl_seconds() -> int:
    try:
        value = int(os.getenv("DMARKET_CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS)))
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS
    return value if value > 0 else DEFAULT_CACHE_TTL_SECONDS


def _remember_bids(prices: dict[str, dict[str, int | None]], titles: list[str]) -> None:
    now = time.monotonic()
    with _bid_cache_lock:
        for title in titles:
            entry = prices.get(title) or {}
            _bid_cache[title] = (now, entry.get("bid_cents"), entry.get("bid_count") or 0)
        if len(_bid_cache) > 5000:
            for title in sorted(_bid_cache, key=lambda key: _bid_cache[key][0])[:1000]:
                del _bid_cache[title]


def _cached_bid(title: str, ttl_seconds: int) -> tuple[int | None, int] | None:
    with _bid_cache_lock:
        entry = _bid_cache.get(title)
    if entry is None or time.monotonic() - entry[0] > ttl_seconds:
        return None
    return entry[1], entry[2]


def get_dmarket_prices(skin_id: str) -> dict[str, Any]:
    """Return the cached minimum ask per variant, refreshing stale rows in one request."""
    ttl = cache_ttl_seconds()
    with get_connection() as connection:
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
    if stale:
        titles = [row["market_hash_name"] for row in stale]
        try:
            prices = get_aggregated_prices(titles)
        except DmarketRequestError as request_error:
            error = str(request_error)
        else:
            _remember_bids(prices, titles)
            fetched_at = datetime.now(timezone.utc)
            for row in stale:
                entry = prices.get(row["market_hash_name"]) or {}
                ask = entry.get("ask_cents")
                fresh_rows[row["id"]] = {
                    "variant_id": row["id"],
                    "listing_id": None,
                    "price_cents": ask,
                    "item_url": item_url(row["market_hash_name"]) if ask else None,
                    "float_value": None,
                    "quantity": entry.get("ask_count") if ask else None,
                    "is_available": ask is not None,
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


def get_dmarket_variant_fast_buy(variant_id: str) -> dict[str, Any] | None:
    """Best current target price for one variant; used by quick-flip comparison."""
    variant = _variant(variant_id)
    if variant is None:
        return None
    title = variant["market_hash_name"]
    cached = _cached_bid(title, cache_ttl_seconds())
    if cached is not None:
        return {"best_price_cents": cached[0], "error": None, "cached": True}
    try:
        prices = get_aggregated_prices([title])
    except DmarketRequestError as error:
        return {"best_price_cents": None, "error": str(error), "cached": False}
    _remember_bids(prices, [title])
    return {
        "best_price_cents": (prices.get(title) or {}).get("bid_cents"),
        "error": None,
        "cached": False,
    }


def get_dmarket_skin_listings(
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
    """Concrete DMarket offers for the variants selected by wear and kind."""
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
    selected = [
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
            offers = get_active_listings(
                row["market_hash_name"],
                min_float=min_float, max_float=max_float,
                min_price_cents=min_price_cents, max_price_cents=max_price_cents,
                has_stickers=has_stickers, has_charm=has_charm, limit=limit,
            )
        except DmarketRequestError as error:
            errors.append(str(error))
            # Missing or rejected keys fail identically for every variant.
            if not keys_configured():
                break
            continue
        for offer in offers:
            listings.append({
                **offer,
                "variant_id": row["id"],
                "market_hash_name": row["market_hash_name"],
                "marketplace": MARKETPLACE,
                "marketplace_id": MARKETPLACE_ID,
                "wear_name": row["wear_name"],
                "stattrak": row["stattrak"],
                "souvenir": row["souvenir"],
                "image_url": offer.get("image_url") or row["image_url"] or skin["image_url"],
                "item_name": skin["name"],
            })
    listings.sort(key=lambda listing: listing["price_cents"])
    return {
        "marketplace": MARKETPLACE,
        "sort_by": "lowest_price",
        "requested_sort_by": sort_by,
        "listings": listings[:limit],
        "error": errors[0] if errors and not listings else None,
        # Lets the UI say "keys needed" instead of offering a pointless retry.
        "error_code": "credentials_required" if errors and not keys_configured() else None,
        "partial_error": errors[0] if errors and listings else None,
    }


def get_dmarket_variant_details(variant_id: str) -> dict[str, Any] | None:
    """Live snapshot shaped like the other marketplaces' variant details."""
    variant = _variant(variant_id)
    if variant is None:
        return None
    title = variant["market_hash_name"]
    fetched_at = datetime.now(timezone.utc)

    summary: dict[str, int | None] = {}
    summary_error: str | None = None
    listings: list[dict[str, object]] = []
    orders: list[dict[str, object]] = []
    sales: list[dict[str, object]] = []
    listings_error = orders_error = sales_error = None

    with ThreadPoolExecutor(max_workers=4) as executor:
        summary_future = executor.submit(get_aggregated_prices, [title])
        signed = keys_configured()
        futures = {
            "listings": executor.submit(get_active_listings, title, limit=10),
            "orders": executor.submit(get_buy_orders, title, limit=10),
            "sales": executor.submit(get_sales_history, title),
        } if signed else {}
        try:
            prices = summary_future.result()
        except DmarketRequestError as error:
            summary_error = str(error)
        else:
            _remember_bids(prices, [title])
            summary = prices.get(title) or {}
        if signed:
            try:
                listings = futures["listings"].result()
            except DmarketRequestError as error:
                listings_error = str(error)
            try:
                orders = futures["orders"].result()
            except DmarketRequestError as error:
                orders_error = str(error)
            try:
                sales = futures["sales"].result()
            except DmarketRequestError as error:
                sales_error = str(error)
        else:
            listings_error = sales_error = KEYS_MISSING_MESSAGE

    for listing in listings:
        listing["variant_id"] = variant_id
        listing["market_hash_name"] = title
        listing["marketplace_id"] = MARKETPLACE_ID
        listing["image_url"] = listing.get("image_url") or variant.get("image_url")

    lowest_ask = summary.get("ask_cents") or (listings[0]["price_cents"] if listings else None)
    # Unrestricted targets accept any item of this title; without the target
    # book the aggregated best bid is the only executable quote available.
    open_orders = [order for order in orders if not order.get("attributes")]
    if orders_error is None and signed:
        bid_orders = open_orders
        best_bid = max((order["price_cents"] for order in bid_orders), default=None)
        bids_available = True
    else:
        best_bid = summary.get("bid_cents")
        bid_orders = (
            [{"price_cents": best_bid, "quantity": 1, "min_float": None, "max_float": None}]
            if best_bid else []
        )
        bids_available = summary_error is None
    liquidity = calculate_liquidity(
        sales, lowest_ask, bid_orders,
        sales_available=sales_error is None,
        orders_available=bids_available,
        now=fetched_at,
    )
    best_bid_quantity = sum(
        order["quantity"] for order in bid_orders if order["price_cents"] == best_bid
    )

    def component(error: str | None, available: bool = True) -> dict[str, Any]:
        return {
            "status": "fresh" if error is None and available else "unavailable",
            "fetched_at": fetched_at if error is None and available else None,
            "error": error,
        }

    return {
        "marketplace": MARKETPLACE_ID,
        "variant_id": variant_id,
        "market_hash_name": title,
        "overview": {
            "price_cents": lowest_ask,
            "active_listings": summary.get("ask_count") or (len(listings) or None),
            "item_url": item_url(title),
        },
        "stats": {
            "sales_count": len(sales) if sales_error is None else None,
            "sales_scope": "Последние продажи DMarket",
            "sales_per_day": liquidity["sales_per_day"],
            "sales_count_7d": liquidity["sales_count_7d"],
            "liquidity_score": liquidity["score"],
            "liquidity_label": liquidity["label"],
            "liquidity_data_status": liquidity["data_status"],
            "price_retention_percent": liquidity["price_retention_percent"],
            "near_bid_depth": liquidity["near_bid_depth"],
            "methodology": LIQUIDITY_METHOD,
        },
        "quick_sell": {
            "best_price_cents": best_bid,
            "best_price_quantity": best_bid_quantity,
            "discount_percent": liquidity["quick_sell_discount_percent"],
            "near_bid_depth": liquidity["near_bid_depth"],
            "orders": [
                {key: order[key] for key in ("price_cents", "quantity", "min_float", "max_float")}
                for order in (orders if signed and orders_error is None else bid_orders)
            ],
            "error": orders_error if signed else summary_error,
            "note": (
                "Заявки (targets) DMarket по точному названию. Заявки с условиями "
                "по float, фазе или paint seed подходят не каждому предмету."
                if signed else
                "Лучшая заявка из публичного агрегата DMarket. Полный список заявок "
                "доступен после настройки API-ключей."
            ),
        },
        "listings": listings,
        "sales": sales,
        "listings_error": listings_error,
        "sales_error": sales_error,
        "buy_orders_error": orders_error if signed else summary_error,
        "components": {
            # The aggregate already states the lowest ask and the offer count.
            "listings": component(None if summary_error is None else listings_error or summary_error),
            "sales": component(sales_error),
            "buy_orders": component(orders_error if signed else summary_error),
        },
        "fetched_at": fetched_at,
        "cached": False,
        "stale": False,
        # "Partial" tells the UI the lowest ask may be missing; that is only
        # true when the aggregate itself failed. Other gaps are per component.
        "is_partial": summary_error is not None,
    }


def _variant(variant_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT market_hash_name, image_url FROM skin_variants WHERE id = %s",
            (variant_id,),
        ).fetchone()
    if row is None or not row.get("market_hash_name"):
        return None
    return dict(row)
