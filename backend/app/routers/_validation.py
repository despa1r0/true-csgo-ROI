"""Shared request validation used by marketplace HTTP routers."""

from fastapi import HTTPException


def validate_listing_ranges(
    *,
    min_float: float | None,
    max_float: float | None,
    min_price_cents: int | None,
    max_price_cents: int | None,
) -> None:
    if min_float is not None and max_float is not None and min_float > max_float:
        raise HTTPException(status_code=422, detail="Минимальный float больше максимального")
    if (
        min_price_cents is not None
        and max_price_cents is not None
        and min_price_cents > max_price_cents
    ):
        raise HTTPException(status_code=422, detail="Минимальная цена больше максимальной")
