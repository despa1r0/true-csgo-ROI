from backend.app.marketplaces_fees import FeeRule, MARKETPLACES
from backend.app.profit import calculate_profit


def test_calculates_all_fee_rules_and_three_roi_levels():
    result = calculate_profit(
        buy_price_cents=1840,
        sell_price_cents=1940,
        deposit_rule=FeeRule(percent=1),
        sell_rule=FeeRule(percent=2),
        withdraw_rule=FeeRule(percent=1),
    )

    assert result.deposit_fee_cents == 18
    assert result.sell_fee_cents == 39
    assert result.withdraw_fee_cents == 19
    assert result.gross_profit_cents == 100
    assert result.market_profit_cents == 61
    assert result.profit_cents == 24
    assert result.gross_roi_percent == 5.43
    assert result.market_roi_percent == 3.32
    assert result.cash_roi_percent == 1.29
    assert result.roi_percent == 1.29


def test_uses_fixed_fee_and_can_skip_deposit_fee():
    result = calculate_profit(
        buy_price_cents=1840,
        sell_price_cents=1940,
        deposit_rule=FeeRule(percent=2.8, fixed_cents=30),
        sell_rule=FeeRule(),
        withdraw_rule=FeeRule(),
        use_deposit_fee=False,
    )

    assert result.deposit_fee_cents == 0
    assert result.profit_cents == 100
    assert result.cash_roi_percent == 5.43


def test_fixed_fee_is_included_when_deposit_is_used():
    result = calculate_profit(
        buy_price_cents=1000,
        sell_price_cents=1100,
        deposit_rule=FeeRule(percent=2.8, fixed_cents=30),
        sell_rule=FeeRule(),
        withdraw_rule=FeeRule(),
    )

    assert result.deposit_fee_cents == 58
    assert result.profit_cents == 42


def test_existing_marketplaces_support_selling():
    assert all(marketplace.can_sell for marketplace in MARKETPLACES.values())
    assert all(marketplace.fees.sell is not None for marketplace in MARKETPLACES.values())
