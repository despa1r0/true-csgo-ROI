import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from backend.app import csfloat
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
                            {"name": "Sticker | Test", "slot": 2, "wear": 0.01}
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
            "stickers": [{"name": "Sticker | Test", "slot": 2, "wear": 0.01}],
            "seller_name": "seller",
            "seller_online": True,
            "created_at": "2026-08-20T10:00:00Z",
            "inspect_link": "steam://inspect",
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


@pytest.mark.parametrize(
    ("sales", "listings", "expected"),
    [
        (None, 10, (None, "unavailable")),
        (5, 100, (5, "low")),
        (20, 100, (20, "medium")),
        (60, 100, (60, "high")),
    ],
)
def test_calculates_transparent_liquidity_score(sales, listings, expected):
    assert calculate_liquidity(sales, listings) == expected
