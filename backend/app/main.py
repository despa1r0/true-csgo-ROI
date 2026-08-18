from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .catalog import find_skins
from .csfloat import CsfloatRequestError, get_lowest_price
from .mock_data import get_mock_prices
from .models import CalculationRequest, SkinSearchResult
from .profit import calculate_profit

app = FastAPI(title="Skin Market Tracker API")
load_dotenv()

# Vite запускает фронтенд отдельно, поэтому в разработке разрешаем этот origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/search", response_model=list[SkinSearchResult])
def search_skins(q: str = Query(min_length=2, max_length=100)):
    """Ищет во временном каталоге и показывает live-цену CSFloat для каждого совпадения."""
    results = []
    for skin_name in find_skins(q):
        try:
            results.append(
                SkinSearchResult(
                    market_hash_name=skin_name,
                    csfloat_price=get_lowest_price(skin_name),
                )
            )
        except CsfloatRequestError as error:
            results.append(
                SkinSearchResult(market_hash_name=skin_name, csfloat_error=str(error))
            )
    return results


@app.post("/api/calculate")
def post_calculation(request: CalculationRequest):
    return calculate_profit(**request.model_dump())
