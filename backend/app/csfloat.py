import json
import os
import time
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import MarketPrice

CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"
CSFLOAT_PRICE_LIST_URL = f"{CSFLOAT_LISTINGS_URL}/price-list"
CSFLOAT_HISTORY_URL = "https://csfloat.com/api/v1/history"
CSFLOAT_ITEM_URL = "https://csfloat.com/item"
CSFLOAT_SORTS = {"best_deal", "lowest_price"}


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
                "charms": _normalize_keychains(item.get("keychains")),
                "seller_name": seller.get("username"),
                "seller_online": seller.get("online"),
                "created_at": raw_listing.get("created_at"),
                "inspect_link": item.get("inspect_link"),
            }
        )
    return listings


def search_market_listings(
    *,
    paint_index: int,
    sort_by: str = "best_deal",
    category: int = 0,
    min_float: float | None = None,
    max_float: float | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    limit: int = 30,
) -> list[dict[str, object]]:
    """Search and normalize CSFloat listings for one paint kit."""
    if sort_by not in CSFLOAT_SORTS:
        raise ValueError(f"Unsupported CSFloat sort: {sort_by}")
    query: dict[str, object] = {
        "paint_index": paint_index,
        "sort_by": sort_by,
        "category": category,
        "type": "buy_now",
        "limit": min(max(limit, 1), 50),
    }
    optional = {
        "min_float": min_float,
        "max_float": max_float,
        "min_price": min_price_cents,
        "max_price": max_price_cents,
    }
    query.update({key: value for key, value in optional.items() if value is not None})
    payload = _authenticated_get(
        f"{CSFLOAT_LISTINGS_URL}?{urlencode(query)}",
        error_message="Не удалось получить каталог листингов CSFloat",
    )
    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list):
        raise CsfloatRequestError("CSFloat вернул неожиданный формат листингов")

    listings = []
    for raw_listing in payload:
        listing = _normalize_market_listing(raw_listing)
        if listing is not None:
            listings.append(listing)
    return listings


def get_listing(listing_id: str) -> dict[str, object] | None:
    """Return one normalized listing so dependent checks use its real properties."""
    payload = _authenticated_get(
        f"{CSFLOAT_LISTINGS_URL}/{quote(str(listing_id), safe='')}",
        error_message="Не удалось получить выбранный лот CSFloat",
    )
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    return _normalize_market_listing(payload)


def _normalize_market_listing(raw_listing: object) -> dict[str, object] | None:
    if not isinstance(raw_listing, dict):
        return None
    listing_id = raw_listing.get("id")
    price_cents = _integer_or_none(raw_listing.get("price"))
    item = raw_listing.get("item")
    if not isinstance(listing_id, (str, int)) or price_cents is None or price_cents < 0:
        return None
    if not isinstance(item, dict):
        return None
    reference = raw_listing.get("reference")
    if not isinstance(reference, dict):
        reference = {}
    predicted_price = _integer_or_none(reference.get("predicted_price"))
    deal_percent = None
    if predicted_price and predicted_price > 0:
        deal = (
            (Decimal(predicted_price) - Decimal(price_cents))
            / Decimal(predicted_price)
            * Decimal("100")
        )
        deal_percent = float(deal.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return {
        "listing_id": str(listing_id),
        "item_url": f"{CSFLOAT_ITEM_URL}/{listing_id}",
        "price_cents": price_cents,
        "min_offer_price_cents": _integer_or_none(raw_listing.get("min_offer_price")),
        "created_at": raw_listing.get("created_at"),
        "market_hash_name": item.get("market_hash_name"),
        "item_name": item.get("item_name"),
        "wear_name": item.get("wear_name"),
        "collection": item.get("collection"),
        "image_url": _https_url_or_none(item.get("icon_url")),
        "float_value": _number_or_none(item.get("float_value")),
        "paint_seed": _integer_or_none(item.get("paint_seed")),
        "paint_index": _integer_or_none(item.get("paint_index")),
        "stattrak": bool(item.get("is_stattrak")),
        "souvenir": bool(item.get("is_souvenir")),
        "stickers": _normalize_stickers(item.get("stickers")),
        "charms": _normalize_keychains(item.get("keychains")),
        "predicted_price_cents": predicted_price,
        "base_price_cents": _integer_or_none(reference.get("base_price")),
        "deal_percent": deal_percent,
        "reference_quantity": _integer_or_none(reference.get("quantity")),
        "reference_updated_at": reference.get("last_updated"),
    }


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
    sales.sort(key=lambda sale: str(sale.get("sold_at") or ""), reverse=True)
    return sales


def get_buy_orders(listing_id: str, *, limit: int = 10) -> list[dict[str, object]]:
    """Return normalized buy orders currently matching one concrete listing.

    CSFloat evaluates float and other hybrid conditions against a listing, so
    the listing id is intentionally required instead of only a market name.
    """
    payload = _authenticated_get(
        f"{CSFLOAT_LISTINGS_URL}/{quote(str(listing_id), safe='')}/buy-orders?"
        f"{urlencode({'limit': min(max(limit, 1), 10)})}",
        error_message="Не удалось получить заявки на покупку CSFloat",
    )
    if isinstance(payload, dict):
        payload = payload.get("data") or payload.get("orders")
    if not isinstance(payload, list):
        raise CsfloatRequestError("CSFloat вернул неожиданный формат заявок")

    orders: list[dict[str, object]] = []
    for raw_order in payload[:10]:
        if not isinstance(raw_order, dict):
            continue
        price_cents = _integer_or_none(raw_order.get("price"))
        quantity = _integer_or_none(raw_order.get("qty", raw_order.get("quantity")))
        if price_cents is None or price_cents < 0 or quantity is None or quantity < 1:
            continue
        properties = raw_order.get("hybrid_properties")
        if not isinstance(properties, dict):
            properties = {}
        orders.append(
            {
                "price_cents": price_cents,
                "quantity": quantity,
                "min_float": _number_or_none(properties.get("min_float")),
                "max_float": _number_or_none(properties.get("max_float")),
            }
        )
    return orders


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
        reference = sticker.get("reference")
        if not isinstance(reference, dict):
            reference = {}
        steam_reference = sticker.get("scm")
        if not isinstance(steam_reference, dict):
            steam_reference = {}
        stickers.append(
            {
                "name": sticker.get("name") or "Стикер",
                "slot": _integer_or_none(sticker.get("slot")),
                "wear": _number_or_none(sticker.get("wear")),
                "icon_url": _https_url_or_none(sticker.get("icon_url")),
                "csfloat_price_cents": _integer_or_none(reference.get("price")),
                "csfloat_quantity": _integer_or_none(reference.get("quantity")),
                "price_updated_at": reference.get("updated_at"),
                "steam_price_cents": _integer_or_none(steam_reference.get("price")),
            }
        )
    return stickers


def _normalize_keychains(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    keychains = []
    for keychain in value:
        if not isinstance(keychain, dict):
            continue
        reference = keychain.get("reference")
        if not isinstance(reference, dict):
            reference = {}
        keychains.append(
            {
                "name": keychain.get("name") or "Charm",
                "slot": _integer_or_none(keychain.get("slot")),
                "pattern": _integer_or_none(keychain.get("pattern")),
                "icon_url": _https_url_or_none(keychain.get("icon_url")),
                "csfloat_price_cents": _integer_or_none(reference.get("price")),
                "csfloat_quantity": _integer_or_none(reference.get("quantity")),
                "price_updated_at": reference.get("updated_at"),
            }
        )
    return keychains


def _https_url_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.startswith("https://"):
        return value
    return None


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
