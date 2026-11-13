"""Tradeit.gg store prices and items.

Tradeit.gg publishes no developer API. This adapter reads the JSON endpoint
its own storefront calls, ``/api/v2/inventory/data``, without authentication
(verified 12 November 2026). It is undocumented and can change without
notice, so every field is validated and a changed shape becomes a provider
error rather than a wrong price.

* ``searchValue=<text>`` returns one row per item name ("group") with the
  store price and, in ``counts``, how many items the group holds.
* ``groupId=<id>`` returns the individual items of one group with float,
  pattern and stickers.

``storePrice`` is the cash price in USD cents. ``price``/``sitePrice`` is the
inflated value used for item-for-item trades and is never used here.
Tradeit.gg is modelled as buy-only: what it pays for a user's item depends on
that user's inventory and is not exposed by this endpoint.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .base import MarketplaceRequestError


INVENTORY_URL = "https://tradeit.gg/api/v2/inventory/data"
STORE_URL = "https://tradeit.gg/csgo/store"
STEAM_IMAGE_URL = "https://community.akamai.steamstatic.com/economy/image/"
GAME_ID = 730
SEARCH_PAGE_SIZE = 100
GROUP_PAGE_SIZE = 100
MAX_PRICE_CENTS = 2_147_483_647  # PostgreSQL INTEGER


class TradeitRequestError(MarketplaceRequestError):
    """Безопасное для отображения пользователю описание сбоя Tradeit.gg."""


def item_url(market_hash_name: str) -> str:
    return f"{STORE_URL}?{urlencode({'search': market_hash_name})}"


def search_groups(query: str) -> dict[str, dict[str, int]]:
    """Return store price, stock and group id for every item name matching a text query."""
    payload = _request({
        "gameId": GAME_ID, "offset": 0, "limit": SEARCH_PAGE_SIZE, "searchValue": query,
    })
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    groups: dict[str, dict[str, int]] = {}
    for item in _items(payload):
        name = item.get("name")
        group_id = item.get("groupId")
        price_cents = _cents(item.get("storePrice"))
        if (not isinstance(name, str) or not name or price_cents is None
                or isinstance(group_id, bool) or not isinstance(group_id, int)):
            continue
        quantity = counts.get(str(group_id))
        quantity = quantity if isinstance(quantity, int) and not isinstance(quantity, bool) else 0
        if quantity < 1:
            continue
        # The same name can appear once per group; keep the cheapest.
        known = groups.get(name)
        if known is None or price_cents < known["price_cents"]:
            groups[name] = {"price_cents": price_cents, "quantity": quantity, "group_id": group_id}
    return groups


def get_group_items(
    group_id: int,
    market_hash_name: str,
    *,
    min_float: float | None = None,
    max_float: float | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    has_stickers: bool = False,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Return the cheapest individual store items of one group, filtered locally."""
    payload = _request({
        "gameId": GAME_ID, "groupId": group_id, "offset": 0, "limit": GROUP_PAGE_SIZE,
    })
    listings: list[dict[str, object]] = []
    for item in _items(payload):
        listing = _normalize_item(item, market_hash_name)
        if listing is None:
            continue
        float_value = listing["float_value"]
        price_cents = listing["price_cents"]
        if min_float is not None and (float_value is None or float_value < min_float):
            continue
        if max_float is not None and (float_value is None or float_value > max_float):
            continue
        if min_price_cents is not None and price_cents < min_price_cents:
            continue
        if max_price_cents is not None and price_cents > max_price_cents:
            continue
        if has_stickers and not listing["stickers"]:
            continue
        listings.append(listing)
    listings.sort(key=lambda listing: (listing["price_cents"], listing["float_value"] or 0))
    return listings[:max(limit, 1)]


def _request(params: dict[str, object]) -> dict[str, Any]:
    request = Request(
        f"{INVENTORY_URL}?{urlencode(params, quote_via=quote)}",
        headers={"Accept": "application/json", "User-Agent": "trueROI/0.1"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 429:
            raise TradeitRequestError("Tradeit.gg временно ограничил частоту запросов") from error
        if error.code in (401, 403):
            raise TradeitRequestError(
                f"Tradeit.gg закрыл доступ к данным магазина (HTTP {error.code})"
            ) from error
        raise TradeitRequestError(
            f"Tradeit.gg временно недоступен (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise TradeitRequestError("Не удалось получить данные Tradeit.gg") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise TradeitRequestError("Tradeit.gg вернул неожиданный формат ответа")
    return payload


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in payload["items"] if isinstance(item, dict)]


def _normalize_item(item: dict[str, Any], market_hash_name: str) -> dict[str, object] | None:
    if item.get("name") != market_hash_name:
        return None
    asset_id = item.get("assetId")
    price_cents = _cents(item.get("storePrice"))
    if not isinstance(asset_id, (str, int)) or isinstance(asset_id, bool) or price_cents is None:
        return None
    float_value = item.get("floatValue")
    if isinstance(float_value, bool) or not isinstance(float_value, (int, float)) or not 0 <= float_value <= 1:
        float_value = None
    pattern = item.get("patternIndex")
    paint_index = item.get("paintIndex")
    image = item.get("imgURL")
    stickers = [
        # Sticker image paths are relative to an undocumented host, so only names are kept.
        {"name": sticker["name"], "icon_url": None}
        for sticker in item.get("stickers") or []
        if isinstance(sticker, dict) and isinstance(sticker.get("name"), str) and sticker["name"]
    ]
    return {
        "listing_id": str(asset_id),
        "price_cents": price_cents,
        "item_url": item_url(market_hash_name),
        "float_value": float(float_value) if float_value is not None else None,
        "paint_seed": pattern if isinstance(pattern, int) and not isinstance(pattern, bool) else None,
        "paint_index": paint_index if isinstance(paint_index, int) and not isinstance(paint_index, bool) else None,
        "stickers": stickers,
        "charms": [],
        "image_url": STEAM_IMAGE_URL + image if isinstance(image, str) and image else None,
    }


def _cents(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 < value <= MAX_PRICE_CENTS else None
