"""WhiteMarket integration via the Partner GraphQL API.

Everything here goes through WhiteMarket's Partner GraphQL endpoint
(api.white.market/graphql/partner), which requires a Partner Token
(WHITEMARKET_PARTNER_TOKEN) — issued by WhiteMarket outside of any
self-service flow, exchanged for a short-lived access token per the
Partner docs' auth flow. Without a configured token, every call here
raises WhitemarketRequestError.

WhiteMarket does have a public buy-order book (order_list, confirmed live —
other users' orders come back with isMy: false), so quick-sell here mirrors
CSFloat's. There is, however, no market-wide public sales history: deal_history
only returns the authenticated partner account's own deals (confirmed live —
empty even with no filters at all), so there is still no WhiteMarket
equivalent of csfloat's get_sales_history() / liquidity score.
"""

import json
import os
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import MarketplaceRequestError

WHITEMARKET_ITEM_URL = "https://white.market/item"
WHITEMARKET_GRAPHQL_URL = "https://api.white.market/graphql/partner"

# Partner docs: the exchanged access token has a 24-hour lifetime. Refresh a
# little early so a request never races the exact expiry moment.
ACCESS_TOKEN_TTL_SECONDS = 23 * 60 * 60

_LISTINGS_QUERY = """
query($search: MarketProductSearchInput!, $first: Int!) {
  market_list(search: $search, forwardPagination: {first: $first}) {
    totalCount
    edges {
      node {
        id
        price { value currency }
        slug
        createdAt
        item {
          ... on CSGOInventoryItem {
            float
            paintIndex
            paintSeed
            link
            stickers { name title icon }
            charms { name title icon }
            description { icon iconLarge name }
          }
        }
      }
    }
  }
}
"""


class WhitemarketRequestError(MarketplaceRequestError):
    """Безопасное для отображения пользователю описание сбоя WhiteMarket."""


def get_cheapest_listing(market_hash_name: str) -> dict[str, object] | None:
    """Return the single cheapest live listing for one exact market name.

    Includes ``quantity`` (total active listings for this exact name),
    taken from the same search's totalCount so no second request is needed.
    """
    listings = get_active_listings(market_hash_name, limit=1, _include_total=True)
    return listings[0] if listings else None


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
    _include_total: bool = False,
) -> list[dict[str, object]]:
    """Return live active listings for one exact market_hash_name.

    Unlike CSFloat, WhiteMarket's market_hash_name already encodes the wear
    (e.g. "AK-47 | Redline (Field-Tested)"), so this searches by name
    directly — no paint_index + float-range translation is needed. Requires
    WHITEMARKET_PARTNER_TOKEN; raises WhitemarketRequestError without it.
    """
    search: dict[str, object] = {
        "appId": "CSGO",
        "nameHash": market_hash_name,
        "sort": {"field": "PRICE", "type": "ASC"},
    }
    if min_float is not None:
        search["csgoFloatFrom"] = str(min_float)
    if max_float is not None:
        search["csgoFloatTo"] = str(max_float)
    if min_price_cents is not None or max_price_cents is not None:
        price_range: dict[str, object] = {}
        if min_price_cents is not None:
            price_range["from"] = {"value": _cents_to_decimal_str(min_price_cents), "currency": "USD"}
        if max_price_cents is not None:
            price_range["to"] = {"value": _cents_to_decimal_str(max_price_cents), "currency": "USD"}
        search["price"] = price_range
    if has_stickers:
        search["csgoStickers"] = True
    if has_charm:
        search["csgoCharm"] = True

    data = _graphql_request(
        _LISTINGS_QUERY, {"search": search, "first": min(max(limit, 1), 50)}
    )
    market_list = data.get("market_list") or {}
    total_count = market_list.get("totalCount") if isinstance(market_list, dict) else None
    edges = market_list.get("edges") if isinstance(market_list, dict) else None
    listings = []
    for edge in edges or []:
        listing = _normalize_listing(edge.get("node") if isinstance(edge, dict) else None)
        if listing is None:
            continue
        if _include_total:
            listing["quantity"] = total_count if isinstance(total_count, int) else None
        listings.append(listing)
    return listings


_ORDER_LIST_QUERY = """
query($search: MarketOrderSearchInput!, $first: Int!) {
  order_list(search: $search, forwardPagination: {first: $first}) {
    edges {
      node {
        nameHash
        quantity
        price { value currency }
        params { param value }
      }
    }
  }
}
"""


def get_buy_orders(market_hash_name: str, *, limit: int = 10) -> list[dict[str, object]]:

    data = _graphql_request(
        _ORDER_LIST_QUERY,
        {
            "search": {
                "appId": "CSGO",
                "nameHash": market_hash_name,
                "sort": {"field": "PRICE", "type": "DESC"},
            },
            "first": 50,
        },
    )
    edges = ((data.get("order_list") or {}).get("edges")) or []
    orders: list[dict[str, object]] = []
    for edge in edges:
        order = _normalize_order(
            edge.get("node") if isinstance(edge, dict) else None, market_hash_name
        )
        if order is not None:
            orders.append(order)
        if len(orders) >= limit:
            break
    return orders


def _normalize_order(node: object, market_hash_name: str) -> dict[str, object] | None:
    if not isinstance(node, dict) or node.get("nameHash") != market_hash_name:
        return None
    price = node.get("price") if isinstance(node.get("price"), dict) else {}
    price_cents = (
        _price_to_cents(price.get("value")) if isinstance(price.get("value"), str) else None
    )
    quantity = node.get("quantity")
    if price_cents is None or not isinstance(quantity, int) or quantity < 1:
        return None

    min_float = None
    max_float = None
    for param in node.get("params") or []:
        if not isinstance(param, dict) or param.get("param") != "CSGO_FLOAT":
            continue
        value = param.get("value")
        if isinstance(value, list) and len(value) == 2:
            min_float = _float_from_str(value[0])
            max_float = _float_from_str(value[1])

    return {
        "price_cents": price_cents,
        "quantity": quantity,
        "min_float": min_float,
        "max_float": max_float,
    }


_access_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}


def _get_access_token(*, force_refresh: bool = False) -> str:
    """Return a cached Partner API access token, exchanging one if needed."""
    if (
        not force_refresh
        and _access_token_cache["token"]
        and time.time() < _access_token_cache["expires_at"]
    ):
        return _access_token_cache["token"]

    partner_token = os.getenv("WHITEMARKET_PARTNER_TOKEN")
    if not partner_token:
        raise WhitemarketRequestError("Не настроен WHITEMARKET_PARTNER_TOKEN")

    request = Request(
        WHITEMARKET_GRAPHQL_URL,
        data=json.dumps({"query": "mutation { auth_token { accessToken } }"}).encode(
            "utf-8"
        ),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-partner-token": partner_token,
            "User-Agent": "trueROI/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise WhitemarketRequestError(
            f"WhiteMarket отклонил partner token (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WhitemarketRequestError("Не удалось авторизоваться в WhiteMarket") from error

    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        raise WhitemarketRequestError(
            "WhiteMarket отклонил partner token: "
            + "; ".join(str(e.get("message", "")) for e in errors if isinstance(e, dict))
        )
    data = payload.get("data") if isinstance(payload, dict) else None
    token = (
        (data or {}).get("auth_token", {}).get("accessToken")
        if isinstance(data, dict)
        else None
    )
    if not isinstance(token, str) or not token:
        raise WhitemarketRequestError("WhiteMarket не вернул access token")

    _access_token_cache["token"] = token
    _access_token_cache["expires_at"] = time.time() + ACCESS_TOKEN_TTL_SECONDS
    return token


def _graphql_request(
    query: str, variables: dict[str, object], *, _retry: bool = True
) -> dict[str, object]:
    access_token = _get_access_token()
    request = Request(
        WHITEMARKET_GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "trueROI/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise WhitemarketRequestError(
            f"WhiteMarket временно недоступен (HTTP {error.code})"
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise WhitemarketRequestError("Не удалось получить данные WhiteMarket") from error

    if not isinstance(payload, dict):
        raise WhitemarketRequestError("WhiteMarket вернул неожиданный формат ответа")

    error_messages = [
        str(e.get("message", "")) for e in payload.get("errors") or [] if isinstance(e, dict)
    ]
    warning_messages = [
        str(w.get("message", ""))
        for w in (payload.get("extensions") or {}).get("warnings") or []
        if isinstance(w, dict)
    ]
    if error_messages or warning_messages:
        all_messages = error_messages + warning_messages
        # A stale/expired access token surfaces as one of these; refresh once
        # and retry, rather than surfacing an avoidable error to the user.
        if _retry and any(
            "expired" in m.lower() or "denied" in m.lower() for m in all_messages
        ):
            _get_access_token(force_refresh=True)
            return _graphql_request(query, variables, _retry=False)
        combined = "; ".join(m for m in all_messages if m)
        raise WhitemarketRequestError(
            f"WhiteMarket отклонил запрос: {combined}" if combined else "WhiteMarket отклонил запрос"
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise WhitemarketRequestError("WhiteMarket вернул неожиданный формат ответа")
    return data


def _normalize_listing(node: object) -> dict[str, object] | None:
    if not isinstance(node, dict):
        return None
    listing_id = node.get("id")
    price = node.get("price") if isinstance(node.get("price"), dict) else {}
    price_cents = (
        _price_to_cents(price.get("value")) if isinstance(price.get("value"), str) else None
    )
    if not isinstance(listing_id, str) or price_cents is None:
        return None

    slug = node.get("slug")
    item = node.get("item") if isinstance(node.get("item"), dict) else {}
    description = item.get("description") if isinstance(item.get("description"), dict) else {}

    return {
        "listing_id": listing_id,
        "price_cents": price_cents,
        "item_url": f"{WHITEMARKET_ITEM_URL}/{slug}" if isinstance(slug, str) else None,
        "float_value": _float_from_str(item.get("float")),
        "paint_seed": _int_from_str(item.get("paintSeed")),
        "paint_index": _int_from_str(item.get("paintIndex")),
        "stickers": _normalize_stickers(item.get("stickers")),
        "charms": _normalize_charms(item.get("charms")),
        "created_at": node.get("createdAt"),
        "inspect_link": item.get("link"),
        "image_url": description.get("iconLarge") or description.get("icon"),
    }


def _normalize_stickers(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    stickers = []
    for sticker in value:
        if not isinstance(sticker, dict):
            continue
        stickers.append(
            {
                "name": sticker.get("title") or sticker.get("name") or "Стикер",
                "icon_url": sticker.get("icon"),
            }
        )
    return stickers


def _normalize_charms(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    charms = []
    for charm in value:
        if not isinstance(charm, dict):
            continue
        charms.append(
            {
                "name": charm.get("title") or charm.get("name") or "Charm",
                "icon_url": charm.get("icon"),
            }
        )
    return charms


def _price_to_cents(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        cents = (Decimal(value) * 100).to_integral_value()
    except InvalidOperation:
        return None
    cents_int = int(cents)
    return cents_int if cents_int >= 0 else None


def _cents_to_decimal_str(cents: int) -> str:
    return str((Decimal(cents) / 100).quantize(Decimal("0.01")))


def _float_from_str(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int_from_str(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except ValueError:
        return None
