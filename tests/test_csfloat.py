import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from backend.app import csfloat
from backend.app import market_data
from backend.app.market_data import calculate_liquidity


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_gets_direct_link_to_lowest_buy_now_listing(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            [
                {
                    "id": "123456789",
                    "price": 1840,
                    "item": {"float_value": 0.23456789},
                }
            ]
        )

    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(csfloat, "urlopen", fake_urlopen)

    price = csfloat.get_lowest_price("AK-47 | Redline (Field-Tested)")

    assert price is not None
    assert price.price_cents == 1840
    assert price.listing_id == "123456789"
    assert price.item_url == "https://csfloat.com/item/123456789"
    assert price.float_value == 0.23456789
    assert captured["request"].get_header("Authorization") == "test-key"
    query = parse_qs(urlparse(captured["request"].full_url).query)
    assert query["market_hash_name"] == ["AK-47 | Redline (Field-Tested)"]
    assert query["sort_by"] == ["lowest_price"]
    assert query["type"] == ["buy_now"]
    assert query["limit"] == ["1"]


def test_returns_none_when_there_are_no_listings(monkeypatch):
    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(csfloat, "urlopen", lambda *_args, **_kwargs: FakeResponse([]))

    assert csfloat.get_lowest_price("Missing skin") is None


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)

    with pytest.raises(csfloat.CsfloatRequestError, match="CSFLOAT_API_KEY"):
        csfloat.get_lowest_price("AK-47 | Redline (Field-Tested)")


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
        return FakeResponse([{"id": "42", "price": 500, "item": {}}])

    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(csfloat, "urlopen", fake_urlopen)
    monkeypatch.setattr(csfloat.time, "sleep", lambda _seconds: None)

    price = csfloat.get_lowest_price("AK-47 | Test (Factory New)")

    assert price is not None
    assert price.listing_id == "42"
    assert len(calls) == 2


def test_loads_market_wide_price_index(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            [
                {
                    "market_hash_name": "AWP | Redline (Field-Tested)",
                    "quantity": 788,
                    "min_price": 3306,
                },
                {"market_hash_name": "Invalid entry", "min_price": None},
            ]
        )

    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(csfloat, "urlopen", fake_urlopen)

    index = csfloat.get_price_index()

    assert index == {
        "AWP | Redline (Field-Tested)": {
            "price_cents": 3306,
            "quantity": 788,
        }
    }
    assert captured["request"].full_url.endswith("/listings/price-list")
    assert captured["request"].get_header("Authorization") == "test-key"
    assert captured["timeout"] == 30


def test_normalizes_detailed_active_listings(monkeypatch):
    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(
        csfloat,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            [
                {
                    "id": "987",
                    "price": 4321,
                    "created_at": "2026-08-20T10:00:00Z",
                    "seller": {"username": "seller", "online": True},
                    "item": {
                        "float_value": 0.123456789,
                        "paint_seed": 321,
                        "paint_index": 282,
                        "inspect_link": "steam://inspect",
                        "stickers": [
                            {
                                "name": "Sticker | Test",
                                "slot": 2,
                                "wear": 0.01,
                                "icon_url": "https://example.test/sticker.png",
                                "reference": {
                                    "price": 125,
                                    "quantity": 14,
                                    "updated_at": "2026-08-20T09:00:00Z",
                                },
                            }
                        ],
                    },
                }
            ]
        ),
    )

    listings = csfloat.get_active_listings(
        "AK-47 | Redline (Field-Tested)", limit=10
    )

    assert listings == [
        {
            "listing_id": "987",
            "price_cents": 4321,
            "item_url": "https://csfloat.com/item/987",
            "float_value": 0.123456789,
            "paint_seed": 321,
            "paint_index": 282,
            "stickers": [
                {
                    "name": "Sticker | Test",
                    "slot": 2,
                    "wear": 0.01,
                    "icon_url": "https://example.test/sticker.png",
                    "csfloat_price_cents": 125,
                    "csfloat_quantity": 14,
                    "price_updated_at": "2026-08-20T09:00:00Z",
                    "steam_price_cents": None,
                }
            ],
            "charms": [],
            "seller_name": "seller",
            "seller_online": True,
            "created_at": "2026-08-20T10:00:00Z",
            "inspect_link": "steam://inspect",
        }
    ]


def test_market_search_passes_csfloat_filters_and_keeps_best_deal_reference(
    monkeypatch,
):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(
            [
                {
                    "id": "best-1",
                    "price": 9000,
                    "min_offer_price": 8750,
                    "item": {
                        "market_hash_name": "AK-47 | Test (Field-Tested)",
                        "item_name": "AK-47 | Test",
                        "wear_name": "Field-Tested",
                        "icon_url": "https://example.test/item.png",
                        "float_value": 0.2,
                        "paint_seed": 123,
                        "paint_index": 1171,
                        "is_stattrak": False,
                        "is_souvenir": False,
                    },
                    "reference": {
                        "base_price": 9500,
                        "predicted_price": 10000,
                        "quantity": 24,
                    },
                }
            ]
        )

    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(csfloat, "urlopen", fake_urlopen)

    listings = csfloat.search_market_listings(
        paint_index=1171,
        sort_by="best_deal",
        category=1,
        min_float=0.15,
        max_float=0.38,
        min_price_cents=5000,
        max_price_cents=12000,
        limit=30,
    )

    query = parse_qs(urlparse(captured["url"]).query)
    assert query == {
        "paint_index": ["1171"],
        "sort_by": ["best_deal"],
        "category": ["1"],
        "type": ["buy_now"],
        "limit": ["30"],
        "min_float": ["0.15"],
        "max_float": ["0.38"],
        "min_price": ["5000"],
        "max_price": ["12000"],
    }
    assert listings[0]["listing_id"] == "best-1"
    assert listings[0]["predicted_price_cents"] == 10000
    assert listings[0]["deal_percent"] == 10.0
    assert listings[0]["wear_name"] == "Field-Tested"


def test_market_search_normalizes_charms(monkeypatch):
    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(
        csfloat,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            [
                {
                    "id": "charmed-1",
                    "price": 5000,
                    "item": {
                        "market_hash_name": "AK-47 | Test (Minimal Wear)",
                        "item_name": "AK-47 | Test",
                        "wear_name": "Minimal Wear",
                        "paint_index": 1,
                        "keychains": [
                            {
                                "name": "Charm | Lil' No. 2",
                                "slot": 0,
                                "pattern": 21896,
                                "icon_url": "https://example.test/charm.png",
                                "reference": {"price": 21, "quantity": 532},
                            }
                        ],
                    },
                }
            ]
        ),
    )

    listing = csfloat.search_market_listings(paint_index=1, limit=1)[0]

    assert listing["charms"] == [
        {
            "name": "Charm | Lil' No. 2",
            "slot": 0,
            "pattern": 21896,
            "icon_url": "https://example.test/charm.png",
            "csfloat_price_cents": 21,
            "csfloat_quantity": 532,
            "price_updated_at": None,
        }
    ]


def test_normalizes_sales_history_envelope(monkeypatch):
    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(
        csfloat,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            {
                "sales": [
                    {
                        "price": 4100,
                        "created_at": "2026-08-19T10:00:00Z",
                        "item": {"float_value": 0.2},
                    }
                ]
            }
        ),
    )

    assert csfloat.get_sales_history("AK-47 | Redline (Field-Tested)") == [
        {
            "price_cents": 4100,
            "sold_at": "2026-08-19T10:00:00Z",
            "float_value": 0.2,
        }
    ]


def test_sorts_sales_history_newest_first(monkeypatch):
    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(
        csfloat,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            [
                {"price": 1000, "created_at": "2026-08-18T10:00:00Z"},
                {"price": 1200, "created_at": "2026-08-20T10:00:00Z"},
            ]
        ),
    )

    sales = csfloat.get_sales_history("AK-47 | Redline (Field-Tested)")

    assert [sale["price_cents"] for sale in sales] == [1200, 1000]


def test_normalizes_matching_buy_orders(monkeypatch):
    monkeypatch.setenv("CSFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(
        csfloat,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            [
                {
                    "market_hash_name": "AK-47 | Test (Field-Tested)",
                    "qty": 5,
                    "price": 3320,
                    "hybrid_properties": {"min_float": 0.15, "max_float": 0.38},
                }
            ]
        ),
    )

    assert csfloat.get_buy_orders("listing-1") == [
        {
            "price_cents": 3320,
            "quantity": 5,
            "min_float": 0.15,
            "max_float": 0.38,
        }
    ]


def test_liquidity_uses_spread_depth_and_sales_velocity():
    sales = [
        {"sold_at": "2026-08-20T10:00:00Z"},
        {"sold_at": "2026-08-21T10:00:00Z"},
        {"sold_at": "2026-08-21T22:00:00Z"},
    ]
    orders = [{"price_cents": 9500, "quantity": 20}]

    result = calculate_liquidity(sales, 10000, orders)

    assert result["score"] == 93
    assert result["label"] == "high"
    assert result["price_retention_percent"] == 95.0
    assert result["near_bid_depth"] == 20
    assert result["sales_per_day"] == 1.33


def test_liquidity_is_unavailable_without_ask_or_buy_orders():
    result = calculate_liquidity([], None, [])

    assert result["score"] is None
    assert result["label"] == "unavailable"


def test_quick_sell_is_calculated_for_the_selected_listing(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "get_listing",
        lambda listing_id: {"listing_id": listing_id, "price_cents": 10000},
    )
    monkeypatch.setattr(
        market_data,
        "get_buy_orders",
        lambda listing_id, limit: [
            {"price_cents": 9500, "quantity": 3},
            {"price_cents": 9000, "quantity": 2},
        ],
    )

    result = market_data.get_csfloat_listing_quick_sell("selected-1")

    assert result is not None
    assert result["listing_id"] == "selected-1"
    assert result["best_price_cents"] == 9500
    assert result["discount_percent"] == 5.0
    assert result["near_bid_depth"] == 3
    assert "выбранного лота" in result["note"]
