"""DMarket integration through the official Trading API (api.dmarket.com).

Reference: https://docs.dmarket.com/v1/swagger.html (trading.swagger.json).

Two access levels are used:

* ``POST /marketplace-api/v1/aggregated-prices`` answers without credentials
  (verified 12 November 2026). It returns the best ask, the best bid and both
  counts for exact titles, up to 100 titles per request. This is enough for
  the price index and for quick-flip quotes.
* Concrete offers, the target (buy-order) book and the last sales require a
  signed request: ``X-Api-Key`` (public key), ``X-Sign-Date`` (unix seconds,
  valid for two minutes) and ``X-Request-Sign: dmar ed25519 <hex signature>``.
  They are available only when DMARKET_PUBLIC_KEY and DMARKET_SECRET_KEY are
  configured.

Prices are USD cents everywhere except last-sales, where DMarket returns a
decimal USD string.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .base import MarketplaceRequestError


API_URL = "https://api.dmarket.com"
GAME_ID = "a8db"  # CS2
ITEM_LIST_URL = "https://dmarket.com/ingame-items/item-list/csgo-skins"
AGGREGATED_PAGE_SIZE = 100
OFFERS_PAGE_SIZE = 100
LAST_SALES_PAGE_SIZE = 20  # documented maximum
MAX_PRICE_CENTS = 2_147_483_647  # PostgreSQL INTEGER
KEYS_MISSING_MESSAGE = (
    "Не настроены DMARKET_PUBLIC_KEY и DMARKET_SECRET_KEY: доступен только индекс цен"
)


class DmarketRequestError(MarketplaceRequestError):
    """Безопасное для отображения пользователю описание сбоя DMarket."""


class DmarketAuthError(DmarketRequestError):
    """Ключи отсутствуют, повреждены или отклонены DMarket."""


def item_url(market_hash_name: str) -> str:
    return f"{ITEM_LIST_URL}?{urlencode({'title': market_hash_name})}"


def keys_configured() -> bool:
    return bool(_env("DMARKET_PUBLIC_KEY") and _env("DMARKET_SECRET_KEY"))


def get_aggregated_prices(titles: list[str]) -> dict[str, dict[str, int | None]]:
    """Return best ask/bid and their counts for exact titles.

    Titles DMarket does not know are simply absent from the result.
    """
    unique = list(dict.fromkeys(title for title in titles if title))
    result: dict[str, dict[str, int | None]] = {}
    for start in range(0, len(unique), AGGREGATED_PAGE_SIZE):
        chunk = unique[start:start + AGGREGATED_PAGE_SIZE]
        cursor = ""
        # A chunk never needs more pages than titles; the bound stops a
        # provider that keeps returning a cursor.
        for _page in range(len(chunk)):
            body: dict[str, Any] = {
                "filter": {"game": GAME_ID, "titles": chunk},
                "limit": str(AGGREGATED_PAGE_SIZE),
            }
            if cursor:
                body["cursor"] = cursor
            payload = _request(
                "POST", "/marketplace-api/v1/aggregated-prices",
                body=body, allow_public=True,
            )
            rows = payload.get("aggregatedPrices")
            if not isinstance(rows, list):
                raise DmarketRequestError("DMarket вернул неожиданный формат цен")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("title"), str):
                    continue
                ask_count = _count(row.get("offerCount"))
                bid_count = _count(row.get("orderCount"))
                ask = _money_cents(row.get("offerBestPrice"))
                bid = _money_cents(row.get("orderBestPrice"))
                result[row["title"]] = {
                    "ask_cents": ask if ask_count else None,
                    "ask_count": ask_count,
                    "bid_cents": bid if bid_count else None,
                    "bid_count": bid_count,
                }
            cursor = payload.get("nextCursor") or ""
            if not isinstance(cursor, str) or not cursor or not rows:
                break
    return result


def get_active_listings(
    market_hash_name: str,
    *,
    min_float: float | None = None,
    max_float: float | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Return the cheapest buyable offers for one exact title (signed)."""
    limit = min(max(limit, 1), 50)
    # ``title`` is a prefix filter, and float/attachment filters are applied
    # locally, so a full page is requested whenever something can be dropped.
    params: dict[str, object] = {
        "gameId": GAME_ID,
        "title": market_hash_name,
        "orderBy": "price",
        "orderDir": "asc",
        "limit": OFFERS_PAGE_SIZE,
        "offerType": "all",
        "withImages": "true",
    }
    if min_price_cents is not None:
        params["priceFrom"] = min_price_cents
    if max_price_cents is not None:
        params["priceTo"] = max_price_cents
    payload = _request("GET", "/marketplace-api/v2/offers", query=params)
    items = payload.get("items")
    if not isinstance(items, list):
        raise DmarketRequestError("DMarket вернул неожиданный формат лотов")

    listings: list[dict[str, object]] = []
    for item in items:
        listing = _normalize_offer(item, market_hash_name)
        if listing is None:
            continue
        float_value = listing["float_value"]
        if min_float is not None and (float_value is None or float_value < min_float):
            continue
        if max_float is not None and (float_value is None or float_value > max_float):
            continue
        if has_stickers and not listing["stickers"]:
            continue
        if has_charm and not listing["charms"]:
            continue
        listings.append(listing)
    listings.sort(key=lambda listing: listing["price_cents"])
    return listings[:limit]


def get_buy_orders(market_hash_name: str, *, limit: int = 10) -> list[dict[str, object]]:
    """Return aggregated targets (buy orders) for one exact title (signed)."""
    payload = _request(
        "GET",
        f"/marketplace-api/v1/targets-by-title/{GAME_ID}/{market_hash_name}",
    )
    raw_orders = payload.get("orders")
    if not isinstance(raw_orders, list):
        raise DmarketRequestError("DMarket вернул неожиданный формат заявок")
    orders: list[dict[str, object]] = []
    for raw in raw_orders:
        if not isinstance(raw, dict) or raw.get("title") not in (None, market_hash_name):
            continue
        price_cents = _cents(raw.get("price"))
        quantity = _count(raw.get("amount"))
        if price_cents is None or not quantity:
            continue
        attributes = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
        restricted = {
            key: value for key, value in attributes.items()
            if isinstance(value, str) and value and value.casefold() != "any"
        }
        orders.append({
            "price_cents": price_cents,
            "quantity": quantity,
            "min_float": None,
            "max_float": None,
            # A restricted target matches only some items of this title.
            "attributes": restricted,
        })
    orders.sort(key=lambda order: order["price_cents"], reverse=True)
    return orders[:limit]


def get_sales_history(market_hash_name: str, *, limit: int = 100) -> list[dict[str, object]]:
    """Return the most recent real sales, newest first (signed)."""
    sales: list[dict[str, object]] = []
    for offset in range(0, max(limit, 1), LAST_SALES_PAGE_SIZE):
        payload = _request(
            "GET", "/trade-aggregator/v1/last-sales",
            query={
                "gameId": GAME_ID,
                "title": market_hash_name,
                "limit": LAST_SALES_PAGE_SIZE,
                "offset": offset,
            },
        )
        rows = payload.get("sales")
        if not isinstance(rows, list):
            raise DmarketRequestError("DMarket вернул неожиданный формат продаж")
        for row in rows:
            sale = _normalize_sale(row)
            if sale is not None:
                sales.append(sale)
        if len(rows) < LAST_SALES_PAGE_SIZE:
            break
    sales.sort(key=lambda sale: sale["sold_at"], reverse=True)
    return sales[:limit]


def sign_request(
    method: str, path: str, query: str, body: str, timestamp: str, secret_key_hex: str
) -> str:
    """Build the X-Request-Sign value.

    The unsigned string is method + path (decoded) + ``?query`` (exactly as
    sent) + body + timestamp. The secret is the hex key from the DMarket
    account settings: 64 bytes whose first 32 are the Ed25519 seed.
    """
    try:
        secret = bytes.fromhex(secret_key_hex.strip())
    except ValueError as error:
        raise DmarketAuthError("DMARKET_SECRET_KEY должен быть hex-строкой") from error
    if len(secret) not in (32, 64):
        raise DmarketAuthError("DMARKET_SECRET_KEY имеет неверную длину")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as error:  # pragma: no cover - dependency is in requirements.txt
        raise DmarketAuthError(
            "Для подписи запросов DMarket требуется пакет cryptography"
        ) from error
    unsigned = method.upper() + path + (f"?{query}" if query else "") + body + timestamp
    signature = Ed25519PrivateKey.from_private_bytes(secret[:32]).sign(
        unsigned.encode("utf-8")
    )
    return "dmar ed25519 " + signature.hex()


def _request(
    method: str,
    path: str,
    *,
    query: dict[str, object] | None = None,
    body: dict[str, Any] | None = None,
    allow_public: bool = False,
) -> dict[str, Any]:
    """Send one API request; ``path`` is the decoded route."""
    public_key = _env("DMARKET_PUBLIC_KEY")
    secret_key = _env("DMARKET_SECRET_KEY")
    signed = bool(public_key and secret_key)
    if not signed and not allow_public:
        raise DmarketAuthError(KEYS_MISSING_MESSAGE)

    query_string = urlencode(query or {}, quote_via=quote)
    body_string = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
    headers = {"Accept": "application/json", "User-Agent": "trueROI/0.1"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if signed:
        timestamp = str(int(time.time()))
        headers["X-Api-Key"] = public_key.lower()
        headers["X-Sign-Date"] = timestamp
        headers["X-Request-Sign"] = sign_request(
            method, path, query_string, body_string, timestamp, secret_key
        )
    url = API_URL + quote(path, safe="/") + (f"?{query_string}" if query_string else "")
    request = Request(
        url,
        data=body_string.encode("utf-8") if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code in (401, 403):
            if signed and allow_public:
                # Rejected keys must not take the public price index down.
                return _request_public(method, path, query_string, body_string)
            raise DmarketAuthError(
                f"DMarket отклонил API-ключи (HTTP {error.code})"
            ) from error
        if error.code == 429:
            raise DmarketRequestError("DMarket временно ограничил частоту запросов") from error
        raise DmarketRequestError(
            f"DMarket временно недоступен (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise DmarketRequestError("Не удалось получить данные DMarket") from error
    if not isinstance(payload, dict):
        raise DmarketRequestError("DMarket вернул неожиданный формат ответа")
    return payload


def _request_public(method: str, path: str, query_string: str, body_string: str) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "trueROI/0.1"}
    if body_string:
        headers["Content-Type"] = "application/json"
    request = Request(
        API_URL + quote(path, safe="/") + (f"?{query_string}" if query_string else ""),
        data=body_string.encode("utf-8") if body_string else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise DmarketRequestError(
            f"DMarket временно недоступен (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise DmarketRequestError("Не удалось получить данные DMarket") from error
    if not isinstance(payload, dict):
        raise DmarketRequestError("DMarket вернул неожиданный формат ответа")
    return payload


def _normalize_offer(item: object, market_hash_name: str) -> dict[str, object] | None:
    if not isinstance(item, dict) or item.get("locked") is True:
        return None
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    if attributes.get("title") != market_hash_name:
        return None
    offer_id = item.get("offerId")
    price_cents = _cents(item.get("priceCents"))
    if not isinstance(offer_id, str) or not offer_id or price_cents is None:
        return None
    cs2 = attributes.get("cs2") if isinstance(attributes.get("cs2"), dict) else {}
    return {
        "listing_id": offer_id,
        "price_cents": price_cents,
        "item_url": item_url(market_hash_name),
        "float_value": _float(cs2.get("float")),
        "paint_seed": _int(cs2.get("paintSeed")),
        "paint_index": _int(cs2.get("paintIndex")),
        "stickers": _attachments(cs2.get("stickers"), "Стикер"),
        "charms": _attachments(cs2.get("charms"), "Charm"),
        "created_at": item.get("createdAt") if isinstance(item.get("createdAt"), str) else None,
        "inspect_link": cs2.get("inspectInGameUri") or None,
        "image_url": attributes.get("imageUri") or None,
        "offer_type": item.get("offerType") if isinstance(item.get("offerType"), str) else None,
    }


def _normalize_sale(row: object) -> dict[str, object] | None:
    if not isinstance(row, dict):
        return None
    try:
        amount = Decimal(str(row.get("price")))
        sold_at = datetime.fromtimestamp(int(str(row.get("date"))), tz=timezone.utc)
    except (InvalidOperation, ValueError, OverflowError, OSError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    price_cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not 0 < price_cents <= MAX_PRICE_CENTS:
        return None
    attributes = row.get("offerAttributes") if isinstance(row.get("offerAttributes"), dict) else {}
    return {
        "sold_at": sold_at.isoformat(),
        "price_cents": price_cents,
        "float_value": _float(attributes.get("floatValue")),
        "sale_type": row.get("txOperationType") if isinstance(row.get("txOperationType"), str) else None,
    }


def _attachments(value: object, fallback_name: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [
        {"name": entry.get("name") or fallback_name, "icon_url": entry.get("image") or None}
        for entry in value
        if isinstance(entry, dict)
    ]


def _money_cents(value: object) -> int | None:
    """Parse commonMoney: {"Currency": "USD", "Amount": "2323"} (coins = cents)."""
    if not isinstance(value, dict) or value.get("Currency") not in (None, "", "USD"):
        return None
    return _cents(value.get("Amount"))


def _cents(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        cents = int(str(value))
    except (TypeError, ValueError):
        return None
    return cents if 0 < cents <= MAX_PRICE_CENTS else None


def _count(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        count = int(str(value))
    except (TypeError, ValueError):
        return 0
    return min(count, MAX_PRICE_CENTS) if count > 0 else 0


def _float(value: object) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 1 else None


def _int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()
