from backend.app import market_comparison
from backend.app.market_comparison import compare_market_responses


def market_response(
    name,
    price_cents,
    *,
    error=None,
    variant_id="variant-1",
    market_hash_name="AK-47 | Redline (Field-Tested)",
    listing_extra=None,
):
    listing = None
    if price_cents is not None:
        listing = {
            "marketplace": name,
            "price_cents": price_cents,
            "item_url": "https://example.test/item",
            **(listing_extra or {}),
        }
    return {
        "marketplace": name,
        "cache_ttl_seconds": 300,
        "variants": [
            {
                "variant_id": variant_id,
                "market_hash_name": market_hash_name,
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
    assert variant["opportunities"][0]["variant_id"] == "variant-1"
    assert variant["opportunities"][0]["market_hash_name"] == (
        "AK-47 | Redline (Field-Tested)"
    )
    assert variant["opportunities"][0]["buy_price_source"] == "lowest_ask"
    assert variant["opportunities"][0]["sell_price_source"] == "lowest_ask"
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


def test_quick_flip_uses_best_ranked_buy_to_fast_buy_direction():
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
    assert opportunity["buy_price_source"] == "lowest_ask"
    assert opportunity["sell_price_source"] == "best_bid"
    assert opportunity["buy_price_cents"] == 1000
    assert opportunity["sell_price_cents"] == 900
    assert opportunity["deposit_fee_cents"] == 0
    assert opportunity["profit_cents"] == -245


def test_golden_coil_wear_variants_keep_profit_and_prices_isolated():
    """A profitable Souvenir FT quote must not decorate the $59 Normal FT ask."""
    normal_name = "M4A1-S | Golden Coil (Field-Tested)"
    souvenir_name = "Souvenir M4A1-S | Golden Coil (Field-Tested)"
    responses = []
    for marketplace, normal_price, souvenir_price in (
        ("CSFloat", 5_904, 31_627),
        ("CSGO Market", 6_373, 50_807),
    ):
        normal = market_response(
            marketplace,
            normal_price,
            variant_id="golden-coil-normal-ft",
            market_hash_name=normal_name,
        )
        souvenir = market_response(
            marketplace,
            souvenir_price,
            variant_id="golden-coil-souvenir-ft",
            market_hash_name=souvenir_name,
        )
        normal["variants"].extend(souvenir["variants"])
        responses.append(normal)

    result = compare_market_responses(
        "golden-coil",
        responses,
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=True,
        profit_mode="smart",
    )

    by_id = {variant["variant_id"]: variant for variant in result["variants"]}
    normal = by_id["golden-coil-normal-ft"]
    souvenir = by_id["golden-coil-souvenir-ft"]

    assert normal["cheapest_price_cents"] == 5_904
    assert normal["opportunities"][0]["profit_cents"] == -9
    assert all(
        opportunity["variant_id"] == "golden-coil-normal-ft"
        and opportunity["market_hash_name"] == normal_name
        and opportunity["buy_price_cents"] < 10_000
        and opportunity["sell_price_cents"] < 10_000
        for opportunity in normal["opportunities"]
    )

    assert souvenir["cheapest_price_cents"] == 31_627
    assert souvenir["opportunities"][0]["profit_cents"] == 16_224
    assert all(
        opportunity["variant_id"] == "golden-coil-souvenir-ft"
        and opportunity["market_hash_name"] == souvenir_name
        and opportunity["buy_price_cents"] > 30_000
        and opportunity["sell_price_cents"] > 30_000
        for opportunity in souvenir["opportunities"]
    )


def test_profit_ignores_liquidity_and_attachment_values():
    """Liquidity and sticker/charm metadata are display data, not cash flow."""
    result = compare_market_responses(
        "skin-1",
        [
            market_response(
                "CSFloat",
                1_000,
                listing_extra={
                    "liquidity_score": 100,
                    "stickers": [{"price_cents": 500_000}],
                    "charms": [{"price_cents": 300_000}],
                },
            ),
            market_response(
                "CSGO Market",
                1_200,
                listing_extra={"liquidity_score": 0, "stickers": [], "charms": []},
            ),
        ],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=True,
        profit_mode="smart",
    )

    opportunity = result["variants"][0]["opportunities"][0]
    assert opportunity["buy_price_cents"] == 1_000
    assert opportunity["sell_price_cents"] == 1_200
    assert opportunity["profit_cents"] == 30
    assert opportunity["cash_roi_percent"] == 2.97


def test_quick_flip_compares_every_supported_sell_market_and_ranks_net_profit():
    result = compare_market_responses(
        "skin-1",
        [
            market_response("CSFloat", 1000),
            market_response("CSGO Market", 1100),
            market_response("WhiteMarket", 1200),
        ],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=False,
        profit_mode="quick_flip",
        quick_sell_prices={
            "variant-1": {
                "csgomarket": {"best_price_cents": 1050, "error": None},
                "whitemarket": {"best_price_cents": 1180, "error": None},
            }
        },
    )

    opportunities = result["variants"][0]["opportunities"]
    assert {
        (item["buy_marketplace"], item["sell_marketplace"])
        for item in opportunities
    } == {
        ("csfloat", "csgomarket"),
        ("csfloat", "whitemarket"),
        ("csgomarket", "whitemarket"),
        ("whitemarket", "csgomarket"),
    }
    assert opportunities[0]["sell_price_cents"] == 1180


def test_quick_flip_can_choose_non_cheapest_buy_after_fees():
    result = compare_market_responses(
        "skin-1",
        [
            market_response("CSFloat", 20_000),
            market_response("CSGO Market", 20_010),
            market_response("WhiteMarket", 30_000),
        ],
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=True,
        profit_mode="quick_flip",
        quick_sell_prices={
            "variant-1": {
                "csfloat": {"best_price_cents": 23_000, "error": None},
                "whitemarket": {"best_price_cents": 25_000, "error": None},
            }
        },
    )

    best = result["variants"][0]["opportunities"][0]
    assert best["buy_marketplace"] == "csgomarket"
    assert best["sell_marketplace"] == "whitemarket"


def test_comparison_skips_direction_with_unsupported_payment_method():
    result = compare_market_responses(
        "skin-1",
        [market_response("WhiteMarket", 1000), market_response("CSFloat", 1200)],
        deposit_method="card",
        withdraw_method="crypto",
        use_deposit_fee=True,
        profit_mode="smart",
    )

    opportunities = result["variants"][0]["opportunities"]
    assert all(item["buy_marketplace"] != "whitemarket" for item in opportunities)


def test_quick_flip_loads_fast_buy_for_every_available_market(monkeypatch):
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
        "get_whitemarket_prices",
        lambda _skin_id: market_response("WhiteMarket", None),
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

    assert set(calls) == {
        ("csfloat", "variant-1"),
        ("csgomarket", "variant-1"),
    }
    assert result["variants"][0]["opportunities"][0]["sell_price_cents"] == 900
