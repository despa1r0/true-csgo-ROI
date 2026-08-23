from dataclasses import dataclass


@dataclass(frozen=True)
class FeeRule:
    """Commission charged for one money operation, in cents."""

    percent: float = 0
    fixed_cents: int = 0


@dataclass(frozen=True)
class MarketplaceFees:
    deposit: dict[str, FeeRule | None]
    sell: FeeRule | None
    withdraw: dict[str, FeeRule | None]


@dataclass(frozen=True)
class MarketplaceConfig:
    """Operations supported by a marketplace and its current fee rules."""

    can_buy: bool
    can_sell: bool
    supports_fast_buy: bool
    fees: MarketplaceFees


# This is the single registry a new marketplace needs to join.  The API/UI use
# its capabilities to decide where a user may buy, sell, or fast-sell.
MARKETPLACES = {
    "csfloat": MarketplaceConfig(
        can_buy=True,
        can_sell=True,
        supports_fast_buy=True,
        fees=MarketplaceFees(
            deposit={
                "crypto": FeeRule(percent=1),
                "card": FeeRule(percent=2.8, fixed_cents=30),
            },
            sell=FeeRule(percent=2),
            withdraw={
                "crypto": FeeRule(percent=0),
                "card": FeeRule(percent=1),
            },
        ),
    ),
    "csmoney": MarketplaceConfig(
        can_buy=True,
        can_sell=True,
        supports_fast_buy=False,
        fees=MarketplaceFees(
            deposit={
                "crypto": FeeRule(percent=0),
                "card": FeeRule(percent=3, fixed_cents=30),
            },
            sell=FeeRule(percent=5),
            withdraw={
                "crypto": FeeRule(percent=0),
                "card": FeeRule(percent=0),
            },
        ),
    ),
    "whitemarket": MarketplaceConfig(
        can_buy=True,
        can_sell=True,
        supports_fast_buy=False,
        fees=MarketplaceFees(
            deposit={
                "crypto": FeeRule(percent=0),
                "card": None,
            },
            sell=FeeRule(percent=5),
            withdraw={
                "crypto": FeeRule(percent=0),
                "card": None,
            },
        ),
    ),
}

# Kept as a read-only compatibility alias while callers migrate to
# MARKETPLACES[marketplace].fees.
MARKETPLACE_FEES = {name: config.fees for name, config in MARKETPLACES.items()}
