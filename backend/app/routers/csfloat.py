"""HTTP routes for CSFloat-backed prices, listings and detail analytics."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..catalog import get_skin
from ..market_data import (
    get_csfloat_listing_quick_sell,
    get_csfloat_prices,
    get_csfloat_skin_listings,
    get_csfloat_variant_details,
)
from ._validation import validate_listing_ranges


router = APIRouter()


@router.get("/api/skins/{skin_id}/market/csfloat")
def skin_csfloat_prices(skin_id: str):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_csfloat_prices(skin_id)


@router.get("/api/skins/{skin_id}/market/csfloat/listings")
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
    validate_listing_ranges(
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
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


@router.get("/api/variants/{variant_id}/market/csfloat")
def variant_csfloat_details(variant_id: str):
    details = get_csfloat_variant_details(variant_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return details


@router.get("/api/listings/{listing_id}/market/csfloat/quick-sell")
def listing_csfloat_quick_sell(listing_id: str):
    result = get_csfloat_listing_quick_sell(listing_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Лот CSFloat не найден")
    return result
