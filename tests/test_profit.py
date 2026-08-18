from backend.app.profit import calculate_profit


def test_calculates_all_csfloat_style_fees():
    result = calculate_profit(
        buy_price_cents=1840,
        sell_price_cents=1940,
        deposit_fee_percent=1,
        sell_fee_percent=2,
        withdraw_fee_percent=1,
    )

    assert result.deposit_fee_cents == 18
    assert result.sell_fee_cents == 39
    assert result.withdraw_fee_cents == 19
    assert result.profit_cents == 24
    assert result.roi_percent == 1.29


def test_can_skip_deposit_fee_when_user_has_balance():
    result = calculate_profit(
        buy_price_cents=1840,
        sell_price_cents=1940,
        deposit_fee_percent=5,
        sell_fee_percent=0,
        withdraw_fee_percent=0,
        use_deposit_fee=False,
    )

    assert result.deposit_fee_cents == 0
    assert result.profit_cents == 100
    assert result.roi_percent == 5.43
