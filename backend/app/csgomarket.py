"""Market.CSGO adapter with public market data and rate-limited private calls."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import MarketPrice


CSGOMARKET_API_URL = "https://market.csgo.com/api/v2"
CSGOMARKET_PRICE_LIST_URL = f"{CSGOMARKET_API_URL}/prices/USD.json"
CSGOMARKET_HISTORY_INDEX_URL = f"{CSGOMARKET_API_URL}/full-history/all.json"
CSGOMARKET_ITEM_URL = "https://market.csgo.com"
MARKETPLACE = "CSGO Market"
DEFAULT_MAX_PRIVATE_REQUESTS_PER_SECOND = 0.5
MAX_SAFE_PRIVATE_REQUESTS_PER_SECOND = 0.5
DEFAULT_HISTORY_INDEX_TTL_SECONDS = 3600

_private_rate_lock = threading.Lock()
_next_private_request_at = 0.0
_history_index_lock = threading.Lock()
_history_index: dict[str, int] | None = None
_history_index_fetched_at = 0.0


class CsgoMarketRequestError(Exception):
    """Safe, user-facing description of a Market.CSGO request failure."""


def get_price_index() -> dict[str, dict[str, int]]:
    """Return minimum public USD prices keyed by exact Steam market hash name."""
    payload = _request_json(CSGOMARKET_PRICE_LIST_URL)
    if payload.get("success") is not True or payload.get("currency") != "USD":
        raise CsgoMarketRequestError(
            "CSGO Market не подтвердил успешный ответ в валюте USD"
        )
    items = payload.get("items")
    if not isinstance(items, list):
        raise CsgoMarketRequestError(
            "CSGO Market вернул неожиданный формат индекса цен"
        )

    result: dict[str, dict[str, int]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        market_hash_name = item.get("market_hash_name")
        price_cents = _usd_to_cents(item.get("price"))
        if not isinstance(market_hash_name, str) or not market_hash_name:
            continue
        if price_cents is None:
            continue
        result[market_hash_name] = {
            "price_cents": price_cents,
            "quantity": _non_negative_int(item.get("volume")) or 0,
        }

    if not result:
        raise CsgoMarketRequestError("Индекс цен CSGO Market оказался пустым")
    return result


def get_lowest_price(market_hash_name: str) -> MarketPrice | None:
    """Return the current best public offer for one exact market variant."""
    entry = get_price_index().get(market_hash_name)
    if entry is None:
        return None
    return MarketPrice(
        marketplace=MARKETPLACE,
        price_cents=entry["price_cents"],
        item_url=_item_url(market_hash_name),
        quantity=entry["quantity"],
    )


def get_active_listings(
    market_hash_name: str,
    *,
    limit: int = 10,
    with_stickers: bool = False,
) -> list[dict[str, object]]:
    """Return normalized concrete listings from the private item search."""
    payload = _request_json(
        f"{CSGOMARKET_API_URL}/search-item-by-hash-name-specific",
        params={
            "hash_name": market_hash_name,
            "with_stickers": int(with_stickers),
            "lang": "en",
        },
        authenticated=True,
    )
    _require_successful_usd_payload(payload, "листингов")
    data = payload.get("data")
    if not isinstance(data, list):
        raise CsgoMarketRequestError(
            "CSGO Market вернул неожиданный формат листингов"
        )

    listings = []
    for item in data:
        listing = _normalize_listing(item)
        if listing is not None:
            listings.append(listing)
    listings.sort(key=lambda listing: int(listing["price_cents"]))
    return listings[: min(max(limit, 1), 50)]


def get_order_book(
    market_hash_name: str,
    *,
    phase: str | None = None,
    limit: int = 10,
) -> dict[str, list[dict[str, int]]]:
    """Return normalized bid/ask levels for one market name."""
    params: dict[str, object] = {"hash_name": market_hash_name}
    if phase:
        params["phase"] = phase
    payload = _request_json(
        f"{CSGOMARKET_API_URL}/bid-ask",
        params=params,
        authenticated=True,
    )
    if payload.get("success") is False:
        error_code = payload.get("error")
        suffix = f" ({error_code})" if isinstance(error_code, (str, int)) else ""
        raise CsgoMarketRequestError(
            f"CSGO Market не смог загрузить стакан{suffix}"
        )
    if payload.get("currency") != "USD":
        raise CsgoMarketRequestError("CSGO Market вернул стакан не в валюте USD")
    bids = _normalize_order_levels(payload.get("bid"), descending=True, limit=limit)
    asks = _normalize_order_levels(payload.get("ask"), descending=False, limit=limit)
    return {"buy_orders": bids, "sell_orders": asks}


def get_buy_orders(
    market_hash_name: str, *, phase: str | None = None, limit: int = 10
) -> list[dict[str, int]]:
    """Return the bid side used by trueROI's quick-sell analytics."""
    return get_order_book(market_hash_name, phase=phase, limit=limit)["buy_orders"]


def get_sales_history(
    market_hash_name: str, *, limit: int = 200
) -> list[dict[str, object]]:
    """Return recent public sales without spending the private API allowance."""
    item_id = _get_history_index().get(market_hash_name)
    if item_id is None:
        return []
    payload = _request_json(
        f"{CSGOMARKET_API_URL}/full-history/{quote(str(item_id), safe='')}.json"
    )
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("history"), list):
        raise CsgoMarketRequestError(
            "CSGO Market вернул неожиданный формат истории продаж"
        )

    sales = []
    for row in data["history"]:
        if not isinstance(row, list) or len(row) < 3:
            continue
        timestamp = _non_negative_int(row[0])
        price_cents = _usd_to_cents(row[2])
        if timestamp is None or price_cents is None:
            continue
        sold_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        sales.append(
            {
                "price_cents": price_cents,
                "sold_at": sold_at.isoformat().replace("+00:00", "Z"),
                "float_value": None,
            }
        )
    sales.sort(key=lambda sale: str(sale["sold_at"]), reverse=True)
    return sales[: min(max(limit, 1), 1000)]


def _get_history_index() -> dict[str, int]:
    global _history_index, _history_index_fetched_at

    ttl_seconds = _positive_float_env(
        "CSGOMARKET_HISTORY_INDEX_TTL_SECONDS",
        DEFAULT_HISTORY_INDEX_TTL_SECONDS,
    )
    with _history_index_lock:
        now = time.monotonic()
        if (
            _history_index is not None
            and now - _history_index_fetched_at < ttl_seconds
        ):
            return _history_index
        payload = _request_json(CSGOMARKET_HISTORY_INDEX_URL)
        raw_history = payload.get("history")
        if not isinstance(raw_history, dict):
            raise CsgoMarketRequestError(
                "CSGO Market вернул неожиданный индекс истории продаж"
            )
        result = {
            name: item_id
            for name, raw_id in raw_history.items()
            if isinstance(name, str)
            and (item_id := _non_negative_int(raw_id)) is not None
        }
        if not result:
            raise CsgoMarketRequestError("Индекс истории CSGO Market оказался пустым")
        _history_index = result
        _history_index_fetched_at = now
        return result


def _normalize_listing(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    listing_id = value.get("id")
    market_hash_name = value.get("market_hash_name")
    price_cents = _milliusd_to_cents(value.get("price"))
    if not isinstance(listing_id, (str, int)) or not isinstance(
        market_hash_name, str
    ):
        return None
    if price_cents is None:
        return None
    extra = value.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    return {
        "listing_id": str(listing_id),
        "item_url": _item_url(market_hash_name),
        "price_cents": price_cents,
        "market_hash_name": market_hash_name,
        "float_value": _number_or_none(extra.get("float")),
        "phase": extra.get("phase") if isinstance(extra.get("phase"), str) else None,
        "paint_seed": None,
        "paint_index": None,
        "stickers": _normalize_sticker_ids(extra.get("stickers")),
        "charms": [],
        "stattrak": market_hash_name.startswith("StatTrak™ "),
        "souvenir": market_hash_name.startswith("Souvenir "),
        "seller_steam_level": _non_negative_int(
            value.get("seller_steam_level", extra.get("seller_steam_level"))
        ),
        "source": value.get("source"),
    }


def _normalize_order_levels(
    value: object, *, descending: bool, limit: int
) -> list[dict[str, int]]:
    if not isinstance(value, list):
        raise CsgoMarketRequestError("CSGO Market вернул неожиданный формат стакана")
    levels = []
    for row in value:
        if not isinstance(row, dict):
            continue
        price_cents = _usd_to_cents(row.get("price"))
        quantity = _non_negative_int(row.get("total"))
        if price_cents is None or quantity is None or quantity < 1:
            continue
        levels.append({"price_cents": price_cents, "quantity": quantity})
    levels.sort(key=lambda level: level["price_cents"], reverse=descending)
    return levels[: min(max(limit, 1), 50)]


def _normalize_sticker_ids(value: object) -> list[dict[str, object]]:
    if not isinstance(value, str) or not value:
        return []
    stickers = []
    for slot, sticker_id in enumerate(value.split("|")):
        if not sticker_id:
            continue
        stickers.append(
            {
                "id": sticker_id,
                "name": f"Sticker #{sticker_id}",
                "slot": slot,
                "wear": None,
                "icon_url": None,
            }
        )
    return stickers


def _request_json(
    url: str,
    *,
    params: dict[str, object] | None = None,
    authenticated: bool = False,
) -> dict[str, object]:
    query = dict(params or {})
    if authenticated:
        api_key = os.getenv("CSGOMARKET_API_KEY")
        if not api_key:
            raise CsgoMarketRequestError("Не настроен CSGOMARKET_API_KEY")
        query["key"] = api_key
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "trueROI/1.0"},
    )
    try:
        payload = _load_json_with_rate_limit_retry(
            request, timeout=30, authenticated=authenticated
        )
    except HTTPError as error:
        if error.code in (401, 403):
            raise CsgoMarketRequestError("CSGO Market отклонил API-ключ") from error
        if error.code == 429:
            raise CsgoMarketRequestError(
                "CSGO Market временно ограничил частоту запросов"
            ) from error
        raise CsgoMarketRequestError(
            f"CSGO Market временно недоступен (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CsgoMarketRequestError(
            "Не удалось получить ответ от CSGO Market"
        ) from error
    if not isinstance(payload, dict):
        raise CsgoMarketRequestError("CSGO Market вернул неожиданный формат ответа")
    return payload


def _require_successful_usd_payload(
    payload: dict[str, object], response_name: str
) -> None:
    if payload.get("success") is not True:
        error_code = payload.get("error")
        suffix = f" ({error_code})" if isinstance(error_code, (str, int)) else ""
        raise CsgoMarketRequestError(
            f"CSGO Market не смог загрузить {response_name}{suffix}"
        )
    if payload.get("currency") != "USD":
        raise CsgoMarketRequestError(
            f"CSGO Market вернул {response_name} не в валюте USD"
        )


def _wait_for_private_request_slot() -> None:
    """Space all private calls process-wide so no one-second window exceeds 4."""
    global _next_private_request_at

    configured_rate = _positive_float_env(
        "CSGOMARKET_MAX_REQUESTS_PER_SECOND",
        DEFAULT_MAX_PRIVATE_REQUESTS_PER_SECOND,
    )
    safe_rate = min(configured_rate, MAX_SAFE_PRIVATE_REQUESTS_PER_SECOND)
    # A small safety margin prevents boundary jitter from placing five starts
    # into one rolling second when the configured ceiling is four.
    interval = 1.0 / safe_rate + 0.01
    with _private_rate_lock:
        now = time.monotonic()
        scheduled_at = max(now, _next_private_request_at)
        _next_private_request_at = scheduled_at + interval
    delay = scheduled_at - now
    if delay > 0:
        time.sleep(delay)


def _load_json_with_rate_limit_retry(
    request: Request, *, timeout: int, authenticated: bool = False
):
    """Retry one throttled request; private retries also pass the rate limiter."""
    for attempt in range(2):
        if authenticated:
            _wait_for_private_request_slot()
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


def _item_url(market_hash_name: str) -> str:
    return f"{CSGOMARKET_ITEM_URL}/{quote(market_hash_name, safe='')}"


def _usd_to_cents(value: object) -> int | None:
    amount = _decimal_or_none(value)
    if amount is None or amount < 0:
        return None
    return int(
        (amount * Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _milliusd_to_cents(value: object) -> int | None:
    amount = _decimal_or_none(value)
    if amount is None or amount < 0:
        return None
    return int((amount / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _decimal_or_none(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def _number_or_none(value: object) -> float | None:
    amount = _decimal_or_none(value)
    return float(amount) if amount is not None else None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value) if isinstance(value, (str, int)) else None
    except ValueError:
        return None
    return number if number is not None and number >= 0 else None


def _positive_float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return float(default)
    return value if value > 0 else float(default)
