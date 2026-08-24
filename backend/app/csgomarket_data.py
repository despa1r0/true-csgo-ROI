"""Market.CSGO synchronization and analytics backed by PostgreSQL."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from psycopg.types.json import Jsonb

from .csgomarket import (
    CSGOMARKET_ITEM_URL,
    CsgoMarketRequestError,
    get_active_listings,
    get_order_book,
    get_price_index,
    get_sales_history,
)
from .database import get_connection
from .market_data import LIQUIDITY_METHOD, calculate_liquidity


MARKETPLACE = "CSGO Market"
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_DETAILS_TTL_SECONDS = 120
DETAILS_VERSION = 1


def get_csgomarket_prices(skin_id: str) -> dict[str, Any]:
    """Synchronize the public price index when stale and return one skin."""
    ttl_seconds = _positive_int_env(
        "CSGOMARKET_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS
    )
    variants, cached, sync_is_fresh = _load_skin_cache(skin_id, ttl_seconds)
    if sync_is_fresh:
        return _price_response(variants, cached, ttl_seconds, cached=True)

    try:
        price_index = get_price_index()
        _store_price_index(price_index)
    except CsgoMarketRequestError as error:
        return _price_response(
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
    return _price_response(variants, fresh_rows, ttl_seconds, cached=False)


def get_csgomarket_variant_details(variant_id: str) -> dict[str, Any] | None:
    """Load concrete listings, public sales and the private order book."""
    ttl_seconds = _positive_int_env(
        "CSGOMARKET_DETAILS_TTL_SECONDS", DEFAULT_DETAILS_TTL_SECONDS
    )
    context, cached = _load_variant_detail_cache(variant_id, ttl_seconds)
    if context is None:
        return None
    if cached and cached["is_fresh"]:
        return _detail_response(context, cached, cached=True, stale=False)

    listings: list[dict[str, object]] = []
    sales: list[dict[str, object]] = []
    buy_orders: list[dict[str, int]] = []
    sell_orders: list[dict[str, int]] = []
    listings_error = None
    sales_error = None
    buy_orders_error = None
    market_hash_name = context["market_hash_name"]

    with ThreadPoolExecutor(max_workers=3) as executor:
        listings_future = executor.submit(
            get_active_listings, market_hash_name, limit=10
        )
        sales_future = executor.submit(get_sales_history, market_hash_name, limit=200)
        order_book_future = executor.submit(get_order_book, market_hash_name, limit=10)
        try:
            listings = listings_future.result()
        except CsgoMarketRequestError as error:
            listings_error = str(error)
        try:
            sales = sales_future.result()
        except CsgoMarketRequestError as error:
            sales_error = str(error)
        try:
            order_book = order_book_future.result()
            buy_orders = order_book["buy_orders"]
            sell_orders = order_book["sell_orders"]
        except CsgoMarketRequestError as error:
            buy_orders_error = str(error)

    stale = False
    if listings_error and cached:
        listings = cached["listings"]
        stale = True
    if sales_error and cached:
        sales = cached["sales"]
        stale = True
    if buy_orders_error and cached:
        buy_orders = cached["buy_orders"]
        stale = True

    lowest_ask_cents = context.get("price_cents") or (
        listings[0]["price_cents"] if listings else None
    )
    liquidity = calculate_liquidity(sales, lowest_ask_cents, buy_orders)
    detail = {
        "sales_count": len(sales) if not sales_error or sales else None,
        "liquidity_score": liquidity["score"],
        "liquidity_label": liquidity["label"],
        "listings": listings,
        "sales": sales,
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "listings_error": listings_error,
        "sales_error": sales_error,
        "buy_orders_error": buy_orders_error,
        "fetched_at": datetime.now(timezone.utc),
    }
    _store_variant_details(variant_id, detail)
    return _detail_response(context, detail, cached=False, stale=stale)


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
        "price_cents": entry["price_cents"] if entry else None,
        "item_url": (
            f"{CSGOMARKET_ITEM_URL}/{quote(market_hash_name, safe='')}"
            if entry
            else None
        ),
        "quantity": entry["quantity"] if entry else None,
        "is_available": entry is not None,
        "fetched_at": fetched_at,
    }


def _price_response(
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
                "listing_id": None,
                "price_cents": row["price_cents"],
                "item_url": row["item_url"],
                "float_value": None,
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
            SELECT sales_count, liquidity_score, liquidity_label, listings, sales,
                   buy_orders, sell_orders, listings_error, sales_error, buy_orders_error,
                   fetched_at,
                   details_version >= %s
                     AND fetched_at >= NOW() - (%s * INTERVAL '1 second') AS is_fresh
            FROM marketplace_variant_details
            WHERE marketplace = %s AND variant_id = %s
            """,
            (DETAILS_VERSION, ttl_seconds, MARKETPLACE, variant_id),
        ).fetchone()
    return dict(context), dict(cached) if cached else None


def _store_variant_details(variant_id: str, detail: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO marketplace_variant_details (
                marketplace, variant_id, sales_count, liquidity_score,
                liquidity_label, listings, sales, buy_orders, sell_orders, listings_error,
                sales_error, buy_orders_error, details_version, fetched_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (marketplace, variant_id) DO UPDATE SET
                sales_count = EXCLUDED.sales_count,
                liquidity_score = EXCLUDED.liquidity_score,
                liquidity_label = EXCLUDED.liquidity_label,
                listings = EXCLUDED.listings,
                sales = EXCLUDED.sales,
                buy_orders = EXCLUDED.buy_orders,
                sell_orders = EXCLUDED.sell_orders,
                listings_error = EXCLUDED.listings_error,
                sales_error = EXCLUDED.sales_error,
                buy_orders_error = EXCLUDED.buy_orders_error,
                details_version = EXCLUDED.details_version,
                fetched_at = NOW()
            """,
            (
                MARKETPLACE,
                variant_id,
                detail["sales_count"],
                detail["liquidity_score"],
                detail["liquidity_label"],
                Jsonb(detail["listings"]),
                Jsonb(detail["sales"]),
                Jsonb(detail["buy_orders"]),
                Jsonb(detail["sell_orders"]),
                detail["listings_error"],
                detail["sales_error"],
                detail["buy_orders_error"],
                DETAILS_VERSION,
            ),
        )


def _detail_response(
    context: dict[str, Any],
    detail: dict[str, Any],
    *,
    cached: bool,
    stale: bool,
) -> dict[str, Any]:
    listings = detail.get("listings") or []
    buy_orders = detail.get("buy_orders") or []
    lowest_ask_cents = context.get("price_cents") or (
        listings[0]["price_cents"] if listings else None
    )
    liquidity = calculate_liquidity(
        detail.get("sales") or [], lowest_ask_cents, buy_orders
    )
    best_buy_price = max(
        (order["price_cents"] for order in buy_orders), default=None
    )
    best_buy_quantity = sum(
        order["quantity"]
        for order in buy_orders
        if order["price_cents"] == best_buy_price
    )
    return {
        "marketplace": MARKETPLACE,
        "variant_id": context["variant_id"],
        "market_hash_name": context["market_hash_name"],
        "overview": {
            "price_cents": lowest_ask_cents,
            "active_listings": context.get("active_listings"),
            "item_url": context.get("item_url")
            or f"{CSGOMARKET_ITEM_URL}/{quote(context['market_hash_name'], safe='')}",
        },
        "stats": {
            "sales_count": detail.get("sales_count"),
            "sales_scope": "До 200 последних продаж CSGO Market",
            "sales_per_day": liquidity["sales_per_day"],
            "liquidity_score": liquidity["score"],
            "liquidity_label": liquidity["label"],
            "price_retention_percent": liquidity["price_retention_percent"],
            "near_bid_depth": liquidity["near_bid_depth"],
            "methodology": LIQUIDITY_METHOD,
        },
        "quick_sell": {
            "best_price_cents": best_buy_price,
            "best_price_quantity": best_buy_quantity,
            "discount_percent": liquidity["quick_sell_discount_percent"],
            "near_bid_depth": liquidity["near_bid_depth"],
            "orders": buy_orders,
            "error": detail.get("buy_orders_error"),
            "note": (
                "Стакан CSGO Market сопоставлен по market_hash_name. Для Doppler "
                "точная цена может зависеть от выбранной phase."
            ),
        },
        "listings": listings,
        "sales": detail.get("sales") or [],
        "sell_orders": detail.get("sell_orders") or [],
        "listings_error": detail.get("listings_error"),
        "sales_error": detail.get("sales_error"),
        "buy_orders_error": detail.get("buy_orders_error"),
        "fetched_at": detail.get("fetched_at"),
        "cached": cached,
        "stale": stale,
    }


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default
