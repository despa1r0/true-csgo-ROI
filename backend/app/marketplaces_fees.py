from dataclasses import dataclass


@dataclass(frozen=True)
class FeeRule:
    percent: float = 0
    fixed_cents: int = 0 

@dataclass(frozen=True)
class MarketplaceFees: 
    deposit: dict[str, FeeRule | None]
    sell: FeeRule
    withdraw: dict[str, FeeRule | None]


MARKETPLACE_FEES = {
    "csfloat": MarketplaceFees(
        deposit = {
            "crypto": FeeRule(percent=1),
            "card": FeeRule(percent=2.8, fixed_cents=30),
        },
        sell=FeeRule(percent=2),
        withdraw = {
            "crypto": FeeRule(percent=0),
            "card": FeeRule(percent=1),
        }
    ), 
        "csmoney": MarketplaceFees(
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
    "whitemarket": MarketplaceFees(
        deposit={
            "crypto": FeeRule(percent=0),
            "card": None,  # метод не поддерживается / данных пока нет
        },
        sell=FeeRule(percent=5),
        withdraw={
            "crypto": FeeRule(percent=0),
            "card": None,
        },
    ),
}
