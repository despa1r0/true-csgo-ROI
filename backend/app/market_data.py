"""CSFloat price synchronization backed by PostgreSQL."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlencode

from psycopg.types.json import Jsonb

from .csfloat import (
    CsfloatRequestError,
    get_active_listings,
    get_buy_orders,
    get_listing,
    get_price_index,
    get_sales_history,
    search_market_listings,
)
from .database import get_connection


MARKETPLACE = "CSFloat"
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_DETAILS_TTL_SECONDS = 120
DETAILS_VERSION = 3
WEAR_FLOAT_RANGES = {
    "factory-new": (0.0, 0.07),
    "minimal-wear": (0.07, 0.15),
    "field-tested": (0.15, 0.38),
    "well-worn": (0.38, 0.45),
    "battle-scarred": (0.45, 1.0),
}
VARIANT_CATEGORIES = {"any": 0, "normal": 1, "stattrak": 2, "souvenir": 3}
LIQUIDITY_METHOD = (
    "Beta-оценка: 65% — сохранение цены при быстрой продаже (лучшая заявка / "
    "минимальный листинг), 25% — глубина заявок в пределах 5% от лучшей, "
    "10% — частота продаж в доступной истории. Это рыночный score, а не "
    "вероятность продажи."
)


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def get_csfloat_prices(skin_id: str) -> dict[str, Any]:
    """Synchronize the global index when stale and return one skin's prices."""
    ttl_seconds = _positive_int_env(
        "CSFLOAT_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS
    )
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


def get_csfloat_skin_listings(
    skin_id: str,
    *,
    sort_by: str = "best_deal",
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
    """Return concrete CSFloat listings for one local catalogue skin."""
    with get_connection() as connection:
        skin = connection.execute(
            "SELECT id, name, image_url, paint_index, min_float, max_float "
            "FROM skins WHERE id = %s",
            (skin_id,),
        ).fetchone()
        if skin is None:
            return None
        variants = {
            row["market_hash_name"]: row["id"]
            for row in connection.execute(
                "SELECT id, market_hash_name FROM skin_variants "
                "WHERE skin_id = %s AND market_hash_name IS NOT NULL",
                (skin_id,),
            ).fetchall()
        }

    try:
        paint_index = int(skin["paint_index"])
    except (TypeError, ValueError):
        return {
            "marketplace": MARKETPLACE,
            "sort_by": sort_by,
            "listings": [],
            "error": "Для этого скина отсутствует paint index",
        }

    effective_min = min_float
    effective_max = max_float
    if wear:
        wear_min, wear_max = WEAR_FLOAT_RANGES[wear]
        effective_min = max(wear_min, min_float) if min_float is not None else wear_min
        effective_max = min(wear_max, max_float) if max_float is not None else wear_max
    if effective_min is not None and effective_max is not None and effective_min > effective_max:
        return {
            "marketplace": MARKETPLACE,
            "sort_by": sort_by,
            "listings": [],
            "error": None,
        }

    try:
        raw_listings = search_market_listings(
            paint_index=paint_index,
            sort_by=sort_by,
            category=VARIANT_CATEGORIES[variant],
            min_float=effective_min,
            max_float=effective_max,
            min_price_cents=min_price_cents,
            max_price_cents=max_price_cents,
            limit=50 if has_stickers or has_charm else limit,
        )
    except CsfloatRequestError as error:
        return {
            "marketplace": MARKETPLACE,
            "sort_by": sort_by,
            "listings": [],
            "error": str(error),
        }

    listings = []
    for listing in raw_listings:
        if listing.get("item_name") != skin["name"]:
            continue
        if has_stickers and not listing.get("stickers"):
            continue
        if has_charm and not listing.get("charms"):
            continue
        listing["variant_id"] = variants.get(listing.get("market_hash_name"))
        listing["image_url"] = listing.get("image_url") or skin["image_url"]
        listings.append(listing)
        if len(listings) >= limit:
            break
    return {
        "marketplace": MARKETPLACE,
        "sort_by": sort_by,
        "listings": listings,
        "error": None,
    }


def get_csfloat_listing_quick_sell(listing_id: str) -> dict[str, Any] | None:
    """Return buy orders matched by CSFloat to one concrete inventory item."""
    try:
        listing = get_listing(listing_id)
        if listing is None:
            return None
        orders = get_buy_orders(listing_id, limit=10)
    except CsfloatRequestError as error:
        return {
            "listing_id": listing_id,
            "best_price_cents": None,
            "best_price_quantity": 0,
            "discount_percent": None,
            "orders": [],
            "error": str(error),
        }

    best_price = max((order["price_cents"] for order in orders), default=None)
    best_quantity = sum(
        order["quantity"] for order in orders if order["price_cents"] == best_price
    )
    near_bid_depth = 0
    if best_price is not None:
        near_bid_floor = Decimal(best_price) * Decimal("0.95")
        near_bid_depth = sum(
            order["quantity"]
            for order in orders
            if Decimal(order["price_cents"]) >= near_bid_floor
        )
    discount = None
    if best_price is not None and listing["price_cents"]:
        retention = min(
            Decimal("100"),
            Decimal(best_price) / Decimal(listing["price_cents"]) * Decimal("100"),
        )
        discount = float(
            (Decimal("100") - retention).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        )
    return {
        "listing_id": listing_id,
        "listing_price_cents": listing["price_cents"],
        "best_price_cents": best_price,
        "best_price_quantity": best_quantity,
        "discount_percent": discount,
        "near_bid_depth": near_bid_depth,
        "orders": orders,
        "error": None,
        "note": (
            "CSFloat проверил эти заявки по float и свойствам выбранного лота."
        ),
    }


def get_csfloat_variant_details(variant_id: str) -> dict[str, Any] | None:
    """Load listings, matching buy orders and market activity on demand."""
    ttl_seconds = _positive_int_env(
        "CSFLOAT_DETAILS_TTL_SECONDS", DEFAULT_DETAILS_TTL_SECONDS
    )
    context, cached = _load_variant_detail_cache(variant_id, ttl_seconds)
    if context is None:
        return None
    if cached and cached["is_fresh"]:
        return _detail_response(context, cached, cached=True, stale=False)

    listings: list[dict[str, object]] = []
    sales: list[dict[str, object]] = []
    listings_error = None
    sales_error = None
    with ThreadPoolExecutor(max_workers=2) as executor:
        listings_future = executor.submit(
            get_active_listings, context["market_hash_name"], limit=10
        )
        sales_future = executor.submit(get_sales_history, context["market_hash_name"])
        try:
            listings = listings_future.result()
        except CsfloatRequestError as error:
            listings_error = str(error)
        try:
            sales = sales_future.result()
        except CsfloatRequestError as error:
            sales_error = str(error)

    stale = False
    if listings_error and cached:
        listings = cached["listings"]
        stale = True
    if sales_error and cached:
        sales = cached["sales"]
        stale = True

    buy_orders: list[dict[str, object]] = []
    buy_orders_error = None
    if listings:
        try:
            buy_orders = get_buy_orders(str(listings[0]["listing_id"]), limit=10)
        except CsfloatRequestError as error:
            buy_orders_error = str(error)
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
        "listings_error": listings_error,
        "sales_error": sales_error,
        "buy_orders_error": buy_orders_error,
        "fetched_at": datetime.now(timezone.utc),
    }
    _store_variant_details(variant_id, detail)
    return _detail_response(context, detail, cached=False, stale=stale)


def calculate_liquidity(
    sales: list[dict[str, object]],
    lowest_ask_cents: int | None,
    buy_orders: list[dict[str, object]],
) -> dict[str, Any]:
    """Estimate execution quality from spread, near-bid depth and sales rate."""
    best_bid = max(
        (
            order["price_cents"]
            for order in buy_orders
            if order.get("price_cents") is not None
        ),
        default=None,
    )
    sales_per_day = _sales_per_day(sales)
    if not lowest_ask_cents or best_bid is None:
        return {
            "score": None,
            "label": "unavailable",
            "price_retention_percent": None,
            "quick_sell_discount_percent": None,
            "near_bid_depth": 0,
            "sales_per_day": sales_per_day,
        }

    retention = min(
        Decimal("100"),
        Decimal(best_bid) / Decimal(lowest_ask_cents) * Decimal("100"),
    )
    near_bid_floor = Decimal(best_bid) * Decimal("0.95")
    near_bid_depth = sum(
        int(order["quantity"])
        for order in buy_orders
        if Decimal(int(order["price_cents"])) >= near_bid_floor
    )
    depth_score = min(Decimal("100"), Decimal(near_bid_depth) * Decimal("5"))
    velocity_score = (
        min(Decimal("100"), Decimal(str(sales_per_day)) * Decimal("50"))
        if sales_per_day is not None
        else Decimal("0")
    )
    score = int(
        (
            retention * Decimal("0.65")
            + depth_score * Decimal("0.25")
            + velocity_score * Decimal("0.10")
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if score >= 75:
        label = "high"
    elif score >= 50:
        label = "medium"
    else:
        label = "low"
    retention_display = retention.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return {
        "score": min(100, score),
        "label": label,
        "price_retention_percent": float(retention_display),
        "quick_sell_discount_percent": float(Decimal("100") - retention_display),
        "near_bid_depth": near_bid_depth,
        "sales_per_day": sales_per_day,
    }


def _sales_per_day(sales: list[dict[str, object]]) -> float | None:
    timestamps = []
    for sale in sales:
        value = sale.get("sold_at")
        if not isinstance(value, str):
            continue
        try:
            timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            continue
    if len(timestamps) < 2:
        return None
    span_seconds = (max(timestamps) - min(timestamps)).total_seconds()
    span_days = Decimal(str(span_seconds)) / Decimal("86400")
    span_days = max(span_days, Decimal("0.0416667"))
    rate = Decimal(len(timestamps) - 1) / span_days
    return float(rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
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
                   buy_orders, listings_error, sales_error, buy_orders_error,
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
                liquidity_label, listings, sales, buy_orders, listings_error,
                sales_error, buy_orders_error, details_version, fetched_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
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
    item_url = context.get("item_url") or (
        f"https://csfloat.com/search?"
        f"{urlencode({'market_hash_name': context['market_hash_name']})}"
    )
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
            "item_url": item_url,
        },
        "stats": {
            "sales_count": detail.get("sales_count"),
            "sales_scope": "Доступная история CSFloat",
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
                "Заявки проверены относительно самого дешёвого активного лота. "
                "Для конкретного инвентарного предмета итог зависит от его float и наклеек."
            ),
        },
        "listings": listings,
        "sales": detail.get("sales") or [],
        "listings_error": detail.get("listings_error"),
        "sales_error": detail.get("sales_error"),
        "buy_orders_error": detail.get("buy_orders_error"),
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
