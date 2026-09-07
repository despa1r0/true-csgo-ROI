import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from backend.app import csgomarket


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_normalizes_public_usd_price_index(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "success": True,
                "time": 1787598262,
                "currency": "USD",
                "items": [
                    {
                        "market_hash_name": "AK-47 | Redline (Field-Tested)",
                        "volume": "95",
                        "price": "14.625",
                    },
                    {"market_hash_name": "Broken", "price": "not-a-price"},
                ],
            }
        )

    monkeypatch.setattr(csgomarket, "urlopen", fake_urlopen)

    assert csgomarket.get_price_index() == {
        "AK-47 | Redline (Field-Tested)": {
            "price_cents": 1463,
            "quantity": 95,
        }
    }
    assert captured["request"].full_url.endswith("/api/v2/prices/USD.json")
    assert captured["request"].get_header("Authorization") is None
    assert captured["timeout"] == 30


def test_returns_normalized_market_price_with_item_link(monkeypatch):
    monkeypatch.setattr(
        csgomarket,
        "get_price_index",
        lambda: {
            "StatTrak™ AK-47 | Redline (Field-Tested)": {
                "price_cents": 4321,
                "quantity": 12,
            }
        },
    )

    price = csgomarket.get_lowest_price(
        "StatTrak™ AK-47 | Redline (Field-Tested)"
    )

    assert price is not None
    assert price.marketplace == "CSGO Market"
    assert price.price_cents == 4321
    assert price.quantity == 12
    assert price.listing_id is None
    assert price.item_url == (
        "https://market.csgo.com/"
        "StatTrak%E2%84%A2%20AK-47%20%7C%20Redline%20%28Field-Tested%29"
    )


def test_returns_none_for_missing_market_name(monkeypatch):
    monkeypatch.setattr(csgomarket, "get_price_index", lambda: {})

    assert csgomarket.get_lowest_price("Missing skin") is None


def test_rejects_unexpected_currency(monkeypatch):
    monkeypatch.setattr(
        csgomarket,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            {"success": True, "currency": "RUB", "items": []}
        ),
    )

    with pytest.raises(csgomarket.CsgoMarketRequestError, match="USD"):
        csgomarket.get_price_index()


def test_retries_one_rate_limited_request(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "0"},
                BytesIO(b""),
            )
        return FakeResponse(
            {
                "success": True,
                "currency": "USD",
                "items": [
                    {"market_hash_name": "Test item", "volume": "1", "price": "1"}
                ],
            }
        )

    monkeypatch.setattr(csgomarket, "urlopen", fake_urlopen)
    monkeypatch.setattr(csgomarket.time, "sleep", lambda _seconds: None)

    assert csgomarket.get_price_index()["Test item"]["price_cents"] == 100
    assert len(calls) == 2


def test_private_listing_search_uses_key_and_normalizes_milliusd(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(
            {
                "success": True,
                "currency": "USD",
                "data": [
                    {
                        "id": 521320033,
                        "market_hash_name": "AWP | Worm God (Factory New)",
                        "price": 35735,
                        "source": "STEAM",
                        "extra": {
                            "float": "0.061443410813808",
                            "phase": "",
                            "seller_steam_level": 12,
                            "stickers": "13026426608|13026426609",
                        },
                    }
                ],
            }
        )

    monkeypatch.setenv("CSGOMARKET_API_KEY", "private-test-key")
    monkeypatch.setattr(csgomarket, "urlopen", fake_urlopen)
    monkeypatch.setattr(csgomarket, "_wait_for_private_request_slot", lambda: None)

    listings = csgomarket.get_active_listings(
        "AWP | Worm God (Factory New)", limit=10
    )

    query = parse_qs(urlparse(captured["request"].full_url).query)
    assert query["key"] == ["private-test-key"]
    assert query["hash_name"] == ["AWP | Worm God (Factory New)"]
    assert listings[0]["price_cents"] == 3574
    assert listings[0]["float_value"] == 0.061443410813808
    assert listings[0]["seller_steam_level"] == 12
    assert [sticker["id"] for sticker in listings[0]["stickers"]] == [
        "13026426608",
        "13026426609",
    ]


def test_private_methods_require_api_key(monkeypatch):
    monkeypatch.delenv("CSGOMARKET_API_KEY", raising=False)

    with pytest.raises(csgomarket.CsgoMarketRequestError, match="API_KEY"):
        csgomarket.get_active_listings("Test item")


def test_normalizes_bid_ask_order_book(monkeypatch):
    monkeypatch.setenv("CSGOMARKET_API_KEY", "private-test-key")
    monkeypatch.setattr(csgomarket, "_wait_for_private_request_slot", lambda: None)
    monkeypatch.setattr(
        csgomarket,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            {
                "currency": "USD",
                "bid": [
                    {"price": "28.7550", "total": "3"},
                    {"price": "27.1000", "total": "5"},
                ],
                "ask": [{"price": "28.8000", "total": "2"}],
            }
        ),
    )

    order_book = csgomarket.get_order_book("AK-47 | Redline (Field-Tested)")

    assert order_book == {
        "buy_orders": [
            {"price_cents": 2876, "quantity": 3},
            {"price_cents": 2710, "quantity": 5},
        ],
        "sell_orders": [{"price_cents": 2880, "quantity": 2}],
    }


def test_loads_and_caches_public_sales_history_index(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith("/full-history/all.json"):
            return FakeResponse(
                {"history": {"AK-47 | Redline (Field-Tested)": 12345}}
            )
        return FakeResponse(
            {
                "data": {
                    "history": [
                        [1700000000, 1000, 28.805, 27.0],
                        [1700001000, 1000, 29.0, 27.0],
                    ]
                }
            }
        )

    monkeypatch.setattr(csgomarket, "urlopen", fake_urlopen)
    monkeypatch.setattr(csgomarket, "_history_index", None)
    monkeypatch.setattr(csgomarket, "_history_index_fetched_at", 0.0)

    first = csgomarket.get_sales_history("AK-47 | Redline (Field-Tested)")
    second = csgomarket.get_sales_history("AK-47 | Redline (Field-Tested)")

    assert first[0]["price_cents"] == 2900
    assert first[1]["price_cents"] == 2881
    assert second == first
    assert sum(url.endswith("/full-history/all.json") for url in calls) == 1


def test_private_rate_limiter_spaces_calls_and_caps_config(monkeypatch):
    sleeps = []
    monkeypatch.setenv("CSGOMARKET_MAX_REQUESTS_PER_SECOND", "100")
    monkeypatch.setattr(csgomarket, "_next_private_request_at", 0.0)
    monkeypatch.setattr(csgomarket.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(csgomarket.time, "sleep", sleeps.append)

    csgomarket._wait_for_private_request_slot()
    csgomarket._wait_for_private_request_slot()
    csgomarket._wait_for_private_request_slot()

    assert sleeps == [2.01, 4.02]
