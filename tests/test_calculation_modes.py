import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.main import marketplace_options, post_calculation
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


@pytest.mark.parametrize(
    ("use_deposit_fee", "use_sell_fee", "use_withdraw_fee", "expected_profit"),
    [
        (False, False, False, 200),
        (True, False, False, 190),
        (False, True, False, 140),
        (False, False, True, 100),
        (True, True, False, 130),
        (True, False, True, 90),
        (False, True, True, 40),
        (True, True, True, 30),
    ],
)
def test_custom_mode_supports_every_independent_fee_combination(
    use_deposit_fee,
    use_sell_fee,
    use_withdraw_fee,
    expected_profit,
):
    result = post_calculation(
        CalculationRequest(
            buy_price_cents=1000,
            sell_price_cents=1200,
            buy_marketplace="csfloat",
            sell_marketplace="csgomarket",
            profit_mode="custom",
            deposit_method="crypto",
            withdraw_method="crypto",
            use_deposit_fee=use_deposit_fee,
            use_sell_fee=use_sell_fee,
            use_withdraw_fee=use_withdraw_fee,
        )
    )

    assert result.deposit_fee_cents == (10 if use_deposit_fee else 0)
    assert result.sell_fee_cents == (60 if use_sell_fee else 0)
    assert result.withdraw_fee_cents == (100 if use_withdraw_fee else 0)
    assert result.profit_cents == expected_profit
    assert result.applied_fees.deposit.enabled is use_deposit_fee
    assert result.applied_fees.sell.enabled is use_sell_fee
    assert result.applied_fees.withdraw.enabled is use_withdraw_fee


def test_legacy_presets_ignore_new_checkbox_fields():
    raw = calculation_request("raw")
    raw.use_deposit_fee = True
    raw.use_sell_fee = True
    raw.use_withdraw_fee = True
    smart = calculation_request("smart", use_deposit_fee=False)
    smart.use_sell_fee = False
    smart.use_withdraw_fee = False
    enhanced = calculation_request("enhanced", use_deposit_fee=True)
    enhanced.use_sell_fee = False
    enhanced.use_withdraw_fee = False

    raw_result = post_calculation(raw)
    smart_result = post_calculation(smart)
    enhanced_result = post_calculation(enhanced)

    assert (
        raw_result.deposit_fee_cents,
        raw_result.sell_fee_cents,
        raw_result.withdraw_fee_cents,
    ) == (0, 0, 0)
    assert (
        smart_result.deposit_fee_cents,
        smart_result.sell_fee_cents,
        smart_result.withdraw_fee_cents,
    ) == (10, 60, 100)
    assert (
        enhanced_result.deposit_fee_cents,
        enhanced_result.sell_fee_cents,
        enhanced_result.withdraw_fee_cents,
    ) == (0, 60, 100)


def test_result_exposes_effective_totals_break_even_and_applied_server_rules():
    result = post_calculation(calculation_request("smart"))

    assert result.effective_buy_cents == 1010
    assert result.effective_payout_cents == 1040
    assert result.break_even_sell_price_cents == 1168
    assert result.applied_fees.deposit.model_dump() == {
        "enabled": True,
        "amount_cents": 10,
        "percent": 1.0,
        "fixed_cents": 0,
        "method": "crypto",
    }
    assert result.applied_fees.sell.percent == 5
    assert result.applied_fees.withdraw.fixed_cents == 100
    assert result.fee_configuration_version == "2026-09-04"


def test_request_rejects_client_supplied_fee_rates():
    with pytest.raises(ValidationError, match="sell_fee_percent"):
        CalculationRequest.model_validate(
            {
                "buy_price_cents": 1000,
                "sell_price_cents": 1200,
                "buy_marketplace": "csfloat",
                "sell_marketplace": "csgomarket",
                "sell_fee_percent": 0,
            }
        )


def test_disabled_unsupported_methods_do_not_block_custom_or_raw_calculation():
    custom = CalculationRequest(
        buy_price_cents=1000,
        sell_price_cents=1200,
        buy_marketplace="whitemarket",
        sell_marketplace="whitemarket",
        profit_mode="custom",
        deposit_method="card",
        withdraw_method="card",
        use_deposit_fee=False,
        use_sell_fee=False,
        use_withdraw_fee=False,
    )
    raw = custom.model_copy(update={"profit_mode": "raw"})

    assert post_calculation(custom).profit_cents == 200
    assert post_calculation(raw).profit_cents == 200


def test_enabled_unsupported_method_is_rejected():
    request = CalculationRequest(
        buy_price_cents=1000,
        sell_price_cents=1200,
        buy_marketplace="whitemarket",
        sell_marketplace="whitemarket",
        profit_mode="custom",
        deposit_method="card",
        use_deposit_fee=True,
        use_sell_fee=False,
        use_withdraw_fee=False,
    )

    with pytest.raises(HTTPException) as error:
        post_calculation(request)

    assert getattr(error.value, "status_code", None) == 422
    assert getattr(error.value, "detail", None) == "Unsupported deposit method"


def test_marketplace_options_expose_dynamic_capabilities_and_fee_rules():
    options = {option["id"]: option for option in marketplace_options()}
    csfloat = options["csfloat"]
    whitemarket = options["whitemarket"]
    csmoney = options["csmoney"]

    assert csfloat["display_name"] == "CSFloat"
    assert csfloat["currency"] == "USD"
    assert csfloat["capabilities"] == {
        "can_buy": True,
        "can_sell": True,
        "supports_listings": True,
        "supports_sales_history": True,
        "supports_quick_sell": True,
        "supports_float": True,
        "supports_stickers": True,
        "supports_charms": True,
        "supports_best_deal_sort": True,
    }
    assert csfloat["fees"]["deposit"]["card"] == {
        "percent": 2.8,
        "fixed_cents": 30,
    }
    assert csfloat["fees"]["sell"] == {"percent": 2, "fixed_cents": 0}
    assert whitemarket["capabilities"]["supports_quick_sell"] is True
    assert whitemarket["capabilities"]["supports_sales_history"] is False
    assert whitemarket["fees"]["deposit"]["card"] is None
    assert csmoney["capabilities"]["supports_listings"] is False
    assert all(
        option["fee_configuration_version"] == "2026-09-04"
        for option in options.values()
    )
