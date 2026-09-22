"""Backward-compatible import facade for market-data services.

New application code should import CSFloat and WhiteMarket use cases from
``app.services.market_data`` and pure liquidity calculations from
``app.analytics.liquidity``.  This module deliberately keeps the previous
imports stable for integrations and for callers that still use the legacy
module path.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .analytics.liquidity import LIQUIDITY_METHOD, calculate_liquidity
from .services import market_data as _service


# All callable implementation names remain available to legacy internal users.
# The wrappers additionally mirror test-time dependency substitutions into the
# service, which preserves the old module's patching seam during the migration.
_SERVICE_FUNCTIONS = (
    "_positive_int_env",
    "get_csfloat_prices",
    "_with_csfloat_auth_status",
    "get_whitemarket_prices",
    "_whitemarket_auth_error",
    "get_whitemarket_variant_listings",
    "get_whitemarket_skin_listings",
    "get_whitemarket_variant_quick_sell",
    "get_whitemarket_variant_details",
    "_whitemarket_listing_row",
    "_store_whitemarket_listing_rows",
    "get_csfloat_skin_listings",
    "_get_csfloat_exact_item_listings",
    "get_csfloat_listing_quick_sell",
    "get_csfloat_variant_details",
    "get_csfloat_variant_fast_buy",
    "_load_variant_detail_cache",
    "_store_variant_details",
    "_detail_response",
    "_load_skin_cache",
    "_store_csfloat_price_index",
    "_csfloat_index_row",
    "_response",
)
_INJECTABLES = (
    "get_connection",
    "validate_api_key",
    "get_active_listings",
    "get_buy_orders",
    "get_listing",
    "get_price_index",
    "get_sales_history",
    "search_market_listings",
    "get_whitemarket_active_listings",
    "get_whitemarket_buy_orders",
    "get_whitemarket_cheapest_listing",
    "_load_skin_cache",
    "_store_csfloat_price_index",
    "_store_whitemarket_listing_rows",
    "_load_variant_detail_cache",
    "_store_variant_details",
    "_detail_response",
    "_response",
    "_get_csfloat_exact_item_listings",
    "_csfloat_index_row",
)
_ORIGINALS: dict[str, Any] = {
    name: getattr(_service, name) for name in _INJECTABLES
}
_FACADE_FUNCTIONS: dict[str, Callable[..., Any]] = {}


def _synchronize_legacy_substitutions() -> None:
    for name in _INJECTABLES:
        value = globals()[name]
        if value is _FACADE_FUNCTIONS.get(name):
            value = _ORIGINALS[name]
        setattr(_service, name, value)


def _legacy_wrapper(name: str) -> Callable[..., Any]:
    implementation = getattr(_service, name)

    @wraps(implementation)
    def call(*args: Any, **kwargs: Any) -> Any:
        _synchronize_legacy_substitutions()
        return getattr(_service, name)(*args, **kwargs)

    return call


for _name in _SERVICE_FUNCTIONS:
    _FACADE_FUNCTIONS[_name] = _legacy_wrapper(_name)
    globals()[_name] = _FACADE_FUNCTIONS[_name]

for _name in _INJECTABLES:
    if _name not in globals():
        globals()[_name] = _ORIGINALS[_name]

for _name in (
    "MARKETPLACE",
    "WHITEMARKET_MARKETPLACE",
    "DEFAULT_CACHE_TTL_SECONDS",
    "DEFAULT_DETAILS_TTL_SECONDS",
    "DETAILS_VERSION",
    "WEAR_FLOAT_RANGES",
    "VARIANT_CATEGORIES",
    "WEAR_NAME_BY_SLUG",
):
    globals()[_name] = getattr(_service, _name)


__all__ = [
    "LIQUIDITY_METHOD",
    "calculate_liquidity",
    *[name for name in _SERVICE_FUNCTIONS if not name.startswith("_")],
]
