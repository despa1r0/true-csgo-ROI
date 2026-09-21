"""HTTP routes for CSGO Market prices, listings and detail analytics."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..catalog import get_skin
from ..csgomarket_data import (
    get_csgomarket_prices,
    get_csgomarket_skin_listings,
    get_csgomarket_variant_details,
)
from ._validation import validate_listing_ranges


router = APIRouter()


@router.get("/api/skins/{skin_id}/market/csgomarket")
def skin_csgomarket_prices(skin_id: str):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_csgomarket_prices(skin_id)


@router.get("/api/skins/{skin_id}/market/csgomarket/listings")
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
    validate_listing_ranges(
        min_float=min_float,
        max_float=max_float,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
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


@router.get("/api/variants/{variant_id}/market/csgomarket")
def variant_csgomarket_details(variant_id: str):
    details = get_csgomarket_variant_details(variant_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return details
