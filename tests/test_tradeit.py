import json
from urllib.error import HTTPError

import pytest
from fastapi import HTTPException

from backend.app import market_comparison, tradeit_data
from backend.app.main import marketplace_options, post_calculation
from backend.app.models import CalculationRequest
from backend.app.market_comparison import compare_market_responses
from backend.app.marketplaces import tradeit

TITLE = "AK-47 | Redline (Field-Tested)"
STATTRAK = "StatTrak™ AK-47 | Redline (Field-Tested)"


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
    requests = []
    queue = list(payloads)

    def fake_urlopen(request, timeout=None):
        requests.append(request)
        payload = queue.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return Response(payload)

    monkeypatch.setattr(tradeit, "urlopen", fake_urlopen)
    return requests


def group(name, group_id, store_price, trade_price=9999):
    return {"name": name, "groupId": group_id, "storePrice": store_price,
            "price": trade_price, "sitePrice": trade_price}


def store_item(asset_id, store_price, *, name=TITLE, float_value=0.25, stickers=()):
    return {"assetId": asset_id, "name": name, "storePrice": store_price, "price": 9999,
            "floatValue": float_value, "patternIndex": 229, "paintIndex": 282,
            "imgURL": "hash/256fx256f", "stickers": list(stickers)}


def test_search_uses_the_cash_store_price_and_stock_not_the_trade_value(monkeypatch):
    requests = capture(monkeypatch, [{
        "items": [
            group(TITLE, 35154, 2485, trade_price=4411),
            group(STATTRAK, 39260, 5875),
            group("Out of stock", 1, 500),
            group("No store price", 2, 0),
            {"name": "Broken", "groupId": "x", "storePrice": 100},
        ],
        "counts": {"35154": 54, "39260": 2, "1": 0, "2": 9},
    }])
    groups = tradeit.search_groups("AK-47 | Redline")
    assert groups == {
        TITLE: {"price_cents": 2485, "quantity": 54, "group_id": 35154},
        STATTRAK: {"price_cents": 5875, "quantity": 2, "group_id": 39260},
    }
    url = requests[0].full_url
    assert url.startswith("https://tradeit.gg/api/v2/inventory/data?gameId=730")
    assert "searchValue=AK-47%20%7C%20Redline" in url


def test_group_items_are_exact_sorted_and_filtered_locally(monkeypatch):
    requests = capture(monkeypatch, [{"items": [
        store_item("3", 2600, float_value=0.20, stickers=[{"name": "Crown (Foil)", "link": "x.png"}]),
        store_item("other", 100, name=STATTRAK),
        store_item("1", 2485, float_value=0.36),
        store_item("2", 2485, float_value=0.33),
        store_item("no-price", None),
    ], "counts": {}}])
    listings = tradeit.get_group_items(35154, TITLE, max_float=0.35, limit=10)
    assert [item["listing_id"] for item in listings] == ["2", "3"]
    assert listings[0]["paint_seed"] == 229 and listings[0]["float_value"] == 0.33
    assert listings[0]["image_url"].endswith("/economy/image/hash/256fx256f")
    assert listings[1]["stickers"] == [{"name": "Crown (Foil)", "icon_url": None}]
    assert listings[0]["item_url"] == "https://tradeit.gg/csgo/store?search=AK-47+%7C+Redline+%28Field-Tested%29"
    assert "groupId=35154" in requests[0].full_url


@pytest.mark.parametrize("payload", [[], {"items": "no"}, {"counts": {}}])
def test_a_changed_response_shape_is_an_error_not_an_empty_market(monkeypatch, payload):
    capture(monkeypatch, [payload])
    with pytest.raises(tradeit.TradeitRequestError):
        tradeit.search_groups("AK-47 | Redline")


@pytest.mark.parametrize("status", [403, 429, 503])
def test_http_failures_are_reported_without_provider_details(monkeypatch, status):
    capture(monkeypatch, [HTTPError("https://tradeit.gg/?x=SECRET", status, "SECRET", {}, None)])
    with pytest.raises(tradeit.TradeitRequestError) as error:
        tradeit.search_groups("AK-47 | Redline")
    assert "SECRET" not in str(error.value)


def quote(marketplace, price):
    return {
        "marketplace": marketplace, "cache_ttl_seconds": 300,
        "variants": [{"variant_id": "variant-1", "market_hash_name": TITLE,
                      "listing": {"marketplace": marketplace, "price_cents": price,
                                  "item_url": "https://example.test/"}}],
    }


@pytest.mark.parametrize("mode", ["raw", "smart", "enhanced"])
def test_tradeit_is_a_purchase_source_but_never_a_sale_target(mode):
    result = compare_market_responses(
        "skin-1", [quote("Tradeit.gg", 2000), quote("CSFloat", 2600), quote("DMarket", 2500)],
        deposit_method="crypto", withdraw_method="crypto", use_deposit_fee=True, profit_mode=mode,
    )
    variant = result["variants"][0]
    assert variant["cheapest_marketplace"] == "tradeit"
    opportunities = variant["opportunities"]
    assert {item["buy_marketplace"] for item in opportunities} >= {"tradeit"}
    assert all(item["sell_marketplace"] != "tradeit" for item in opportunities)
    assert opportunities[0]["buy_marketplace"] == "tradeit"
    assert opportunities[0]["sell_marketplace"] == "csfloat"


def test_quick_flip_never_asks_tradeit_for_a_bid(monkeypatch):
    monkeypatch.setattr(market_comparison, "get_csfloat_variant_fast_buy",
                        lambda _id: {"best_price_cents": 2300, "error": None})
    prices = market_comparison._load_quick_sell_prices([quote("Tradeit.gg", 2000), quote("CSFloat", 2600)])
    assert set(prices["variant-1"]) == {"csfloat"}


def test_calculate_rejects_selling_on_tradeit_and_lists_it_as_buy_only():
    body = {"buy_price_cents": 1000, "sell_price_cents": 1200,
            "buy_marketplace": "csfloat", "sell_marketplace": "tradeit"}
    with pytest.raises(HTTPException) as error:
        post_calculation(CalculationRequest(**body))
    assert error.value.status_code == 422
    body.update(buy_marketplace="tradeit", sell_marketplace="csfloat", profit_mode="smart")
    assert post_calculation(CalculationRequest(**body)).deposit_fee_cents == 0
    option = next(item for item in marketplace_options() if item["id"] == "tradeit")
    assert option["display_name"] == "Tradeit.gg"
    assert option["capabilities"]["can_buy"] and not option["capabilities"]["can_sell"]
    assert option["withdraw_methods"] == [] and option["fees"]["sell"] is None


def test_listings_reuse_the_group_id_and_skip_variants_tradeit_does_not_stock(monkeypatch):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, _params):
            rows = ({"id": "skin-1", "name": "AK-47 | Redline", "image_url": "skin.png"}
                    if "FROM skins" in query else [
                {"id": "v-ft", "market_hash_name": TITLE, "wear_name": "Field-Tested",
                 "stattrak": False, "souvenir": False, "image_url": None},
                {"id": "v-st", "market_hash_name": STATTRAK, "wear_name": "Field-Tested",
                 "stattrak": True, "souvenir": False, "image_url": None},
            ])
            return type("Cursor", (), {"fetchone": lambda _s: rows, "fetchall": lambda _s: rows})()

    searches = []
    monkeypatch.setattr(tradeit_data, "get_connection", Connection)
    monkeypatch.setattr(tradeit_data, "_group_ids", {})
    monkeypatch.setattr(tradeit_data, "search_groups", lambda name: searches.append(name) or {
        TITLE: {"price_cents": 2485, "quantity": 54, "group_id": 35154},
    })
    monkeypatch.setattr(tradeit_data, "get_group_items", lambda group_id, name, **_kwargs: [
        {"listing_id": "1", "price_cents": 2485, "float_value": 0.33, "image_url": None,
         "stickers": [], "charms": []},
    ] if group_id == 35154 else pytest.fail("unknown group requested"))

    result = tradeit_data.get_tradeit_skin_listings("skin-1", wear="field-tested")
    assert [item["variant_id"] for item in result["listings"]] == ["v-ft"]
    assert result["listings"][0]["marketplace_id"] == "tradeit"
    assert result["listings"][0]["image_url"] == "skin.png"
    assert result["error"] is None
    # One search found the stocked variant; the missing StatTrak one costs one more, not one per call.
    assert searches == ["AK-47 | Redline", "AK-47 | Redline"]
    assert tradeit_data.get_tradeit_skin_listings("skin-1", wear="field-tested", has_charm=True)["listings"] == []
