from .models import ProfitResult
from .marketplaces_fees import FeeRule


def calculate_profit(
    buy_price_cents: int,
    sell_price_cents: int,
    deposit_fee_percent: float = 0,
    sell_fee_percent: float = 0,
    withdraw_fee_percent: float = 0,
    use_deposit_fee: bool = True,
) -> ProfitResult:
    """Рассчитывает итог сделки. Никаких API-запросов здесь быть не должно."""
    deposit_fee_cents = (
        round(buy_price_cents * deposit_fee_percent / 100) if use_deposit_fee else 0
    )
    sell_fee_cents = round(sell_price_cents * sell_fee_percent / 100)
    withdraw_fee_cents = round(sell_price_cents * withdraw_fee_percent / 100)

    effective_buy_cents = buy_price_cents + deposit_fee_cents
    effective_payout_cents = sell_price_cents - sell_fee_cents - withdraw_fee_cents
    profit_cents = effective_payout_cents - effective_buy_cents
    roi_percent = (
        0 if effective_buy_cents == 0 else round(profit_cents / effective_buy_cents * 100, 2)
    )

    return ProfitResult(
        buy_price_cents=buy_price_cents,
        deposit_fee_cents=deposit_fee_cents,
        sell_price_cents=sell_price_cents,
        sell_fee_cents=sell_fee_cents,
        withdraw_fee_cents=withdraw_fee_cents,
        profit_cents=profit_cents,
        roi_percent=roi_percent,
    )

def calculate(amount_cents: int, rule: FeeRule) -> int:
    return round(amount_cents * rule.percent / 100) + rule.fixed_cents
