"""CSFloat and WhiteMarket market-data application service."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlencode

from ..analytics.liquidity import LIQUIDITY_METHOD, calculate_liquidity
from ..cache_freshness import (
    annotate_component_freshness,
    public_component_states,
    refreshed_component_timestamps,
)
from ..database import get_connection
from ..marketplaces.base import MarketplaceRequestError
from ..marketplaces.csfloat import (
    CsfloatAuthError,
    CsfloatRequestError,
    get_active_listings,
    get_buy_orders,
    get_listing,
    get_price_index,
    get_sales_history,
    search_market_listings,
    validate_api_key,
)
from ..marketplaces.whitemarket import get_active_listings as get_whitemarket_active_listings
from ..marketplaces.whitemarket import get_buy_orders as get_whitemarket_buy_orders
from ..marketplaces.whitemarket import get_cheapest_listing as get_whitemarket_cheapest_listing
from ..repositories.market_prices import (
    load_skin_cache as _load_skin_price_cache,
    store_csfloat_price_index as _persist_csfloat_price_index,
    store_whitemarket_listing_rows as _persist_whitemarket_listing_rows,
)
from ..repositories.market_details import (
    load_buy_order_snapshot as _load_buy_order_snapshot,
    load_variant_detail_cache as _load_detail_cache,
    store_variant_details as _persist_variant_details,
)


MARKETPLACE = "CSFloat"
WHITEMARKET_MARKETPLACE = "WhiteMarket"
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_DETAILS_TTL_SECONDS = 600
DETAILS_VERSION = 4
WEAR_FLOAT_RANGES = {
    "factory-new": (0.0, 0.07),
    "minimal-wear": (0.07, 0.15),
    "field-tested": (0.15, 0.38),
    "well-worn": (0.38, 0.45),
    "battle-scarred": (0.45, 1.0),
}
VARIANT_CATEGORIES = {"any": 0, "normal": 1, "stattrak": 2, "souvenir": 3}
WEAR_NAME_BY_SLUG = {
    "factory-new": "Factory New",
    "minimal-wear": "Minimal Wear",
    "field-tested": "Field-Tested",
    "well-worn": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
}
def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def get_csfloat_prices(skin_id: str) -> dict[str, Any]:
    """Synchronize CSFloat's global index when stale and return one skin's prices."""
    # The price-list is public and returns HTTP 200 even for a bad API key.
    # Check a listings route separately so callers never treat that 200 as
    # proof that authenticated listing and buy-order requests work.
    try:
        validate_api_key()
    except CsfloatAuthError as error:
        auth_status, auth_error = "auth_failed", str(error)
    except CsfloatRequestError as error:
        auth_status, auth_error = "unavailable", str(error)
    else:
        auth_status, auth_error = "ok", None

    ttl_seconds = _positive_int_env(
        "CSFLOAT_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS
    )
    variants, cached, sync_is_fresh = _load_skin_cache(skin_id, MARKETPLACE, ttl_seconds)

    if sync_is_fresh:
        result = _response(MARKETPLACE, variants, cached, ttl_seconds, cached=True)
        return _with_csfloat_auth_status(result, auth_status, auth_error)

    try:
        price_index = get_price_index()
        _store_csfloat_price_index(price_index)
    except CsfloatRequestError as error:
        result = _response(
            MARKETPLACE,
            variants,
            cached,
            ttl_seconds,
            cached=True,
            stale=True,
            error=str(error),
        )
        return _with_csfloat_auth_status(result, auth_status, auth_error)

    fetched_at = datetime.now(timezone.utc)
    fresh_rows = {
        variant["id"]: _csfloat_index_row(variant, price_index, fetched_at)
        for variant in variants
    }
    result = _response(MARKETPLACE, variants, fresh_rows, ttl_seconds, cached=False)
    return _with_csfloat_auth_status(result, auth_status, auth_error)


def _with_csfloat_auth_status(
    result: dict[str, Any], status: str, error: str | None
) -> dict[str, Any]:
    result["provider_auth_status"] = status
    result["provider_auth_error"] = error
    if error:
        for variant in result["variants"]:
            variant["error"] = ". ".join(
                part for part in (variant["error"], error) if part
            )
    return result


def get_whitemarket_prices(skin_id: str) -> dict[str, Any]:
    """Live per-variant minimum price via WhiteMarket's Partner GraphQL API.

    WhiteMarket has no bulk "whole marketplace" price feed like CSFloat's
    price-list — only per-item search — so unlike get_csfloat_prices above,
    each variant's cheapest listing is fetched individually (in parallel)
    and cached independently in marketplace_listings, keyed by its own
    fetched_at rather than one marketplace-wide sync timestamp.
    """
    ttl_seconds = _positive_int_env(
        "WHITEMARKET_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS
    )
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
                       quantity, is_available, fetched_at,
                       fetched_at >= NOW() - (%s * INTERVAL '1 second') AS is_fresh
                FROM marketplace_listings
                WHERE marketplace = %s
                  AND variant_id IN (SELECT id FROM skin_variants WHERE skin_id = %s)
                """,
                (ttl_seconds, WHITEMARKET_MARKETPLACE, skin_id),
            ).fetchall()
        }

    stale_variants = [
        variant for variant in variants if not (cached.get(variant["id"]) or {}).get("is_fresh")
    ]

    fresh_rows: dict[str, dict[str, Any]] = {}
    fetch_errors: dict[str, str] = {}
    if stale_variants:
        fetched_at = datetime.now(timezone.utc)
        # Probe one variant before launching a request for every stale one.
        # An invalid partner token otherwise causes a burst of identical
        # authorization failures and makes the entire comparison wait for it.
        first, *remaining = stale_variants
        try:
            listing = get_whitemarket_cheapest_listing(first["market_hash_name"])
        except MarketplaceRequestError as error:
            fetch_errors[first["id"]] = str(error)
            if _whitemarket_auth_error(error):
                fetch_errors.update({variant["id"]: str(error) for variant in remaining})
                remaining = []
        else:
            row = _whitemarket_listing_row(first, listing, fetched_at)
            row["is_fresh"] = True
            fresh_rows[first["id"]] = row

        if remaining:
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {
                    executor.submit(
                        get_whitemarket_cheapest_listing, variant["market_hash_name"]
                    ): variant
                    for variant in remaining
                }
                for future, variant in futures.items():
                    try:
                        listing = future.result()
                    except MarketplaceRequestError as error:
                        fetch_errors[variant["id"]] = str(error)
                        continue
                    row = _whitemarket_listing_row(variant, listing, fetched_at)
                    row["is_fresh"] = True
                    fresh_rows[variant["id"]] = row

    if fresh_rows:
        _store_whitemarket_listing_rows(list(fresh_rows.values()))

    merged_rows = {**cached, **fresh_rows}
    result = _response(
        WHITEMARKET_MARKETPLACE,
        variants,
        merged_rows,
        ttl_seconds,
        cached=not fresh_rows,
        stale=bool(fetch_errors),
    )
    for variant in result["variants"]:
        error = fetch_errors.get(variant["variant_id"])
        if error:
            listing = variant["listing"]
            variant["error"] = (
                f"{error}. Показана последняя сохранённая цена."
                if listing and listing["stale"] else error
            )
    return result


def _whitemarket_auth_error(error: MarketplaceRequestError) -> bool:
    """Recognize provider-wide token failures that should stop the fanout."""
    message = str(error).casefold()
    return any(
        marker in message
        for marker in (
            "whitemarket_partner_token", "partner token", "access token",
            "http 401", "http 403", "unauthorized", "denied",
        )
    )


def get_whitemarket_variant_listings(
    variant_id: str,
    *,
    min_float: float | None = None,
    max_float: float | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = 30,
) -> dict[str, Any] | None:
    """Live active WhiteMarket listings for one exact catalogue variant.

    Unlike CSFloat's skin-level listings endpoint (which takes a wear param
    and translates it into a float range for one shared paint_index),
    WhiteMarket's market_hash_name already encodes the wear per variant, so
    this is looked up directly by variant_id — no wear/float-range
    translation needed. Not cached in Postgres: requires a live Partner
    Token round trip each call, unlike the price index above.
    """
    with get_connection() as connection:
        variant = connection.execute(
            "SELECT market_hash_name, image_url FROM skin_variants WHERE id = %s",
            (variant_id,),
        ).fetchone()
    if variant is None or not variant.get("market_hash_name"):
        return None

    try:
        listings = get_whitemarket_active_listings(
            variant["market_hash_name"],
            min_float=min_float,
            max_float=max_float,
            min_price_cents=min_price_cents,
            max_price_cents=max_price_cents,
            has_stickers=has_stickers,
            has_charm=has_charm,
            limit=limit,
        )
    except MarketplaceRequestError as error:
        return {
            "marketplace": WHITEMARKET_MARKETPLACE,
            "listings": [],
            "error": str(error),
        }

    for listing in listings:
        listing["image_url"] = listing.get("image_url") or variant.get("image_url")
    return {
        "marketplace": WHITEMARKET_MARKETPLACE,
        "listings": listings,
        "error": None,
    }


def get_whitemarket_skin_listings(
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
    """Skin-level WhiteMarket listings, shaped like get_csfloat_skin_listings.

    WhiteMarket's own listings are fetched per exact variant (its
    market_hash_name already encodes wear), so this resolves
    skin_id + wear + variant to the one matching skin_variants row first,
    then delegates to get_whitemarket_variant_listings. WhiteMarket has no
    "best_deal" ranking, so sort_by is accepted for a uniform frontend
    contract but listings are always price-ascending underneath.
    """
    wear_name = WEAR_NAME_BY_SLUG.get(wear) if wear else None
    query = "SELECT id, image_url FROM skin_variants WHERE skin_id = %s"
    params: list[Any] = [skin_id]
    if wear_name:
        query += " AND wear_name = %s"
        params.append(wear_name)
    if variant == "normal":
        query += " AND stattrak = FALSE AND souvenir = FALSE"
    elif variant == "stattrak":
        query += " AND stattrak = TRUE"
    elif variant == "souvenir":
        query += " AND souvenir = TRUE"

    with get_connection() as connection:
        skin_exists = connection.execute(
            "SELECT 1 FROM skins WHERE id = %s", (skin_id,)
        ).fetchone()
        if skin_exists is None:
            return None
        matched_variant = connection.execute(query, params).fetchone()

    if matched_variant is None:
        return {
            "marketplace": WHITEMARKET_MARKETPLACE,
            "sort_by": sort_by,
            "listings": [],
            "error": None,
        }

    result = get_whitemarket_variant_listings(
        matched_variant["id"],
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        has_stickers=has_stickers,
        has_charm=has_charm,
        limit=limit,
    )
    return {
        "marketplace": WHITEMARKET_MARKETPLACE,
        "sort_by": sort_by,
        "listings": result["listings"] if result else [],
        "error": result["error"] if result else None,
    }


def get_whitemarket_variant_quick_sell(variant_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        variant = connection.execute(
            "SELECT market_hash_name FROM skin_variants WHERE id = %s",
            (variant_id,),
        ).fetchone()
    if variant is None or not variant.get("market_hash_name"):
        return None

    try:
        orders = get_whitemarket_buy_orders(variant["market_hash_name"], limit=10)
    except MarketplaceRequestError as error:
        return {
            "marketplace": WHITEMARKET_MARKETPLACE,
            "best_price_cents": None,
            "best_price_quantity": 0,
            "orders": [],
            "error": str(error),
        }

    best_price = max((order["price_cents"] for order in orders), default=None)
    best_quantity = sum(
        order["quantity"] for order in orders if order["price_cents"] == best_price
    )
    return {
        "marketplace": WHITEMARKET_MARKETPLACE,
        "best_price_cents": best_price,
        "best_price_quantity": best_quantity,
        "orders": orders,
        "error": None,
    }


def get_whitemarket_variant_details(variant_id: str) -> dict[str, Any] | None:
    """Live WhiteMarket snapshot shaped like get_csfloat_variant_details.

    WhiteMarket has no sales history or liquidity score (see whitemarket.py's
    module docstring), so those fields are always empty here — this exists
    so the frontend can render a WhiteMarket panel with the same shape as
    CSFloat's, just with fewer populated fields. Not cached: always live.
    """
    with get_connection() as connection:
        variant = connection.execute(
            "SELECT market_hash_name FROM skin_variants WHERE id = %s",
            (variant_id,),
        ).fetchone()
    if variant is None or not variant.get("market_hash_name"):
        return None

    market_hash_name = variant["market_hash_name"]
    listings: list[dict[str, object]] = []
    listings_error: str | None = None
    try:
        listings = get_whitemarket_active_listings(market_hash_name, limit=10)
    except MarketplaceRequestError as error:
        listings_error = str(error)

    orders: list[dict[str, object]] = []
    quick_sell_error: str | None = None
    try:
        orders = get_whitemarket_buy_orders(market_hash_name, limit=10)
    except MarketplaceRequestError as error:
        quick_sell_error = str(error)

    lowest_ask_cents = listings[0]["price_cents"] if listings else None
    best_bid = max((order["price_cents"] for order in orders), default=None)
    best_bid_quantity = sum(
        order["quantity"] for order in orders if order["price_cents"] == best_bid
    )
    discount = None
    near_bid_depth = 0
    if best_bid is not None and lowest_ask_cents:
        retention = min(
            Decimal("100"), Decimal(best_bid) / Decimal(lowest_ask_cents) * Decimal("100")
        )
        discount = float(
            (Decimal("100") - retention).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        )
        near_bid_floor = Decimal(best_bid) * Decimal("0.95")
        near_bid_depth = sum(
            order["quantity"]
            for order in orders
            if Decimal(order["price_cents"]) >= near_bid_floor
        )

    return {
        "marketplace": WHITEMARKET_MARKETPLACE,
        "variant_id": variant_id,
        "market_hash_name": market_hash_name,
        "overview": {
            "price_cents": lowest_ask_cents,
            "active_listings": len(listings) or None,
            "item_url": listings[0]["item_url"] if listings else None,
        },
        "stats": {
            "sales_count": None,
            "sales_scope": "У WhiteMarket нет публичной истории продаж",
            "sales_per_day": None,
            "liquidity_score": None,
            "liquidity_label": None,
            "near_bid_depth": near_bid_depth,
        },
        "quick_sell": {
            "best_price_cents": best_bid,
            "best_price_quantity": best_bid_quantity,
            "discount_percent": discount,
            "near_bid_depth": near_bid_depth,
            "orders": orders,
            "error": quick_sell_error,
            "note": (
                "Публичные заявки на покупку WhiteMarket, не привязаны к float "
                "конкретного лота."
            ),
        },
        "listings": listings,
        "sales": [],
        "listings_error": listings_error,
        "sales_error": "История продаж недоступна",
        "buy_orders_error": quick_sell_error,
        "fetched_at": None,
        "cached": False,
        "stale": False,
    }


def _whitemarket_listing_row(
    variant: dict[str, Any],
    listing: dict[str, object] | None,
    fetched_at: datetime,
) -> dict[str, Any]:
    if listing is None:
        return {
            "variant_id": variant["id"],
            "listing_id": None,
            "price_cents": None,
            "item_url": None,
            "float_value": None,
            "quantity": None,
            "is_available": False,
            "fetched_at": fetched_at,
        }
    return {
        "variant_id": variant["id"],
        "listing_id": listing.get("listing_id"),
        "price_cents": listing.get("price_cents"),
        "item_url": listing.get("item_url"),
        "float_value": listing.get("float_value"),
        "quantity": listing.get("quantity"),
        "is_available": True,
        "fetched_at": fetched_at,
    }


def _store_whitemarket_listing_rows(rows: list[dict[str, Any]]) -> None:
    _persist_whitemarket_listing_rows(rows, marketplace=WHITEMARKET_MARKETPLACE)


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
            "SELECT id, name, item_type, image_url, paint_index, min_float, max_float "
            "FROM skins WHERE id = %s",
            (skin_id,),
        ).fetchone()
        if skin is None:
            return None
        variant_rows = list(
            connection.execute(
                "SELECT id, market_hash_name, wear_name, stattrak, souvenir, image_url "
                "FROM skin_variants "
                "WHERE skin_id = %s AND market_hash_name IS NOT NULL",
                (skin_id,),
            ).fetchall()
        )
        variants = {
            row["market_hash_name"]: row["id"] for row in variant_rows
        }

    if skin.get("item_type", "skin") != "skin":
        return _get_csfloat_exact_item_listings(
            skin,
            variant_rows,
            sort_by=sort_by,
            wear=wear,
            variant=variant,
            min_float=min_float,
            max_float=max_float,
            min_price_cents=min_price_cents,
            max_price_cents=max_price_cents,
            has_stickers=has_stickers,
            has_charm=has_charm,
            limit=limit,
        )

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


def _get_csfloat_exact_item_listings(
    item: dict[str, Any],
    variants: list[dict[str, Any]],
    *,
    sort_by: str,
    wear: str | None,
    variant: str,
    min_float: float | None,
    max_float: float | None,
    min_price_cents: int | None,
    max_price_cents: int | None,
    has_stickers: bool,
    has_charm: bool,
    limit: int,
) -> dict[str, Any]:
    """Load non-skin listings by exact market name instead of paint index."""
    expected_wear = WEAR_NAME_BY_SLUG.get(wear) if wear else None
    selected_variants = [
        row
        for row in variants
        if (expected_wear is None or row.get("wear_name") == expected_wear)
        and (
            variant == "any"
            or (
                variant == "normal"
                and not row.get("stattrak")
                and not row.get("souvenir")
            )
            or (variant == "stattrak" and row.get("stattrak"))
            or (variant == "souvenir" and row.get("souvenir"))
        )
    ]
    listings: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in selected_variants:
        try:
            raw_listings = get_active_listings(
                row["market_hash_name"], limit=min(limit, 10)
            )
        except CsfloatRequestError as error:
            errors.append(str(error))
            continue
        for listing in raw_listings:
            price_cents = listing.get("price_cents")
            float_value = listing.get("float_value")
            if min_price_cents is not None and (
                price_cents is None or int(price_cents) < min_price_cents
            ):
                continue
            if max_price_cents is not None and (
                price_cents is None or int(price_cents) > max_price_cents
            ):
                continue
            if min_float is not None and (
                float_value is None or float(float_value) < min_float
            ):
                continue
            if max_float is not None and (
                float_value is None or float(float_value) > max_float
            ):
                continue
            if has_stickers and not listing.get("stickers"):
                continue
            if has_charm and not listing.get("charms"):
                continue
            listing["marketplace"] = MARKETPLACE
            listing["marketplace_id"] = "csfloat"
            listing["market_hash_name"] = row["market_hash_name"]
            listing["variant_id"] = row["id"]
            listing["wear_name"] = row.get("wear_name")
            listing["image_url"] = row.get("image_url") or item.get("image_url")
            listing["item_name"] = item["name"]
            listings.append(listing)

    listings.sort(key=lambda listing: int(listing["price_cents"]))
    return {
        "marketplace": MARKETPLACE,
        "sort_by": "lowest_price",
        "requested_sort_by": sort_by,
        "listings": listings[:limit],
        "error": errors[0] if errors and not listings else None,
        "partial_error": errors[0] if errors and listings else None,
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
    elif listings_error:
        buy_orders_error = (
            "CSFloat buy orders are unavailable because listings could not be refreshed"
        )
    if buy_orders_error and cached:
        buy_orders = cached["buy_orders"]
        stale = True

    attempted_at = datetime.now(timezone.utc)
    component_timestamps = refreshed_component_timestamps(
        cached,
        errors={
            "listings": listings_error,
            "sales": sales_error,
            "buy_orders": buy_orders_error,
        },
        successful_at=attempted_at,
    )

    lowest_ask_cents = context.get("price_cents") or (
        listings[0]["price_cents"] if listings else None
    )
    liquidity = calculate_liquidity(
        sales, lowest_ask_cents, buy_orders,
        sales_available=not bool(sales_error),
        orders_available=not bool(buy_orders_error),
    )

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
        **component_timestamps,
        "fetched_at": attempted_at,
    }
    _store_variant_details(variant_id, detail)
    return _detail_response(context, detail, cached=False, stale=stale)


def get_csfloat_variant_fast_buy(variant_id: str) -> dict[str, Any] | None:
    """Return the best currently matching CSFloat bid without loading sales."""
    ttl_seconds = _positive_int_env(
        "CSFLOAT_DETAILS_TTL_SECONDS", DEFAULT_DETAILS_TTL_SECONDS
    )
    context, cached = _load_buy_order_snapshot(
        variant_id, marketplace=MARKETPLACE
    )
    if context is None:
        return None
    cached = (
        annotate_component_freshness(
            dict(cached),
            ttl_seconds=ttl_seconds,
            minimum_version=DETAILS_VERSION,
            components=("buy_orders",),
        )
        if cached
        else None
    )
    if cached and cached["buy_orders_is_fresh"]:
        orders = cached.get("buy_orders") or []
        return {
            "best_price_cents": max(
                (order["price_cents"] for order in orders), default=None
            ),
            "error": cached.get("buy_orders_error"),
            "cached": True,
        }

    try:
        listings = get_active_listings(context["market_hash_name"], limit=1)
        if not listings:
            return {"best_price_cents": None, "error": None, "cached": False}
        orders = get_buy_orders(str(listings[0]["listing_id"]), limit=10)
    except CsfloatRequestError as error:
        return {"best_price_cents": None, "error": str(error), "cached": False}
    return {
        "best_price_cents": max(
            (order["price_cents"] for order in orders), default=None
        ),
        "error": None,
        "cached": False,
    }


def _load_variant_detail_cache(
    variant_id: str, ttl_seconds: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return _load_detail_cache(
        variant_id,
        ttl_seconds,
        marketplace=MARKETPLACE,
        minimum_version=DETAILS_VERSION,
    )


def _store_variant_details(variant_id: str, detail: dict[str, Any]) -> None:
    _persist_variant_details(
        variant_id,
        detail,
        marketplace=MARKETPLACE,
        details_version=DETAILS_VERSION,
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
        detail.get("sales") or [], lowest_ask_cents, buy_orders,
        sales_available=not bool(detail.get("sales_error")),
        orders_available=not bool(detail.get("buy_orders_error")),
    )
    best_buy_price = max(
        (order["price_cents"] for order in buy_orders), default=None
    )
    best_buy_quantity = sum(
        order["quantity"]
        for order in buy_orders
        if order["price_cents"] == best_buy_price
    )
    components = public_component_states(detail)
    component_is_stale = any(
        component["status"] != "fresh" for component in components.values()
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
            "sales_float_available": any(
                sale.get("float_value") is not None
                for sale in (detail.get("sales") or [])
            ),
            "sales_float_note": (
                "CSFloat передаёт float для тех продаж, где он доступен в ответе API"
            ),
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
        "components": components,
        "fetched_at": detail.get("fetched_at"),
        "cached": cached,
        "stale": stale or component_is_stale,
        "is_partial": component_is_stale,
    }


def _load_skin_cache(
    skin_id: str, marketplace: str, ttl_seconds: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], bool]:
    return _load_skin_price_cache(skin_id, marketplace, ttl_seconds)


def _store_csfloat_price_index(price_index: dict[str, dict[str, int]]) -> None:
    _persist_csfloat_price_index(price_index, marketplace=MARKETPLACE)


def _csfloat_index_row(
    variant: dict[str, Any],
    price_index: dict[str, dict[str, int]],
    fetched_at: datetime | None,
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
        "fetched_at": fetched_at,
    }


def _response(
    marketplace: str,
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
                "marketplace": marketplace,
                "listing_id": row.get("listing_id"),
                "price_cents": row["price_cents"],
                "item_url": row["item_url"],
                "float_value": row.get("float_value"),
                "quantity": row.get("quantity"),
                "fetched_at": row.get("fetched_at"),
                "stale": stale and not bool(row.get("is_fresh")),
            }
        results.append(
            {
                "variant_id": variant["id"],
                "market_hash_name": variant["market_hash_name"],
                "listing": listing,
                "cached": cached,
                "error": (
                    f"{error}. Показана последняя сохранённая цена."
                    if error and listing and listing["stale"]
                    else error
                ),
            }
        )
    return {
        "marketplace": marketplace,
        "cache_ttl_seconds": ttl_seconds,
        "variants": results,
    }
