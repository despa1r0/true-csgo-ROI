from backend.app import market_comparison
from backend.app.market_comparison import compare_market_responses


def market_response(name, price_cents, *, error=None):
    listing = None
    if price_cents is not None:
        listing = {
            "marketplace": name,
            "price_cents": price_cents,
            "item_url": "https://example.test/item",
        }
    return {
        "marketplace": name,
        "cache_ttl_seconds": 300,
        "variants": [
            {
                "variant_id": "variant-1",
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "listing": listing,
                "error": error,
            }
        ],
    }


def test_compares_exact_variant_and_calculates_both_profit_directions():
    result = compare_market_responses(
        "skin-1",
        [
            market_response("CSFloat", 1000),
            market_response("CSGO Market", 1200),
        ],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=True,
    )

    variant = result["variants"][0]
    assert variant["cheapest_marketplace"] == "csfloat"
    assert variant["cheapest_price_cents"] == 1000
    assert variant["gross_spread_cents"] == 200
    assert variant["markets"]["csfloat"]["price_cents"] == 1000
    assert variant["markets"]["csgomarket"]["price_cents"] == 1200
    assert variant["opportunities"][0]["buy_marketplace"] == "csfloat"
    assert variant["opportunities"][0]["sell_marketplace"] == "csgomarket"
    assert variant["opportunities"][0]["profit_cents"] == 30
    assert variant["opportunities"][0]["cash_roi_percent"] == 2.97
    reverse = next(
        opportunity
        for opportunity in variant["opportunities"]
        if opportunity["buy_marketplace"] == "csgomarket"
        and opportunity["sell_marketplace"] == "csfloat"
    )
    assert reverse["profit_cents"] == -320
    assert reverse["cash_roi_percent"] == -24.62


def test_keeps_cached_market_error_and_handles_one_available_price():
    result = compare_market_responses(
        "skin-1",
        [
            market_response("CSFloat", 1000),
            market_response("CSGO Market", None, error="temporary failure"),
        ],
        deposit_method="card",
        withdraw_method="card",
        use_deposit_fee=False,
    )

    variant = result["variants"][0]
    assert variant["errors"] == {"csgomarket": "temporary failure"}
    assert variant["cheapest_marketplace"] == "csfloat"
    assert variant["gross_spread_cents"] is None
    assert variant["opportunities"] == []


def test_raw_mode_ignores_every_fee():
    result = compare_market_responses(
        "skin-1",
        [market_response("CSFloat", 1000), market_response("CSGO Market", 1200)],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=True,
        profit_mode="raw",
    )

    opportunity = result["variants"][0]["opportunities"][0]
    assert opportunity["profit_mode"] == "raw"
    assert opportunity["deposit_fee_cents"] == 0
    assert opportunity["sell_fee_cents"] == 0
    assert opportunity["withdraw_fee_cents"] == 0
    assert opportunity["profit_cents"] == 200


def test_enhanced_mode_skips_only_deposit_fee():
    result = compare_market_responses(
        "skin-1",
        [market_response("CSFloat", 1000), market_response("CSGO Market", 1200)],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=True,
        profit_mode="enhanced",
    )

    opportunity = result["variants"][0]["opportunities"][0]
    assert opportunity["deposit_fee_cents"] == 0
    assert opportunity["sell_fee_cents"] == 60
    assert opportunity["withdraw_fee_cents"] == 100
    assert opportunity["profit_cents"] == 40


def test_quick_flip_buys_cheapest_and_uses_other_market_fast_buy():
    result = compare_market_responses(
        "skin-1",
        [market_response("CSFloat", 1000), market_response("CSGO Market", 1200)],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=False,
        profit_mode="quick_flip",
        quick_sell_prices={
            "variant-1": {
                "csgomarket": {"best_price_cents": 900, "error": None}
            }
        },
    )

    opportunity = result["variants"][0]["opportunities"][0]
    assert opportunity["buy_marketplace"] == "csfloat"
    assert opportunity["sell_marketplace"] == "csgomarket"
    assert opportunity["sell_mode"] == "fast_buy"
    assert opportunity["buy_price_cents"] == 1000
    assert opportunity["sell_price_cents"] == 900
    assert opportunity["deposit_fee_cents"] == 0
    assert opportunity["profit_cents"] == -245


def test_quick_flip_loads_only_other_market_fast_buy(monkeypatch):
    calls = []
    monkeypatch.setattr(
        market_comparison,
        "get_csfloat_prices",
        lambda _skin_id: market_response("CSFloat", 1000),
    )
    monkeypatch.setattr(
        market_comparison,
        "get_csgomarket_prices",
        lambda _skin_id: market_response("CSGO Market", 1200),
    )
    monkeypatch.setattr(
        market_comparison,
        "get_csgomarket_variant_fast_buy",
        lambda variant_id: calls.append(("csgomarket", variant_id))
        or {"best_price_cents": 900, "error": None},
    )
    monkeypatch.setattr(
        market_comparison,
        "get_csfloat_variant_fast_buy",
        lambda variant_id: calls.append(("csfloat", variant_id))
        or {"best_price_cents": 800, "error": None},
    )

    result = market_comparison.get_skin_market_comparison(
        "skin-1", profit_mode="quick_flip", use_deposit_fee=False
    )

    assert calls == [("csgomarket", "variant-1")]
    assert result["variants"][0]["opportunities"][0]["sell_price_cents"] == 900
