"""Liquidity calculation independent of HTTP and persistence concerns."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


LIQUIDITY_METHOD = (
    "Beta-оценка 0–100: 40% — качество выхода по bid (60% сохранение цены, "
    "40% глубина заявок в пределах 5% от лучшей), 60% — число наблюдаемых "
    "продаж за последние 7 дней. При отсутствии истории, ask или bid оценка "
    "недоступна. Это не вероятность продажи; история может быть неполной."
)


def calculate_liquidity(
    sales: list[dict[str, object]],
    lowest_ask_cents: int | None,
    buy_orders: list[dict[str, object]],
    *,
    sales_available: bool = True,
    orders_available: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Estimate liquidity from a fixed seven-day sample and executable bids.

    Missing source data is unknown rather than a zero-value observation.
    The score is a heuristic index, never a probability of sale.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    sales_count_7d = _recent_sales_count(sales, now) if sales_available and sales else None
    sales_per_day = round(sales_count_7d / 7, 2) if sales_count_7d is not None else None
    best_bid = max(
        (
            order["price_cents"]
            for order in buy_orders
            if isinstance(order.get("price_cents"), int)
            and not isinstance(order["price_cents"], bool)
            and order["price_cents"] > 0
        ),
        default=None,
    )
    if not orders_available:
        best_bid = None
    if not lowest_ask_cents or best_bid is None:
        return {
            "score": None,
            "label": "unavailable",
            "price_retention_percent": None,
            "quick_sell_discount_percent": None,
            "near_bid_depth": 0,
            "sales_per_day": sales_per_day,
            "sales_count_7d": sales_count_7d,
            "data_status": "missing_ask" if not lowest_ask_cents else "missing_orders",
        }

    retention = min(
        Decimal("100"),
        Decimal(best_bid) / Decimal(lowest_ask_cents) * Decimal("100"),
    )
    near_bid_floor = Decimal(best_bid) * Decimal("0.95")
    near_bid_depth = sum(
        int(order["quantity"])
        for order in buy_orders
        if isinstance(order.get("price_cents"), int)
        and isinstance(order.get("quantity"), int)
        and not isinstance(order["quantity"], bool)
        and order["quantity"] > 0
        and Decimal(order["price_cents"]) >= near_bid_floor
    )
    score = None
    label = "unavailable"
    if sales_count_7d is not None:
        depth_score = min(Decimal("100"), Decimal(near_bid_depth) * Decimal("10"))
        activity_score = min(
            Decimal("100"),
            (Decimal(sales_count_7d) / Decimal("14")).sqrt() * Decimal("100"),
        )
        execution_score = retention * Decimal("0.6") + depth_score * Decimal("0.4")
        score = int((execution_score * Decimal("0.4") + activity_score * Decimal("0.6"))
                    .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        label = "high" if score >= 75 else "medium" if score >= 50 else "low"
    retention_display = retention.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return {
        "score": min(100, score) if score is not None else None,
        "label": label,
        "price_retention_percent": float(retention_display),
        "quick_sell_discount_percent": float(Decimal("100") - retention_display),
        "near_bid_depth": near_bid_depth,
        "sales_per_day": sales_per_day,
        "sales_count_7d": sales_count_7d,
        "data_status": "complete" if score is not None else "missing_sales",
    }


def _recent_sales_count(sales: list[dict[str, object]], now: datetime) -> int:
    count = 0
    since = now - timedelta(days=7)
    for sale in sales:
        value = sale.get("sold_at")
        if not isinstance(value, str):
            continue
        try:
            sold_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if sold_at.tzinfo is not None and since <= sold_at.astimezone(timezone.utc) <= now:
            count += 1
    return count
