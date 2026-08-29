from backend.app.main import post_calculation
from backend.app.models import CalculationRequest


def calculation_request(mode: str, *, use_deposit_fee: bool = True):
    return CalculationRequest(
        buy_price_cents=1000,
        sell_price_cents=1200,
        buy_marketplace="csfloat",
        sell_marketplace="csgomarket",
        profit_mode=mode,
        deposit_method="crypto",
        withdraw_method="crypto",
        use_deposit_fee=use_deposit_fee,
    )


def test_manual_calculation_contract_supports_raw_mode():
    result = post_calculation(calculation_request("raw"))

    assert result.deposit_fee_cents == 0
    assert result.sell_fee_cents == 0
    assert result.withdraw_fee_cents == 0
    assert result.profit_cents == 200


def test_manual_calculation_contract_supports_enhanced_mode():
    result = post_calculation(calculation_request("enhanced"))

    assert result.deposit_fee_cents == 0
    assert result.sell_fee_cents == 60
    assert result.withdraw_fee_cents == 100
    assert result.profit_cents == 40


def test_manual_quick_flip_can_disable_deposit_fee():
    result = post_calculation(
        calculation_request("quick_flip", use_deposit_fee=False)
    )

    assert result.deposit_fee_cents == 0
    assert result.sell_fee_cents == 60
    assert result.withdraw_fee_cents == 100
