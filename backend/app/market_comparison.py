"""First normalized cross-market price and profit comparison."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .csgomarket_data import (
    get_csgomarket_prices,
    get_csgomarket_variant_fast_buy,
)
from .market_data import get_csfloat_prices, get_csfloat_variant_fast_buy
from .marketplaces_fees import MARKETPLACES, FeeRule
from .profit import calculate_profit


MARKET_RESPONSE_KEYS = {
    "CSFloat": "csfloat",
    "CSGO Market": "csgomarket",
}
PROFIT_MODES = {"raw", "smart", "enhanced", "quick_flip"}


def get_skin_market_comparison(
    skin_id: str,
    *,
    deposit_method: str = "crypto",
    withdraw_method: str = "crypto",
    use_deposit_fee: bool = True,
    profit_mode: str = "smart",
) -> dict[str, Any]:
    """Load both cached indexes concurrently and compare every exact variant."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        csfloat_future = executor.submit(get_csfloat_prices, skin_id)
        csgomarket_future = executor.submit(get_csgomarket_prices, skin_id)
        csfloat = csfloat_future.result()
        csgomarket = csgomarket_future.result()
    quick_sell_prices = (
        _load_quick_sell_prices([csfloat, csgomarket])
        if profit_mode == "quick_flip"
        else None
    )
    return compare_market_responses(
        skin_id,
        [csfloat, csgomarket],
        deposit_method=deposit_method,
        withdraw_method=withdraw_method,
        use_deposit_fee=use_deposit_fee,
        profit_mode=profit_mode,
        quick_sell_prices=quick_sell_prices,
    )


def compare_market_responses(
    skin_id: str,
    market_responses: list[dict[str, Any]],
    *,
    deposit_method: str,
    withdraw_method: str,
    use_deposit_fee: bool,
    profit_mode: str = "smart",
    quick_sell_prices: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if profit_mode not in PROFIT_MODES:
        raise ValueError(f"Unsupported profit mode: {profit_mode}")
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
            variant["variant_id"],
            available,
            deposit_method=deposit_method,
            withdraw_method=withdraw_method,
            use_deposit_fee=use_deposit_fee,
            profit_mode=profit_mode,
            quick_sell_prices=quick_sell_prices or {},
        )
        variant["quick_flip_errors"] = {
            marketplace: result["error"]
            for marketplace, result in (quick_sell_prices or {})
            .get(variant["variant_id"], {})
            .items()
            if result.get("error")
        }
        compared_variants.append(variant)

    return {
        "skin_id": skin_id,
        "deposit_method": deposit_method,
        "withdraw_method": withdraw_method,
        "profit_mode": profit_mode,
        "use_deposit_fee": _effective_deposit_fee(profit_mode, use_deposit_fee),
        "marketplaces": marketplaces,
        "variants": compared_variants,
    }


def _profit_directions(
    variant_id: str,
    available: list[tuple[str, dict[str, Any]]],
    *,
    deposit_method: str,
    withdraw_method: str,
    use_deposit_fee: bool,
    profit_mode: str,
    quick_sell_prices: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    if len(available) < 2:
        return []
    if profit_mode == "quick_flip":
        buy_marketplace, buy_listing = available[0]
        sell_marketplace, _sell_listing = available[1]
        fast_buy = quick_sell_prices.get(variant_id, {}).get(sell_marketplace, {})
        sell_price_cents = fast_buy.get("best_price_cents")
        if sell_price_cents is None:
            return []
        return [
            _calculate_direction(
                buy_marketplace,
                sell_marketplace,
                buy_listing["price_cents"],
                sell_price_cents,
                deposit_method=deposit_method,
                withdraw_method=withdraw_method,
                use_deposit_fee=use_deposit_fee,
                profit_mode=profit_mode,
                sell_mode="fast_buy",
            )
        ]

    opportunities = []
    for buy_marketplace, buy_listing in available:
        for sell_marketplace, sell_listing in available:
            if buy_marketplace == sell_marketplace:
                continue
            opportunities.append(
                _calculate_direction(
                    buy_marketplace,
                    sell_marketplace,
                    buy_listing["price_cents"],
                    sell_listing["price_cents"],
                    deposit_method=deposit_method,
                    withdraw_method=withdraw_method,
                    use_deposit_fee=use_deposit_fee,
                    profit_mode=profit_mode,
                    sell_mode="listing",
                )
            )
    opportunities.sort(key=lambda item: item["profit_cents"], reverse=True)
    return opportunities


def _calculate_direction(
    buy_marketplace: str,
    sell_marketplace: str,
    buy_price_cents: int,
    sell_price_cents: int,
    *,
    deposit_method: str,
    withdraw_method: str,
    use_deposit_fee: bool,
    profit_mode: str,
    sell_mode: str,
) -> dict[str, Any]:
    buy_config = MARKETPLACES[buy_marketplace]
    sell_config = MARKETPLACES[sell_marketplace]
    effective_deposit_fee = _effective_deposit_fee(profit_mode, use_deposit_fee)
    if profit_mode == "raw":
        deposit_rule = FeeRule()
        sell_rule = FeeRule()
        withdraw_rule = FeeRule()
    else:
        deposit_rule = buy_config.fees.deposit.get(deposit_method)
        sell_rule = sell_config.fees.sell
        withdraw_rule = sell_config.fees.withdraw.get(withdraw_method)
    result = calculate_profit(
        buy_price_cents=buy_price_cents,
        sell_price_cents=sell_price_cents,
        deposit_rule=deposit_rule,
        sell_rule=sell_rule,
        withdraw_rule=withdraw_rule,
        use_deposit_fee=effective_deposit_fee,
    )
    return {
        "buy_marketplace": buy_marketplace,
        "sell_marketplace": sell_marketplace,
        "profit_mode": profit_mode,
        "sell_mode": sell_mode,
        **result.model_dump(),
    }


def _effective_deposit_fee(profit_mode: str, requested: bool) -> bool:
    if profit_mode == "smart":
        return True
    if profit_mode in {"raw", "enhanced"}:
        return False
    return requested


def _load_quick_sell_prices(
    market_responses: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    variants: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for response in market_responses:
        marketplace = MARKET_RESPONSE_KEYS[response["marketplace"]]
        for item in response.get("variants", []):
            if item.get("listing") is not None:
                variants.setdefault(item["variant_id"], []).append(
                    (marketplace, item["listing"])
                )

    targets = []
    for variant_id, available in variants.items():
        if len(available) < 2:
            continue
        available.sort(key=lambda pair: pair[1]["price_cents"])
        sell_marketplace = available[1][0]
        targets.append((variant_id, sell_marketplace))

    results: dict[str, dict[str, dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=min(3, len(targets) or 1)) as executor:
        futures = {
            executor.submit(
                get_csfloat_variant_fast_buy
                if marketplace == "csfloat"
                else get_csgomarket_variant_fast_buy,
                variant_id,
            ): (variant_id, marketplace)
            for variant_id, marketplace in targets
        }
        for future, (variant_id, marketplace) in futures.items():
            try:
                result = future.result()
            except Exception as error:  # Keep one marketplace failure isolated.
                result = {"best_price_cents": None, "error": str(error)}
            results.setdefault(variant_id, {})[marketplace] = result or {
                "best_price_cents": None,
                "error": "Вариант не найден",
            }
    return results
