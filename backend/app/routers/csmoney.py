"""HTTP routes for cached CS.MONEY data and Wiki price history."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..catalog import get_skin
from ..csmoney_data import (
    get_csmoney_prices,
    get_csmoney_skin_listings,
    get_csmoney_variant_details,
)
from ..csmoney_wiki import get_variant_price_history
from ..csmoney_search import enqueue_search, get_search, normalize_query
from ..catalog import search_skins
from ._validation import validate_listing_ranges


router = APIRouter()


class TextSearchRequest(BaseModel):
    query: str


@router.post("/api/market/csmoney/search", status_code=202)
def create_csmoney_search(request: TextSearchRequest):
    try:
        query, _normalized = normalize_query(request.query)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if search_skins(query, limit=1):
        raise HTTPException(status_code=409, detail="Item already exists in the local catalogue")
    return enqueue_search(query)


@router.get("/api/market/csmoney/search/{request_id}")
def csmoney_search_status(request_id: UUID):
    result = get_search(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Search request not found")
    return result


@router.get("/api/skins/{skin_id}/market/csmoney")
def skin_csmoney_prices(skin_id: str):
    if get_skin(skin_id) is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return get_csmoney_prices(skin_id)


@router.get("/api/skins/{skin_id}/market/csmoney/listings")
def skin_csmoney_listings(
    skin_id: str,
    sort_by: Literal["best_deal", "lowest_price"] = "lowest_price",
    wear: Literal[
        "factory-new", "minimal-wear", "field-tested", "well-worn", "battle-scarred"
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
    result = get_csmoney_skin_listings(
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


@router.get("/api/variants/{variant_id}/market/csmoney")
def variant_csmoney_details(variant_id: str):
    details = get_csmoney_variant_details(variant_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return details


@router.get("/api/variants/{variant_id}/market/csmoney/price-history")
def variant_csmoney_price_history(variant_id: str):
    result = get_variant_price_history(variant_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Вариант скина не найден")
    return result
