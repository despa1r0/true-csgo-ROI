from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .catalog import catalogue_size, get_catalog_filters, get_skin, search_skins
from .market_data import (
    get_csfloat_prices,
    get_csfloat_listing_quick_sell,
    get_csfloat_skin_listings,
    get_csfloat_variant_details,
)
from .mock_data import get_mock_prices
from .models import CalculationRequest, CatalogueSearchResult
from .profit import calculate_profit

load_dotenv()
app = FastAPI(title="trueROI API", version="0.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
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
    limit: int = Query(default=8, ge=1, le=20),
):
    return search_skins(
        q, weapon=weapon, rarity=rarity, collection=collection, limit=limit
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
        "prices": get_mock_prices(),
        "default_fees": {
            "deposit_fee_percent": 0,
            "sell_fee_percent": 2.0,
            "withdraw_fee_percent": 0,
        },
    }


@app.post("/api/calculate")
def post_calculation(request: CalculationRequest):
    return calculate_profit(**request.model_dump())


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
