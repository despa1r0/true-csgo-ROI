"""First normalized cross-market price and profit comparison."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .csgomarket_data import get_csgomarket_prices
from .market_data import get_csfloat_prices
from .marketplaces_fees import MARKETPLACES
from .profit import calculate_profit


MARKET_RESPONSE_KEYS = {
    "CSFloat": "csfloat",
    "CSGO Market": "csgomarket",
}


def get_skin_market_comparison(
    skin_id: str,
    *,
    deposit_method: str = "crypto",
    withdraw_method: str = "crypto",
    use_deposit_fee: bool = True,
) -> dict[str, Any]:
    """Load both cached indexes concurrently and compare every exact variant."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        csfloat_future = executor.submit(get_csfloat_prices, skin_id)
        csgomarket_future = executor.submit(get_csgomarket_prices, skin_id)
        csfloat = csfloat_future.result()
        csgomarket = csgomarket_future.result()
    return compare_market_responses(
        skin_id,
        [csfloat, csgomarket],
        deposit_method=deposit_method,
        withdraw_method=withdraw_method,
        use_deposit_fee=use_deposit_fee,
    )


def compare_market_responses(
    skin_id: str,
    market_responses: list[dict[str, Any]],
    *,
    deposit_method: str,
    withdraw_method: str,
    use_deposit_fee: bool,
) -> dict[str, Any]:
    variants: dict[str, dict[str, Any]] = {}
    marketplaces = []
    for response in market_responses:
        marketplace_name = response["marketplace"]
        marketplace_key = MARKET_RESPONSE_KEYS[marketplace_name]
        marketplace_errors = []
        for item in response.get("variants", []):
            variant = variants.setdefault(
                item["variant_id"],
                {
                    "variant_id": item["variant_id"],
                    "market_hash_name": item["market_hash_name"],
                    "markets": {},
                    "errors": {},
                },
            )
            variant["markets"][marketplace_key] = item.get("listing")
            if item.get("error"):
                variant["errors"][marketplace_key] = item["error"]
                marketplace_errors.append(item["error"])
        marketplaces.append(
            {
                "id": marketplace_key,
                "name": marketplace_name,
                "cache_ttl_seconds": response.get("cache_ttl_seconds"),
                "error": marketplace_errors[0] if marketplace_errors else None,
            }
        )

    compared_variants = []
    for variant in variants.values():
        available = [
            (marketplace, listing)
            for marketplace, listing in variant["markets"].items()
            if listing is not None
        ]
        available.sort(key=lambda pair: pair[1]["price_cents"])
        variant["cheapest_marketplace"] = available[0][0] if available else None
        variant["cheapest_price_cents"] = (
            available[0][1]["price_cents"] if available else None
        )
        variant["gross_spread_cents"] = (
            available[-1][1]["price_cents"] - available[0][1]["price_cents"]
            if len(available) >= 2
            else None
        )
        variant["opportunities"] = _profit_directions(
            available,
            deposit_method=deposit_method,
            withdraw_method=withdraw_method,
            use_deposit_fee=use_deposit_fee,
        )
        compared_variants.append(variant)

    return {
        "skin_id": skin_id,
        "deposit_method": deposit_method,
        "withdraw_method": withdraw_method,
        "use_deposit_fee": use_deposit_fee,
        "marketplaces": marketplaces,
        "variants": compared_variants,
    }


def _profit_directions(
    available: list[tuple[str, dict[str, Any]]],
    *,
    deposit_method: str,
    withdraw_method: str,
    use_deposit_fee: bool,
) -> list[dict[str, Any]]:
    if len(available) < 2:
        return []
    opportunities = []
    for buy_marketplace, buy_listing in available:
        for sell_marketplace, sell_listing in available:
            if buy_marketplace == sell_marketplace:
                continue
            buy_config = MARKETPLACES[buy_marketplace]
            sell_config = MARKETPLACES[sell_marketplace]
            deposit_rule = buy_config.fees.deposit.get(deposit_method)
            withdraw_rule = sell_config.fees.withdraw.get(withdraw_method)
            if (use_deposit_fee and deposit_rule is None) or withdraw_rule is None:
                continue
            result = calculate_profit(
                buy_price_cents=buy_listing["price_cents"],
                sell_price_cents=sell_listing["price_cents"],
                deposit_rule=deposit_rule,
                sell_rule=sell_config.fees.sell,
                withdraw_rule=withdraw_rule,
                use_deposit_fee=use_deposit_fee,
            )
            opportunities.append(
                {
                    "buy_marketplace": buy_marketplace,
                    "sell_marketplace": sell_marketplace,
                    **result.model_dump(),
                }
            )
    opportunities.sort(key=lambda item: item["profit_cents"], reverse=True)
    return opportunities
