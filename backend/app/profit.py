from decimal import Decimal, ROUND_HALF_UP

from .marketplaces_fees import FeeRule
from .models import ProfitResult


def calculate_fee(amount_cents: int, rule: FeeRule) -> int:
    """Calculate a percentage plus fixed fee, rounded to the nearest cent."""
    percent_fee = (
        Decimal(amount_cents) * Decimal(str(rule.percent)) / Decimal("100")
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(percent_fee) + rule.fixed_cents


def calculate_profit(
    *,
    buy_price_cents: int,
    sell_price_cents: int,
    deposit_rule: FeeRule | None,
    sell_rule: FeeRule,
    withdraw_rule: FeeRule | None,
    use_deposit_fee: bool = True,
) -> ProfitResult:
    """Calculate a deal from prices and already selected marketplace fee rules."""
    deposit_fee_cents = (
        calculate_fee(buy_price_cents, deposit_rule)
        if use_deposit_fee and deposit_rule is not None
        else 0
    )
    sell_fee_cents = calculate_fee(sell_price_cents, sell_rule)
    withdraw_fee_cents = (
        calculate_fee(sell_price_cents, withdraw_rule)
        if withdraw_rule is not None
        else 0
    )

    gross_profit_cents = sell_price_cents - buy_price_cents
    market_profit_cents = sell_price_cents - sell_fee_cents - buy_price_cents
    effective_buy_cents = buy_price_cents + deposit_fee_cents
    effective_payout_cents = sell_price_cents - sell_fee_cents - withdraw_fee_cents
    profit_cents = effective_payout_cents - effective_buy_cents

    def roi(profit: int, cost: int) -> float:
        return 0 if cost == 0 else round(profit / cost * 100, 2)

    return ProfitResult(
        buy_price_cents=buy_price_cents,
        deposit_fee_cents=deposit_fee_cents,
        sell_price_cents=sell_price_cents,
        sell_fee_cents=sell_fee_cents,
        withdraw_fee_cents=withdraw_fee_cents,
        gross_profit_cents=gross_profit_cents,
        market_profit_cents=market_profit_cents,
        profit_cents=profit_cents,
        gross_roi_percent=roi(gross_profit_cents, buy_price_cents),
        market_roi_percent=roi(market_profit_cents, buy_price_cents),
        cash_roi_percent=roi(profit_cents, effective_buy_cents),
        roi_percent=roi(profit_cents, effective_buy_cents),
    )


# Temporary compatibility for imports of the old helper name.
calculate = calculate_fee
