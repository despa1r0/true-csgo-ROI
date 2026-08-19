from pydantic import BaseModel, Field


class MarketPrice(BaseModel):
    """Цена предмета на одной торговой площадке. Все суммы — в центах."""

    marketplace: str
    price_cents: int = Field(ge=0)
    item_url: str


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
    use_deposit_fee: bool = True
    deposit_fee_percent: float = Field(default=0, ge=0)
    sell_fee_percent: float = Field(default=0, ge=0)
    withdraw_fee_percent: float = Field(default=0, ge=0)


class ProfitResult(BaseModel):
    buy_price_cents: int
    deposit_fee_cents: int
    sell_price_cents: int
    sell_fee_cents: int
    withdraw_fee_cents: int
    profit_cents: int
    roi_percent: float
