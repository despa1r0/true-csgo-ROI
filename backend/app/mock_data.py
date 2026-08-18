from .models import MarketPrice


def get_mock_prices() -> list[MarketPrice]:
    return [
        MarketPrice(
            marketplace="CSFloat",
            price_cents=1840,
            item_url="https://example.com/csfloat/redline",
        ),
        MarketPrice(
            marketplace="CS.MONEY",
            price_cents=1940,
            item_url="https://example.com/csmoney/redline",
        ),
    ]
