import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import MarketPrice

CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"
CSFLOAT_PRICE_LIST_URL = f"{CSFLOAT_LISTINGS_URL}/price-list"
CSFLOAT_HISTORY_URL = "https://csfloat.com/api/v1/history"
CSFLOAT_ITEM_URL = "https://csfloat.com/item"


class CsfloatRequestError(Exception):
    """Безопасное для отображения пользователю описание сбоя CSFloat."""


def get_lowest_price(market_hash_name: str) -> MarketPrice | None:
    """Получает самый дешёвый активный listing конкретного точного предмета.

    Функция намеренно не делает поиск по всем лотам: один вызов — один предмет.
    """
    query = urlencode(
        {
            "market_hash_name": market_hash_name,
            "sort_by": "lowest_price",
            "type": "buy_now",
            "limit": 1,
        }
    )
    api_key = os.getenv("CSFLOAT_API_KEY")
    if not api_key:
        raise CsfloatRequestError("Не настроен CSFLOAT_API_KEY")

    request = Request(
        f"{CSFLOAT_LISTINGS_URL}?{query}",
        headers={
            "Accept": "application/json",
            "Authorization": api_key,
            "User-Agent": "SkinMarketTracker/0.1",
        },
    )

    try:
        listings = _load_json_with_rate_limit_retry(request, timeout=10)
    except HTTPError as error:
        if error.code in (401, 403):
            raise CsfloatRequestError("CSFloat отклонил API-ключ") from error
        if error.code == 429:
            raise CsfloatRequestError("CSFloat временно ограничил частоту запросов") from error
        raise CsfloatRequestError(f"CSFloat временно недоступен (HTTP {error.code})") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CsfloatRequestError("Не удалось получить ответ от CSFloat") from error

    # The documented response is an array. Accept the newer envelope as well so
    # a harmless API response-shape change does not break price loading.
    if isinstance(listings, dict):
        listings = listings.get("data")
    if not isinstance(listings, list) or not listings:
        return None

    listing = listings[0]
    price_cents = listing.get("price")
    listing_id = listing.get("id")
    if not isinstance(price_cents, int) or price_cents < 0:
        return None
    if not isinstance(listing_id, (str, int)):
        return None

    item = listing.get("item") if isinstance(listing.get("item"), dict) else {}
    float_value = item.get("float_value")
    if not isinstance(float_value, (int, float)):
        float_value = None

    return MarketPrice(
        marketplace="CSFloat",
        price_cents=price_cents,
        listing_id=str(listing_id),
        item_url=f"{CSFLOAT_ITEM_URL}/{listing_id}",
        float_value=float_value,
    )


def get_price_index() -> dict[str, dict[str, int]]:
    """Return CSFloat's market-wide minimum-price index keyed by market name."""
    headers = {"Accept": "application/json", "User-Agent": "trueROI/0.3"}
    api_key = os.getenv("CSFLOAT_API_KEY")
    if api_key:
        headers["Authorization"] = api_key
    request = Request(CSFLOAT_PRICE_LIST_URL, headers=headers)

    try:
        payload = _load_json_with_rate_limit_retry(request, timeout=30)
    except HTTPError as error:
        if error.code in (401, 403):
            raise CsfloatRequestError("CSFloat отклонил API-ключ") from error
        if error.code == 429:
            raise CsfloatRequestError("CSFloat временно ограничил частоту запросов") from error
        raise CsfloatRequestError(f"CSFloat временно недоступен (HTTP {error.code})") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CsfloatRequestError("Не удалось получить индекс цен CSFloat") from error

    if not isinstance(payload, list):
        raise CsfloatRequestError("CSFloat вернул неожиданный формат индекса цен")

    result: dict[str, dict[str, int]] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        market_hash_name = entry.get("market_hash_name")
        min_price = entry.get("min_price")
        quantity = entry.get("quantity")
        if not isinstance(market_hash_name, str):
            continue
        if not isinstance(min_price, int) or min_price < 0:
            continue
        result[market_hash_name] = {
            "price_cents": min_price,
            "quantity": quantity if isinstance(quantity, int) and quantity >= 0 else 0,
        }
    if not result:
        raise CsfloatRequestError("Индекс цен CSFloat оказался пустым")
    return result


def get_active_listings(
    market_hash_name: str, *, limit: int = 10
) -> list[dict[str, object]]:
    """Return normalized active buy-now listings for one exact market variant."""
    query = urlencode(
        {
            "market_hash_name": market_hash_name,
            "sort_by": "lowest_price",
            "type": "buy_now",
            "limit": min(max(limit, 1), 10),
        }
    )
    payload = _authenticated_get(
        f"{CSFLOAT_LISTINGS_URL}?{query}",
        error_message="Не удалось получить листинги CSFloat",
    )
    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list):
        raise CsfloatRequestError("CSFloat вернул неожиданный формат листингов")

    listings: list[dict[str, object]] = []
    for raw_listing in payload[:10]:
        if not isinstance(raw_listing, dict):
            continue
        listing_id = raw_listing.get("id")
        price_cents = raw_listing.get("price")
        if not isinstance(listing_id, (str, int)):
            continue
        if not isinstance(price_cents, int) or price_cents < 0:
            continue
        item = raw_listing.get("item")
        if not isinstance(item, dict):
            item = {}
        seller = raw_listing.get("seller")
        if not isinstance(seller, dict):
            seller = {}
        listings.append(
            {
                "listing_id": str(listing_id),
                "price_cents": price_cents,
                "item_url": f"{CSFLOAT_ITEM_URL}/{listing_id}",
                "float_value": _number_or_none(item.get("float_value")),
                "paint_seed": _integer_or_none(item.get("paint_seed")),
                "paint_index": _integer_or_none(item.get("paint_index")),
                "stickers": _normalize_stickers(item.get("stickers")),
                "seller_name": seller.get("username"),
                "seller_online": seller.get("online"),
                "created_at": raw_listing.get("created_at"),
                "inspect_link": item.get("inspect_link"),
            }
        )
    return listings


def get_sales_history(market_hash_name: str) -> list[dict[str, object]]:
    """Return the sales sample exposed by CSFloat for one market variant."""
    payload = _authenticated_get(
        f"{CSFLOAT_HISTORY_URL}/{quote(market_hash_name, safe='')}/sales",
        error_message="Не удалось получить историю продаж CSFloat",
    )
    if isinstance(payload, dict):
        payload = payload.get("data") or payload.get("sales")
    if not isinstance(payload, list):
        raise CsfloatRequestError("CSFloat вернул неожиданный формат истории продаж")

    sales: list[dict[str, object]] = []
    for raw_sale in payload:
        if not isinstance(raw_sale, dict):
            continue
        item = raw_sale.get("item")
        if not isinstance(item, dict):
            item = {}
        sales.append(
            {
                "price_cents": _integer_or_none(
                    raw_sale.get("price", raw_sale.get("price_cents"))
                ),
                "sold_at": raw_sale.get("created_at", raw_sale.get("sold_at")),
                "float_value": _number_or_none(
                    raw_sale.get("float_value", item.get("float_value"))
                ),
            }
        )
    return sales


def _authenticated_get(url: str, *, error_message: str):
    api_key = os.getenv("CSFLOAT_API_KEY")
    if not api_key:
        raise CsfloatRequestError("Не настроен CSFLOAT_API_KEY")
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": api_key,
            "User-Agent": "trueROI/0.4",
        },
    )
    try:
        return _load_json_with_rate_limit_retry(request, timeout=30)
    except HTTPError as error:
        if error.code in (401, 403):
            raise CsfloatRequestError("CSFloat отклонил API-ключ") from error
        if error.code == 429:
            raise CsfloatRequestError("CSFloat временно ограничил частоту запросов") from error
        raise CsfloatRequestError(
            f"CSFloat временно недоступен (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CsfloatRequestError(error_message) from error


def _normalize_stickers(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    stickers = []
    for sticker in value:
        if not isinstance(sticker, dict):
            continue
        stickers.append(
            {
                "name": sticker.get("name") or "Стикер",
                "slot": _integer_or_none(sticker.get("slot")),
                "wear": _number_or_none(sticker.get("wear")),
            }
        )
    return stickers


def _integer_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _load_json_with_rate_limit_retry(request: Request, *, timeout: int):
    """Retry one throttled request, respecting a short Retry-After response."""
    for attempt in range(2):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code != 429 or attempt == 1:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = float(retry_after) if retry_after is not None else 1.0
            except ValueError:
                delay = 1.0
            time.sleep(min(max(delay, 0.25), 3.0))

    raise RuntimeError("unreachable")
