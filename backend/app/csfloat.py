import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import MarketPrice

CSFLOAT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"


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
        with urlopen(request, timeout=10) as response:
            listings = json.load(response)
    except HTTPError as error:
        if error.code in (401, 403):
            raise CsfloatRequestError("CSFloat отклонил API-ключ") from error
        raise CsfloatRequestError(f"CSFloat временно недоступен (HTTP {error.code})") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CsfloatRequestError("Не удалось получить ответ от CSFloat") from error

    if not isinstance(listings, list) or not listings:
        return None

    price_cents = listings[0].get("price")
    if not isinstance(price_cents, int) or price_cents < 0:
        return None

    return MarketPrice(
        marketplace="CSFloat",
        price_cents=price_cents,
        item_url=f"https://csfloat.com/search?{urlencode({'market_hash_name': market_hash_name})}",
    )
