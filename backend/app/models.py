from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MarketPrice(BaseModel):
    """Цена предмета на одной торговой площадке. Все суммы — в центах."""

    marketplace: str
    price_cents: int = Field(ge=0)
    item_url: str
    listing_id: str | None = None
    float_value: float | None = None
    quantity: int | None = Field(default=None, ge=0)
    fetched_at: datetime | None = None
    stale: bool = False


class SkinSearchResult(BaseModel):
    """Вариант скина и его текущая минимальная цена на CSFloat, если лот есть."""

    market_hash_name: str
    csfloat_price: MarketPrice | None = None
    csfloat_error: str | None = None


class CatalogueSearchResult(BaseModel):
    id: str
    name: str
    image_url: str | None = None
    weapon_id: str | None = None
    weapon_name: str | None = None
    rarity_id: str | None = None
    rarity_name: str | None = None
    rarity_color: str | None = None
    min_float: float | None = None
    max_float: float | None = None
    has_stattrak: bool
    has_souvenir: bool
    variant_count: int


class CalculationRequest(BaseModel):
    """Параметры одной сделки, которые задаёт пользователь во фронтенде."""

    buy_price_cents: int = Field(ge=0)
    sell_price_cents: int = Field(ge=0)
    buy_marketplace: str
    sell_marketplace: str
    deposit_method: Literal["card", "crypto"] = "crypto"
    withdraw_method: Literal["card", "crypto"] = "crypto"
    sell_mode: Literal["listing", "fast_buy"] = "listing"
    use_deposit_fee: bool = True


class ProfitResult(BaseModel):
    buy_price_cents: int
    deposit_fee_cents: int
    sell_price_cents: int
    sell_fee_cents: int
    withdraw_fee_cents: int
    gross_profit_cents: int
    market_profit_cents: int
    profit_cents: int
    gross_roi_percent: float
    market_roi_percent: float
    cash_roi_percent: float
    # Backward-compatible name for the main (cash) ROI.
    roi_percent: float
