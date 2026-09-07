from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .catalog import catalogue_size, get_catalog_filters, get_skin, search_skins
from .csgomarket_data import (
    get_csgomarket_prices,
    get_csgomarket_skin_listings,
    get_csgomarket_variant_details,
)
from .market_comparison import get_skin_market_comparison
from .market_data import (
    get_csfloat_prices,
    get_csfloat_listing_quick_sell,
    get_csfloat_skin_listings,
    get_csfloat_variant_details,
    get_whitemarket_prices,
    get_whitemarket_skin_listings,
    get_whitemarket_variant_details,
    get_whitemarket_variant_listings,
    get_whitemarket_variant_quick_sell,
)
from .marketplaces_fees import FEE_CONFIGURATION_VERSION, MARKETPLACES, FeeRule
from .models import AppliedFee, AppliedFees, CalculationRequest, CatalogueSearchResult
from .profit import calculate_fee, calculate_profit

load_dotenv()
app = FastAPI(title="trueROI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8005", "http://127.0.0.1:8005"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "catalogue": catalogue_size()}


@app.get("/api/catalog/filters")
def catalog_filters():
    return get_catalog_filters()


@app.get("/api/skins/search", response_model=list[CatalogueSearchResult])
def skin_search(
    q: str = Query(default="", max_length=100),
    weapon: str | None = None,
    rarity: str | None = None,
    collection: str | None = None,
    item_type: str | None = None,
    limit: int = Query(default=8, ge=1, le=20),
):
    return search_skins(
        q,
        weapon=weapon,
        rarity=rarity,
        collection=collection,
        item_type=item_type,
        limit=limit,
    )


@app.get("/api/items/search", response_model=list[CatalogueSearchResult])
def item_search(
    q: str = Query(default="", max_length=100),
    weapon: str | None = None,
    rarity: str | None = None,
    collection: str | None = None,
    item_type: str | None = None,
    limit: int = Query(default=8, ge=1, le=20),
):
    """Search the complete imported catalogue, including non-weapon items."""
    return search_skins(
        q,
        weapon=weapon,
        rarity=rarity,
        collection=collection,
        item_type=item_type,
        limit=limit,
    )


@app.get("/api/skins/{skin_id}")
def skin_details(skin_id: str):
    skin = get_skin(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return skin


@app.get("/api/skins/{skin_id}/market/csfloat")
def skin_csfloat_prices(skin_id: str):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_csfloat_prices(skin_id)


@app.get("/api/skins/{skin_id}/market/whitemarket")
def skin_whitemarket_prices(skin_id: str):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_whitemarket_prices(skin_id)


@app.get("/api/skins/{skin_id}/market/whitemarket/listings")
def skin_whitemarket_listings(
    skin_id: str,
    sort_by: Literal["best_deal", "lowest_price"] = "lowest_price",
    wear: Literal[
        "factory-new",
        "minimal-wear",
        "field-tested",
        "well-worn",
        "battle-scarred",
    ]
    | None = None,
    variant: Literal["any", "normal", "stattrak", "souvenir"] = "any",
    min_float: float | None = Query(default=None, ge=0, le=1),
    max_float: float | None = Query(default=None, ge=0, le=1),
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = Query(default=30, ge=1, le=50),
):
    if min_float is not None and max_float is not None and min_float > max_float:
        raise HTTPException(status_code=422, detail="Минимальный float больше максимального")
    if (
        min_price_cents is not None
        and max_price_cents is not None
        and min_price_cents > max_price_cents
    ):
        raise HTTPException(status_code=422, detail="Минимальная цена больше максимальной")
    result = get_whitemarket_skin_listings(
        skin_id,
        sort_by=sort_by,
        wear=wear,
        variant=variant,
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        has_stickers=has_stickers,
        has_charm=has_charm,
        limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return result


@app.get("/api/skins/{skin_id}/market/csgomarket")
def skin_csgomarket_prices(skin_id: str):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_csgomarket_prices(skin_id)


@app.get("/api/skins/{skin_id}/markets/compare")
def skin_market_comparison(
    skin_id: str,
    profit_mode: Literal["raw", "smart", "enhanced", "quick_flip"] = "smart",
    deposit_method: Literal["card", "crypto"] = "crypto",
    withdraw_method: Literal["card", "crypto"] = "crypto",
    use_deposit_fee: bool = True,
):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_skin_market_comparison(
        skin_id,
        deposit_method=deposit_method,
        withdraw_method=withdraw_method,
        use_deposit_fee=use_deposit_fee,
        profit_mode=profit_mode,
    )


@app.get("/api/skins/{skin_id}/market/csgomarket/listings")
def skin_csgomarket_listings(
    skin_id: str,
    sort_by: Literal["best_deal", "lowest_price"] = "lowest_price",
    wear: Literal[
        "factory-new",
        "minimal-wear",
        "field-tested",
        "well-worn",
        "battle-scarred",
    ]
    | None = None,
    variant: Literal["any", "normal", "stattrak", "souvenir"] = "any",
    min_float: float | None = Query(default=None, ge=0, le=1),
    max_float: float | None = Query(default=None, ge=0, le=1),
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = Query(default=30, ge=1, le=50),
):
    if min_float is not None and max_float is not None and min_float > max_float:
        raise HTTPException(status_code=422, detail="Минимальный float больше максимального")
    if (
        min_price_cents is not None
        and max_price_cents is not None
        and min_price_cents > max_price_cents
    ):
        raise HTTPException(status_code=422, detail="Минимальная цена больше максимальной")
    result = get_csgomarket_skin_listings(
        skin_id,
        sort_by=sort_by,
        wear=wear,
        variant=variant,
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        has_stickers=has_stickers,
        has_charm=has_charm,
        limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return result


@app.get("/api/skins/{skin_id}/market/csfloat/listings")
def skin_csfloat_listings(
    skin_id: str,
    sort_by: Literal["best_deal", "lowest_price"] = "best_deal",
    wear: Literal[
        "factory-new",
        "minimal-wear",
        "field-tested",
        "well-worn",
        "battle-scarred",
    ]
    | None = None,
    variant: Literal["any", "normal", "stattrak", "souvenir"] = "any",
    min_float: float | None = Query(default=None, ge=0, le=1),
    max_float: float | None = Query(default=None, ge=0, le=1),
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = Query(default=30, ge=1, le=50),
):
    if min_float is not None and max_float is not None and min_float > max_float:
        raise HTTPException(status_code=422, detail="Минимальный float больше максимального")
    if (
        min_price_cents is not None
        and max_price_cents is not None
        and min_price_cents > max_price_cents
    ):
        raise HTTPException(status_code=422, detail="Минимальная цена больше максимальной")
    result = get_csfloat_skin_listings(
        skin_id,
        sort_by=sort_by,
        wear=wear,
        variant=variant,
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        has_stickers=has_stickers,
        has_charm=has_charm,
        limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return result


@app.get("/api/variants/{variant_id}/market/csfloat")
def variant_csfloat_details(variant_id: str):
    details = get_csfloat_variant_details(variant_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return details


@app.get("/api/variants/{variant_id}/market/whitemarket")
def variant_whitemarket_details(variant_id: str):
    details = get_whitemarket_variant_details(variant_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return details


@app.get("/api/variants/{variant_id}/market/whitemarket/listings")
def variant_whitemarket_listings(
    variant_id: str,
    min_float: float | None = Query(default=None, ge=0, le=1),
    max_float: float | None = Query(default=None, ge=0, le=1),
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    has_stickers: bool = False,
    has_charm: bool = False,
    limit: int = Query(default=30, ge=1, le=50),
):
    if min_float is not None and max_float is not None and min_float > max_float:
        raise HTTPException(status_code=422, detail="Минимальный float больше максимального")
    if (
        min_price_cents is not None
        and max_price_cents is not None
        and min_price_cents > max_price_cents
    ):
        raise HTTPException(status_code=422, detail="Минимальная цена больше максимальной")
    result = get_whitemarket_variant_listings(
        variant_id,
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        has_stickers=has_stickers,
        has_charm=has_charm,
        limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return result


@app.get("/api/variants/{variant_id}/market/whitemarket/quick-sell")
def variant_whitemarket_quick_sell(variant_id: str):
    result = get_whitemarket_variant_quick_sell(variant_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return result


@app.get("/api/variants/{variant_id}/market/csgomarket")
def variant_csgomarket_details(variant_id: str):
    details = get_csgomarket_variant_details(variant_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return details


@app.get("/api/listings/{listing_id}/market/csfloat/quick-sell")
def listing_csfloat_quick_sell(listing_id: str):
    result = get_csfloat_listing_quick_sell(listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Лот CSFloat не найден")
    return result


@app.get("/api/market-overview")
def get_market_overview():
    return {
        "item_name": "AK-47 | Redline (Field-Tested)",
        "marketplaces": marketplace_options(),
    }


def marketplace_options():
    """Public data for populating buy/sell and fast-buy selectors."""
    return [
        {
            "id": name,
            "display_name": marketplace.display_name,
            "currency": marketplace.currency,
            "can_buy": marketplace.can_buy,
            "can_sell": marketplace.can_sell,
            "supports_fast_buy": marketplace.supports_fast_buy,
            "capabilities": {
                "can_buy": marketplace.can_buy,
                "can_sell": marketplace.can_sell,
                "supports_listings": marketplace.supports_listings,
                "supports_sales_history": marketplace.supports_sales_history,
                "supports_quick_sell": marketplace.supports_fast_buy,
                "supports_float": marketplace.supports_float,
                "supports_stickers": marketplace.supports_stickers,
                "supports_charms": marketplace.supports_charms,
                "supports_best_deal_sort": marketplace.supports_best_deal_sort,
            },
            "deposit_methods": [
                method
                for method, rule in marketplace.fees.deposit.items()
                if rule is not None
            ],
            "withdraw_methods": [
                method
                for method, rule in marketplace.fees.withdraw.items()
                if rule is not None
            ],
            "fees": {
                "deposit": {
                    method: _public_fee_rule(rule)
                    for method, rule in marketplace.fees.deposit.items()
                },
                "sell": _public_fee_rule(marketplace.fees.sell),
                "withdraw": {
                    method: _public_fee_rule(rule)
                    for method, rule in marketplace.fees.withdraw.items()
                },
            },
            "fee_configuration_version": FEE_CONFIGURATION_VERSION,
        }
        for name, marketplace in MARKETPLACES.items()
    ]


def _public_fee_rule(rule: FeeRule | None):
    if rule is None:
        return None
    return {"percent": rule.percent, "fixed_cents": rule.fixed_cents}


@app.get("/api/marketplaces")
def get_marketplaces():
    return marketplace_options()


@app.post("/api/calculate")
def post_calculation(request: CalculationRequest):
    buy_marketplace = MARKETPLACES.get(request.buy_marketplace)
    sell_marketplace = MARKETPLACES.get(request.sell_marketplace)

    if buy_marketplace is None:
        raise HTTPException(status_code=422, detail="Unknown buy marketplace")
    if sell_marketplace is None:
        raise HTTPException(status_code=422, detail="Unknown sell marketplace")
    if not buy_marketplace.can_buy:
        raise HTTPException(status_code=422, detail="Marketplace does not support buying")
    if not sell_marketplace.can_sell or sell_marketplace.fees.sell is None:
        raise HTTPException(status_code=422, detail="Marketplace does not support selling")
    sell_mode = "fast_buy" if request.profit_mode == "quick_flip" else request.sell_mode
    if sell_mode == "fast_buy" and not sell_marketplace.supports_fast_buy:
        raise HTTPException(status_code=422, detail="Marketplace does not support fast buy")

    use_deposit_fee, use_sell_fee, use_withdraw_fee = _fee_selection(request)
    configured_deposit_rule = buy_marketplace.fees.deposit.get(
        request.deposit_method
    )
    configured_sell_rule = sell_marketplace.fees.sell
    configured_withdraw_rule = sell_marketplace.fees.withdraw.get(
        request.withdraw_method
    )

    if use_deposit_fee and configured_deposit_rule is None:
        raise HTTPException(status_code=422, detail="Unsupported deposit method")
    if use_withdraw_fee and configured_withdraw_rule is None:
        raise HTTPException(status_code=422, detail="Unsupported withdrawal method")

    deposit_rule = configured_deposit_rule if use_deposit_fee else FeeRule()
    sell_rule = configured_sell_rule if use_sell_fee else FeeRule()
    withdraw_rule = configured_withdraw_rule if use_withdraw_fee else FeeRule()

    result = calculate_profit(
        buy_price_cents=request.buy_price_cents,
        sell_price_cents=request.sell_price_cents,
        deposit_rule=deposit_rule,
        sell_rule=sell_rule,
        withdraw_rule=withdraw_rule,
        use_deposit_fee=use_deposit_fee,
    )
    applied_fees = AppliedFees(
        deposit=_applied_fee(
            configured_deposit_rule,
            enabled=use_deposit_fee,
            amount_cents=result.deposit_fee_cents,
            method=request.deposit_method,
        ),
        sell=_applied_fee(
            configured_sell_rule,
            enabled=use_sell_fee,
            amount_cents=result.sell_fee_cents,
        ),
        withdraw=_applied_fee(
            configured_withdraw_rule,
            enabled=use_withdraw_fee,
            amount_cents=result.withdraw_fee_cents,
            method=request.withdraw_method,
        ),
    )
    return result.model_copy(
        update={
            "break_even_sell_price_cents": _break_even_sell_price_cents(
                result.effective_buy_cents or 0,
                sell_rule,
                withdraw_rule,
            ),
            "applied_fees": applied_fees,
            "fee_configuration_version": FEE_CONFIGURATION_VERSION,
        }
    )


def _fee_selection(request: CalculationRequest) -> tuple[bool, bool, bool]:
    """Resolve fee presets while preserving the four original mode contracts."""
    if request.profit_mode == "raw":
        return False, False, False
    if request.profit_mode == "smart":
        return True, True, True
    if request.profit_mode == "enhanced":
        return False, True, True
    if request.profit_mode == "quick_flip":
        return request.use_deposit_fee, True, True
    return (
        request.use_deposit_fee,
        request.use_sell_fee,
        request.use_withdraw_fee,
    )


def _applied_fee(
    rule: FeeRule | None,
    *,
    enabled: bool,
    amount_cents: int,
    method: Literal["card", "crypto"] | None = None,
) -> AppliedFee:
    return AppliedFee(
        enabled=enabled,
        amount_cents=amount_cents,
        percent=rule.percent if rule is not None else 0,
        fixed_cents=rule.fixed_cents if rule is not None else 0,
        method=method,
    )


def _break_even_sell_price_cents(
    effective_buy_cents: int,
    sell_rule: FeeRule,
    withdraw_rule: FeeRule | None,
) -> int:
    """Find the lowest integer sale price whose payout covers the cash cost."""

    def payout(price_cents: int) -> int:
        return (
            price_cents
            - calculate_fee(price_cents, sell_rule)
            - (
                calculate_fee(price_cents, withdraw_rule)
                if withdraw_rule is not None
                else 0
            )
        )

    low = 0
    high = max(effective_buy_cents, 1)
    while payout(high) < effective_buy_cents:
        high *= 2
    while low < high:
        middle = (low + high) // 2
        if payout(middle) >= effective_buy_cents:
            high = middle
        else:
            low = middle + 1
    return low


class SPAStaticFiles(StaticFiles):
    """Serve the React entry point for client-side routes, but never for API 404s."""

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code == 404 and not scope.get("path", "").startswith("/api/"):
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and not scope.get("path", "").startswith("/api/"):
            return await super().get_response("index.html", scope)
        return response


PROJECT_DIR = Path(__file__).resolve().parents[2]
REACT_DIST_DIR = PROJECT_DIR / "frontend-react" / "dist"
FRONTEND_DIR = REACT_DIST_DIR if REACT_DIST_DIR.exists() else PROJECT_DIR / "frontend"
app.mount("/", SPAStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
