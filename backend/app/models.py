from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    item_type: str = "skin"
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
    """User-controlled inputs for one profit calculation."""

    # Fee rates are intentionally not part of the request contract. They are
    # selected from the server-side marketplace registry in every calculation.
    model_config = ConfigDict(extra="forbid")

    buy_price_cents: int = Field(ge=0)
    sell_price_cents: int = Field(ge=0)
    buy_marketplace: str
    sell_marketplace: str
    profit_mode: Literal["raw", "smart", "enhanced", "quick_flip", "custom"] = (
        "smart"
    )
    deposit_method: Literal["card", "crypto"] = "crypto"
    withdraw_method: Literal["card", "crypto"] = "crypto"
    sell_mode: Literal["listing", "fast_buy"] = "listing"
    use_deposit_fee: bool = True
    use_sell_fee: bool = True
    use_withdraw_fee: bool = True


class AppliedFee(BaseModel):
    """One server-owned fee rule and its effect on this calculation."""

    enabled: bool
    amount_cents: int = Field(ge=0)
    percent: float = Field(ge=0)
    fixed_cents: int = Field(ge=0)
    method: Literal["card", "crypto"] | None = None


class AppliedFees(BaseModel):
    deposit: AppliedFee
    sell: AppliedFee
    withdraw: AppliedFee


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
    effective_buy_cents: int | None = Field(default=None, ge=0)
    effective_payout_cents: int | None = None
    break_even_sell_price_cents: int | None = Field(default=None, ge=0)
    applied_fees: AppliedFees | None = None
    fee_configuration_version: str | None = None

    def model_post_init(self, __context: object) -> None:
        # Keep calculate_profit's long-standing call signature compatible while
        # exposing the two intermediate totals useful to API clients.
        if self.effective_buy_cents is None:
            self.effective_buy_cents = self.buy_price_cents + self.deposit_fee_cents
        if self.effective_payout_cents is None:
            self.effective_payout_cents = (
                self.sell_price_cents
                - self.sell_fee_cents
                - self.withdraw_fee_cents
            )
