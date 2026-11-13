import json
from urllib.error import HTTPError

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from backend.app import dmarket_data, market_comparison
from backend.app.marketplaces import dmarket
from backend.app.marketplaces_fees import MARKETPLACES

TITLE = "AK-47 | Redline (Field-Tested)"
SEED = bytes(range(32))
PUBLIC = Ed25519PrivateKey.from_private_bytes(SEED).public_key()
PUBLIC_HEX = PUBLIC.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
SECRET_HEX = (SEED + bytes.fromhex(PUBLIC_HEX)).hex()  # DMarket's 64-byte form


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return json.dumps(self.payload).encode()


def capture(monkeypatch, payloads):
    """Replace urlopen; return the list of requests it received."""
    requests = []
    queue = list(payloads)

    def fake_urlopen(request, timeout=None):
        requests.append(request)
        payload = queue.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return Response(payload)

    monkeypatch.setattr(dmarket, "urlopen", fake_urlopen)
    return requests


def signature_of(request):
    return bytes.fromhex(request.get_header("X-request-sign").split(" ")[2])


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.delenv("DMARKET_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("DMARKET_SECRET_KEY", raising=False)


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("DMARKET_PUBLIC_KEY", PUBLIC_HEX.upper())
    monkeypatch.setenv("DMARKET_SECRET_KEY", SECRET_HEX)


def test_signature_covers_method_decoded_path_encoded_query_body_and_timestamp():
    path = f"/marketplace-api/v1/targets-by-title/a8db/{TITLE}"
    query = "limit=5&title=AK-47%20%7C%20Redline"
    value = dmarket.sign_request("get", path, query, "", "1605619994", SECRET_HEX)
    prefix, scheme, signature = value.split(" ")
    assert (prefix, scheme) == ("dmar", "ed25519")
    unsigned = f"GET{path}?{query}1605619994"
    PUBLIC.verify(bytes.fromhex(signature), unsigned.encode())  # raises when wrong
    # The 32-byte seed alone is accepted and signs identically.
    assert dmarket.sign_request("GET", path, query, "", "1605619994", SEED.hex()) == value


@pytest.mark.parametrize("secret", ["not-hex", "abcd"])
def test_malformed_secret_is_an_auth_error_without_echoing_the_key(secret):
    with pytest.raises(dmarket.DmarketAuthError) as error:
        dmarket.sign_request("GET", "/x", "", "", "1", secret)
    assert secret not in str(error.value)


def test_aggregated_prices_work_without_keys_and_parse_cents(monkeypatch, no_keys):
    requests = capture(monkeypatch, [{
        "aggregatedPrices": [
            {"title": TITLE, "orderBestPrice": {"Currency": "USD", "Amount": "2326"},
             "orderCount": "139", "offerBestPrice": {"Currency": "USD", "Amount": "2323"},
             "offerCount": "1105"},
            {"title": "No offers", "orderBestPrice": {"Currency": "USD", "Amount": "0"},
             "orderCount": "0", "offerBestPrice": {"Currency": "USD", "Amount": "0"},
             "offerCount": "0"},
        ],
        "nextCursor": "",
    }])
    prices = dmarket.get_aggregated_prices([TITLE, "No offers", TITLE])
    assert prices[TITLE] == {"ask_cents": 2323, "ask_count": 1105, "bid_cents": 2326, "bid_count": 139}
    assert prices["No offers"] == {"ask_cents": None, "ask_count": 0, "bid_cents": None, "bid_count": 0}
    request = requests[0]
    assert request.full_url == "https://api.dmarket.com/marketplace-api/v1/aggregated-prices"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {
        "filter": {"game": "a8db", "titles": [TITLE, "No offers"]}, "limit": "100",
    }
    assert request.get_header("X-request-sign") is None


def test_aggregated_prices_are_split_into_pages_of_100(monkeypatch, no_keys):
    requests = capture(monkeypatch, [{"aggregatedPrices": [], "nextCursor": ""}] * 3)
    dmarket.get_aggregated_prices([f"item {index}" for index in range(250)])
    assert [len(json.loads(request.data)["filter"]["titles"]) for request in requests] == [100, 100, 50]


def test_rejected_keys_do_not_take_down_the_public_price_index(monkeypatch, keys):
    rejected = HTTPError("https://api.dmarket.com", 401, "Unauthorized", {}, None)
    requests = capture(monkeypatch, [rejected, {"aggregatedPrices": [], "nextCursor": ""}])
    assert dmarket.get_aggregated_prices([TITLE]) == {}
    assert requests[0].get_header("X-api-key") == PUBLIC_HEX
    assert requests[1].get_header("X-api-key") is None


def test_signed_endpoints_refuse_to_run_without_keys(monkeypatch, no_keys):
    requests = capture(monkeypatch, [])
    for call in (dmarket.get_active_listings, dmarket.get_buy_orders, dmarket.get_sales_history):
        with pytest.raises(dmarket.DmarketAuthError):
            call(TITLE)
    assert requests == []


def offer(offer_id, price, *, title=TITLE, float_value="0.25", locked=False, stickers=()):
    return {
        "offerId": offer_id, "priceCents": str(price), "locked": locked, "offerType": "dmarket",
        "createdAt": "2026-11-12T10:00:00Z",
        "attributes": {
            "title": title, "imageUri": "https://img.test/a.png",
            "cs2": {"float": float_value, "paintSeed": 661, "paintIndex": 282,
                    "inspectInGameUri": "steam://inspect",
                    "stickers": list(stickers), "charms": []},
        },
    }


def test_listings_are_signed_exact_buyable_and_filtered_locally(monkeypatch, keys):
    sticker = {"name": "Crown (Foil)", "image": "https://img.test/s.png"}
    requests = capture(monkeypatch, [{"items": [
        offer("b", 2500, float_value="0.30", stickers=[sticker]),
        offer("prefix", 100, title=TITLE + " extra"),
        offer("locked", 200, locked=True),
        offer("a", 2400, float_value="0.16"),
        offer("worn", 2300, float_value="0.37"),
    ], "total": "5", "cursor": ""}])
    listings = dmarket.get_active_listings(TITLE, max_float=0.31, min_price_cents=1000, limit=10)
    assert [item["listing_id"] for item in listings] == ["a", "b"]
    assert listings[1]["stickers"] == [{"name": "Crown (Foil)", "icon_url": "https://img.test/s.png"}]
    assert listings[0]["float_value"] == 0.16 and listings[0]["paint_seed"] == 661
    assert listings[0]["item_url"].startswith(
        "https://dmarket.com/ingame-items/item-list/csgo-skins?title=AK-47")
    request = requests[0]
    assert "title=AK-47%20%7C%20Redline%20%28Field-Tested%29" in request.full_url
    assert "priceFrom=1000" in request.full_url and "offerType=all" in request.full_url
    assert request.get_header("X-request-sign").startswith("dmar ed25519 ")
    path_and_query = request.full_url.removeprefix("https://api.dmarket.com")
    unsigned = "GET" + path_and_query + request.get_header("X-sign-date")
    PUBLIC.verify(signature_of(request), unsigned.encode())


def test_targets_sign_the_decoded_title_and_send_it_encoded(monkeypatch, keys):
    requests = capture(monkeypatch, [{"orders": [
        {"amount": "3", "price": "2100", "title": TITLE, "attributes": {"floatPartValue": "any"}},
        {"amount": "1", "price": "2326", "title": TITLE, "attributes": {"floatPartValue": "FT-0"}},
        {"amount": "0", "price": "9999", "title": TITLE, "attributes": {}},
    ]}])
    orders = dmarket.get_buy_orders(TITLE)
    assert [(order["price_cents"], order["quantity"]) for order in orders] == [(2326, 1), (2100, 3)]
    assert orders[0]["attributes"] == {"floatPartValue": "FT-0"} and orders[1]["attributes"] == {}
    request = requests[0]
    assert request.full_url.endswith("/targets-by-title/a8db/AK-47%20%7C%20Redline%20%28Field-Tested%29")
    unsigned = f"GET/marketplace-api/v1/targets-by-title/a8db/{TITLE}" + request.get_header("X-sign-date")
    PUBLIC.verify(signature_of(request), unsigned.encode())


def test_sales_convert_decimal_usd_and_unix_time_and_stop_on_a_short_page(monkeypatch, keys):
    requests = capture(monkeypatch, [{"sales": [
        {"price": "23.05", "date": "1762941600", "txOperationType": "Offer",
         "offerAttributes": {"floatValue": 0.2156}},
        {"price": "bad", "date": "1762941600"},
        {"price": "22.10", "date": "1762945200", "txOperationType": "Target", "offerAttributes": {}},
    ]}])
    sales = dmarket.get_sales_history(TITLE)
    assert len(requests) == 1
    assert [(sale["price_cents"], sale["float_value"], sale["sale_type"]) for sale in sales] == [
        (2210, None, "Target"), (2305, 0.2156, "Offer"),
    ]
    assert sales[0]["sold_at"] == "2025-11-12T11:00:00+00:00"


def test_rate_limit_is_reported_without_provider_details(monkeypatch, no_keys):
    capture(monkeypatch, [HTTPError("https://api.dmarket.com/?x=SECRET", 429, "SECRET", {}, None)])
    with pytest.raises(dmarket.DmarketRequestError) as error:
        dmarket.get_aggregated_prices([TITLE])
    assert "SECRET" not in str(error.value)


def test_registry_and_comparison_know_dmarket():
    config = MARKETPLACES["dmarket"]
    assert config.can_buy and config.can_sell and config.supports_fast_buy
    assert config.fees.sell.percent == 2
    # Card fees come from Pricempire only (unconfirmed by DMarket); crypto is free.
    assert config.fees.deposit["card"] is not None and config.fees.withdraw["card"].percent == 2.5
    assert market_comparison.MARKET_RESPONSE_KEYS["DMarket"] == "dmarket"
    assert market_comparison._fast_buy_function("dmarket") is market_comparison.get_dmarket_variant_fast_buy


def test_quick_flip_bid_reuses_the_price_index_response(monkeypatch):
    calls = []
    monkeypatch.setattr(dmarket_data, "_variant", lambda _id: {"market_hash_name": TITLE, "image_url": None})
    monkeypatch.setattr(dmarket_data, "_bid_cache", {})

    def prices(titles):
        calls.append(titles)
        return {TITLE: {"ask_cents": 2323, "ask_count": 5, "bid_cents": 2200, "bid_count": 2}}

    monkeypatch.setattr(dmarket_data, "get_aggregated_prices", prices)
    first = dmarket_data.get_dmarket_variant_fast_buy("variant-1")
    second = dmarket_data.get_dmarket_variant_fast_buy("variant-1")
    assert first == {"best_price_cents": 2200, "error": None, "cached": False}
    assert second == {"best_price_cents": 2200, "error": None, "cached": True}
    assert calls == [[TITLE]]


def test_variant_details_without_keys_expose_index_quotes_and_say_what_is_missing(monkeypatch, no_keys):
    monkeypatch.setattr(dmarket_data, "_variant", lambda _id: {"market_hash_name": TITLE, "image_url": None})
    monkeypatch.setattr(dmarket_data, "_bid_cache", {})
    monkeypatch.setattr(dmarket_data, "get_aggregated_prices", lambda _titles: {
        TITLE: {"ask_cents": 2323, "ask_count": 1105, "bid_cents": 2200, "bid_count": 139},
    })
    for name in ("get_active_listings", "get_buy_orders", "get_sales_history"):
        monkeypatch.setattr(dmarket_data, name, lambda *_a, **_k: pytest.fail("signed call without keys"))
    details = dmarket_data.get_dmarket_variant_details("variant-1")
    assert details["overview"] == {
        "price_cents": 2323, "active_listings": 1105, "item_url": dmarket.item_url(TITLE),
    }
    assert details["quick_sell"]["best_price_cents"] == 2200
    assert details["listings"] == [] and details["sales"] == []
    assert details["sales_error"] == dmarket.KEYS_MISSING_MESSAGE
    assert details["components"]["buy_orders"]["status"] == "fresh"
    assert details["components"]["sales"]["status"] == "unavailable"
    assert details["stats"]["liquidity_score"] is None


def test_variant_details_with_keys_use_only_unrestricted_targets_for_the_bid(monkeypatch, keys):
    monkeypatch.setattr(dmarket_data, "_variant", lambda _id: {"market_hash_name": TITLE, "image_url": "fallback.png"})
    monkeypatch.setattr(dmarket_data, "_bid_cache", {})
    monkeypatch.setattr(dmarket_data, "get_aggregated_prices", lambda _titles: {
        TITLE: {"ask_cents": 2400, "ask_count": 7, "bid_cents": 2390, "bid_count": 4},
    })
    monkeypatch.setattr(dmarket_data, "get_active_listings", lambda *_a, **_k: [
        {"listing_id": "a", "price_cents": 2400, "image_url": None, "stickers": [], "charms": []},
    ])
    monkeypatch.setattr(dmarket_data, "get_buy_orders", lambda *_a, **_k: [
        {"price_cents": 2390, "quantity": 1, "min_float": None, "max_float": None, "attributes": {"phase": "x"}},
        {"price_cents": 2200, "quantity": 3, "min_float": None, "max_float": None, "attributes": {}},
    ])

    def sales_down(*_args, **_kwargs):
        raise dmarket.DmarketRequestError("DMarket временно недоступен (HTTP 503)")

    monkeypatch.setattr(dmarket_data, "get_sales_history", sales_down)
    details = dmarket_data.get_dmarket_variant_details("variant-1")
    assert details["quick_sell"]["best_price_cents"] == 2200
    assert details["quick_sell"]["best_price_quantity"] == 3
    assert len(details["quick_sell"]["orders"]) == 2
    assert details["listings"][0]["image_url"] == "fallback.png"
    assert details["listings"][0]["marketplace_id"] == "dmarket"
    assert details["components"]["sales"]["status"] == "unavailable"
    assert details["components"]["listings"]["status"] == "fresh"
    assert details["is_partial"] is False
