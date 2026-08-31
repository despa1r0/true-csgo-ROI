import json

import pytest
from urllib.error import HTTPError
from io import BytesIO

from backend.app.marketplaces import whitemarket


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


# --- Partner GraphQL API (get_active_listings / get_cheapest_listing) ------


@pytest.fixture(autouse=True)
def _reset_access_token_cache():
    whitemarket._access_token_cache["token"] = None
    whitemarket._access_token_cache["expires_at"] = 0.0
    yield
    whitemarket._access_token_cache["token"] = None
    whitemarket._access_token_cache["expires_at"] = 0.0


def _request_query(request) -> str:
    return json.loads(request.data.decode("utf-8"))["query"]


AUTH_SUCCESS_PAYLOAD = {"data": {"auth_token": {"accessToken": "fake-access-token"}}}

ONE_LISTING_PAYLOAD = {
    "data": {
        "market_list": {
            "totalCount": 2466,
            "edges": [
                {
                    "node": {
                        "id": "1f1a1f05-199e-66c6-bcfb-0242ac100002",
                        "price": {"value": "28.48", "currency": "USD"},
                        "slug": "ak-47-redline-field-tested-5676347559448654",
                        "createdAt": "2026-08-27T08:21:35+0000",
                        "item": {
                            "float": "0.3154",
                            "paintIndex": "282",
                            "paintSeed": "709",
                            "link": "steam://run/730//+csgo_econ_action_preview%20AB",
                            "stickers": [
                                {"name": "paper_lorena", "title": "Sticker | Lorena", "icon": "https://x/sticker.png"}
                            ],
                            "charms": [],
                            "description": {
                                "icon": "https://x/small.png",
                                "iconLarge": "https://x/large.png",
                                "name": "AK-47 | Redline",
                            },
                        },
                    }
                }
            ],
        }
    }
}

EMPTY_LISTING_PAYLOAD = {"data": {"market_list": {"totalCount": 0, "edges": []}}}


def test_requires_partner_token(monkeypatch):
    monkeypatch.delenv("WHITEMARKET_PARTNER_TOKEN", raising=False)

    with pytest.raises(whitemarket.WhitemarketRequestError, match="WHITEMARKET_PARTNER_TOKEN"):
        whitemarket.get_active_listings("AK-47 | Redline (Field-Tested)")


def test_exchanges_partner_token_and_returns_normalized_listings(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        query = _request_query(request)
        if "auth_token" in query:
            assert request.headers["X-partner-token"] == "partner-secret"
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        assert request.headers["Authorization"] == "Bearer fake-access-token"
        return FakeResponse(ONE_LISTING_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    listings = whitemarket.get_active_listings("AK-47 | Redline (Field-Tested)", limit=5)

    assert len(calls) == 2  # one token exchange, one listings query
    assert listings == [
        {
            "listing_id": "1f1a1f05-199e-66c6-bcfb-0242ac100002",
            "price_cents": 2848,
            "item_url": "https://white.market/item/ak-47-redline-field-tested-5676347559448654",
            "float_value": 0.3154,
            "paint_seed": 709,
            "paint_index": 282,
            "stickers": [{"name": "Sticker | Lorena", "icon_url": "https://x/sticker.png"}],
            "charms": [],
            "created_at": "2026-08-27T08:21:35+0000",
            "inspect_link": "steam://run/730//+csgo_econ_action_preview%20AB",
            "image_url": "https://x/large.png",
        }
    ]


def test_caches_access_token_across_calls(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")
    auth_calls = []

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            auth_calls.append(request)
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        return FakeResponse(ONE_LISTING_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    whitemarket.get_active_listings("AK-47 | Redline (Field-Tested)")
    whitemarket.get_active_listings("AWP | Asiimov (Field-Tested)")

    assert len(auth_calls) == 1  # second call reuses the cached access token


def test_refreshes_token_once_on_expired_jwt(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")
    auth_call_count = 0
    listings_call_count = 0

    def fake_urlopen(request, timeout):
        nonlocal auth_call_count, listings_call_count
        query = _request_query(request)
        if "auth_token" in query:
            auth_call_count += 1
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        listings_call_count += 1
        if listings_call_count == 1:
            return FakeResponse(
                {"errors": [{"message": "Expired JWT Token"}]}
            )
        return FakeResponse(ONE_LISTING_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    listings = whitemarket.get_active_listings("AK-47 | Redline (Field-Tested)")

    assert auth_call_count == 2  # initial exchange + forced refresh after expiry
    assert listings_call_count == 2  # first attempt failed, retried once
    assert len(listings) == 1


def test_raises_on_non_retryable_graphql_error(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        return FakeResponse({"errors": [{"message": "Validation error: bad float range"}]})

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    with pytest.raises(whitemarket.WhitemarketRequestError, match="bad float range"):
        whitemarket.get_active_listings("AK-47 | Redline (Field-Tested)")


def test_builds_float_and_price_filters_into_search_input(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")
    captured = {}

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        captured["variables"] = json.loads(request.data.decode("utf-8"))["variables"]
        return FakeResponse(ONE_LISTING_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    whitemarket.get_active_listings(
        "AK-47 | Redline (Field-Tested)",
        min_float=0.2,
        max_float=0.36,
        min_price_cents=500,
        max_price_cents=10000,
        has_stickers=True,
        limit=100,  # should be clamped to 50
    )

    search = captured["variables"]["search"]
    assert search["csgoFloatFrom"] == "0.2"
    assert search["csgoFloatTo"] == "0.36"
    assert search["price"] == {
        "from": {"value": "5.00", "currency": "USD"},
        "to": {"value": "100.00", "currency": "USD"},
    }
    assert search["csgoStickers"] is True
    assert "csgoCharm" not in search
    assert captured["variables"]["first"] == 50


def test_cheapest_listing_includes_total_count(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")
    captured = {}

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        captured["variables"] = json.loads(request.data.decode("utf-8"))["variables"]
        return FakeResponse(ONE_LISTING_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    listing = whitemarket.get_cheapest_listing("AK-47 | Redline (Field-Tested)")

    assert listing["price_cents"] == 2848
    assert listing["quantity"] == 2466  # from totalCount, not a second request
    assert captured["variables"]["first"] == 1


def test_cheapest_listing_is_none_when_market_is_empty(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        return FakeResponse(EMPTY_LISTING_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    assert whitemarket.get_cheapest_listing("Nonexistent Skin (Field-Tested)") is None


# --- Partner GraphQL API (get_buy_orders) -----------------------------------

# order_list's own nameHash filter matches loosely (confirmed against the
# live API — it returns other weapons of the same wear too), so the mock
# response mirrors that: one exact match plus two off-target orders that
# must be filtered out client-side.
ORDER_LIST_PAYLOAD = {
    "data": {
        "order_list": {
            "edges": [
                {
                    "node": {
                        "nameHash": "AK-47 | Case Hardened (Field-Tested)",
                        "quantity": 1,
                        "price": {"value": "197.33", "currency": "USD"},
                        "params": [{"param": "CSGO_FLOAT", "value": ["0.15", "0.38"]}],
                    }
                },
                {
                    "node": {
                        "nameHash": "AK-47 | Redline (Field-Tested)",
                        "quantity": 2,
                        "price": {"value": "42.50", "currency": "USD"},
                        "params": [{"param": "CSGO_FLOAT", "value": ["0.15", "0.1599"]}],
                    }
                },
                {
                    "node": {
                        "nameHash": "AK-47 | Redline (Field-Tested)",
                        "quantity": 0,  # sold out — should be dropped
                        "price": {"value": "40.00", "currency": "USD"},
                        "params": [{"param": "CSGO_FLOAT", "value": ["0.15", "0.38"]}],
                    }
                },
                {
                    "node": {
                        "nameHash": "StatTrak™ AK-47 | Redline (Field-Tested)",
                        "quantity": 1,
                        "price": {"value": "71.00", "currency": "USD"},
                        "params": [{"param": "CSGO_FLOAT", "value": ["0.15", "0.19"]}],
                    }
                },
            ]
        }
    }
}


def test_buy_orders_keeps_only_exact_nameHash_matches(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")
    captured = {}

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        captured["variables"] = json.loads(request.data.decode("utf-8"))["variables"]
        return FakeResponse(ORDER_LIST_PAYLOAD)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    orders = whitemarket.get_buy_orders("AK-47 | Redline (Field-Tested)")

    # Only the one exact match with quantity > 0 survives — Case Hardened,
    # StatTrak, and the sold-out (quantity=0) Redline row are all dropped.
    assert orders == [
        {"price_cents": 4250, "quantity": 2, "min_float": 0.15, "max_float": 0.1599}
    ]
    assert captured["variables"]["search"]["nameHash"] == "AK-47 | Redline (Field-Tested)"


def test_buy_orders_respects_limit(monkeypatch):
    monkeypatch.setenv("WHITEMARKET_PARTNER_TOKEN", "partner-secret")

    payload = {
        "data": {
            "order_list": {
                "edges": [
                    {
                        "node": {
                            "nameHash": "AWP | Asiimov (Field-Tested)",
                            "quantity": 1,
                            "price": {"value": str(100 - i), "currency": "USD"},
                            "params": [],
                        }
                    }
                    for i in range(5)
                ]
            }
        }
    }

    def fake_urlopen(request, timeout):
        query = _request_query(request)
        if "auth_token" in query:
            return FakeResponse(AUTH_SUCCESS_PAYLOAD)
        return FakeResponse(payload)

    monkeypatch.setattr(whitemarket, "urlopen", fake_urlopen)

    orders = whitemarket.get_buy_orders("AWP | Asiimov (Field-Tested)", limit=2)

    assert len(orders) == 2
