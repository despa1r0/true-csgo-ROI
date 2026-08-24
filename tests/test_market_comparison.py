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
