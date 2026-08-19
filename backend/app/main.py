from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .catalog import catalogue_size, get_catalog_filters, get_skin, search_skins
from .mock_data import get_mock_prices
from .models import CalculationRequest, CatalogueSearchResult
from .profit import calculate_profit

load_dotenv()
app = FastAPI(title="trueROI API", version="0.2.0")

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
    q: str = Query(min_length=2, max_length=100),
    weapon: str | None = None,
    rarity: str | None = None,
    limit: int = Query(default=8, ge=1, le=20),
):
    return search_skins(q, weapon=weapon, rarity=rarity, limit=limit)


@app.get("/api/skins/{skin_id}")
def skin_details(skin_id: str):
    skin = get_skin(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Скин не найден")
    return skin


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
