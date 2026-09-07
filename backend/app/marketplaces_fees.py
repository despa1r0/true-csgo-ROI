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

    display_name: str
    currency: str
    can_buy: bool
    can_sell: bool
    supports_fast_buy: bool
    supports_listings: bool
    supports_sales_history: bool
    supports_float: bool
    supports_stickers: bool
    supports_charms: bool
    supports_best_deal_sort: bool
    fees: MarketplaceFees


FEE_CONFIGURATION_VERSION = "2026-09-04"


# This is the single registry a new marketplace needs to join.  The API/UI use
# its capabilities to decide where a user may buy, sell, or fast-sell.
MARKETPLACES = {
    "csfloat": MarketplaceConfig(
        display_name="CSFloat",
        currency="USD",
        can_buy=True,
        can_sell=True,
        supports_fast_buy=True,
        supports_listings=True,
        supports_sales_history=True,
        supports_float=True,
        supports_stickers=True,
        supports_charms=True,
        supports_best_deal_sort=True,
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
    "csgomarket": MarketplaceConfig(
        display_name="CSGO Market",
        currency="USD",
        can_buy=True,
        can_sell=True,
        supports_fast_buy=True,
        supports_listings=True,
        supports_sales_history=True,
        supports_float=True,
        supports_stickers=True,
        supports_charms=False,
        supports_best_deal_sort=False,
        fees=MarketplaceFees(
            deposit={
                "crypto": FeeRule(fixed_cents=100),
                "card": FeeRule(percent=1),
            },
            sell=FeeRule(percent=5),
            withdraw={
                "crypto": FeeRule(fixed_cents=100),
                "card": FeeRule(percent=2.8),
            },
        ),
    ),
    "csmoney": MarketplaceConfig(
        display_name="CS.MONEY",
        currency="USD",
        can_buy=True,
        can_sell=True,
        supports_fast_buy=False,
        supports_listings=False,
        supports_sales_history=False,
        supports_float=False,
        supports_stickers=False,
        supports_charms=False,
        supports_best_deal_sort=False,
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
        display_name="White.Market",
        currency="USD",
        can_buy=True,
        can_sell=True,
        supports_fast_buy=True,
        supports_listings=True,
        supports_sales_history=False,
        supports_float=True,
        supports_stickers=True,
        supports_charms=True,
        supports_best_deal_sort=False,
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
