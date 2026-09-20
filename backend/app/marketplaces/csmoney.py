"""Read the price-sorted CS.MONEY storefront for an exact market variant.

The site's interactive sell-orders endpoint currently returns 403. Initial
HTML responses still embed inventory.items; this adapter reads that public
payload and never bypasses a security challenge.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from typing import Any
from urllib.parse import urlencode


STORE_URL = "https://cs.money/pl/market/buy/"
PAGE_SIZE = 60
MAX_LISTINGS = 10


class CsMoneyRequestError(RuntimeError):
    """The storefront could not provide a usable price-sorted capture."""


def storefront_url(market_hash_name: str) -> str:
    return STORE_URL + "?" + urlencode(
        {"search": market_hash_name, "order": "asc", "sort": "price"}
    )


def capture_variant(
    page: Any,
    market_hash_name: str,
    *,
    phase: str | None = None,
    limit: int = MAX_LISTINGS,
) -> dict[str, Any]:
    """Capture one sorted storefront page in an existing browser session."""
    url = storefront_url(market_hash_name)
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    except Exception as error:
        raise CsMoneyRequestError(f"CS.MONEY page failed: {error}") from error
    if response is None or response.status != 200:
        status = response.status if response else "no response"
        raise CsMoneyRequestError(f"CS.MONEY page returned {status}")
    return extract_capture(_embedded_items(page), market_hash_name, phase=phase, limit=limit, source_url=url)


def _embedded_items(page: Any) -> list[dict[str, Any]]:
    try:
        scripts = page.locator('script[type="application/json"]').all_text_contents()
    except Exception as error:
        raise CsMoneyRequestError(f"Could not read CS.MONEY page data: {error}") from error
    for script in scripts:
        try:
            payload = json.loads(script)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        inventory = payload.get("inventory")
        if isinstance(inventory, dict) and isinstance(inventory.get("items"), list):
            items = inventory["items"]
            if any(not isinstance(item, dict) for item in items):
                raise CsMoneyRequestError("CS.MONEY inventory contains invalid items")
            return items
    raise CsMoneyRequestError("CS.MONEY page has no embedded inventory")


def extract_capture(
    items: list[dict[str, Any]],
    market_hash_name: str,
    *,
    phase: str | None = None,
    limit: int = MAX_LISTINGS,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Validate sorted prices and keep up to ten exact, distinct listings."""
    if limit < 1:
        raise ValueError("limit must be positive")
    parsed: list[tuple[dict[str, Any], int]] = []
    for item in items:
        pricing = item.get("pricing")
        if not isinstance(pricing, dict):
            raise CsMoneyRequestError("CS.MONEY listing has no pricing")
        price_cents = _usd_cents(pricing.get("computed"))
        if price_cents is None:
            raise CsMoneyRequestError("CS.MONEY listing has invalid computed price")
        parsed.append((item, price_cents))
    if any(parsed[i][1] > parsed[i + 1][1] for i in range(len(parsed) - 1)):
        raise CsMoneyRequestError("CS.MONEY storefront is not sorted by price")

    expected_phase = _phase_slug(phase)
    listings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    exact_matches = 0
    for item, price_cents in parsed:
        asset = item.get("asset")
        if not isinstance(asset, dict):
            continue
        names = asset.get("names")
        if not isinstance(names, dict) or not _same_market_name(
            names.get("full"), market_hash_name, asset.get("phase"), expected_phase
        ):
            continue
        listing_id = item.get("id")
        if not isinstance(listing_id, (str, int)) or isinstance(listing_id, bool):
            continue
        listing_id = str(listing_id)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)
        exact_matches += 1
        if len(listings) >= limit:
            continue
        float_value = asset.get("float")
        if isinstance(float_value, bool) or not isinstance(float_value, (int, float)):
            float_value = None
        pattern = asset.get("pattern")
        if isinstance(pattern, bool) or not isinstance(pattern, int):
            pattern = None
        images = asset.get("images")
        image_url = images.get("steam") if isinstance(images, dict) else None
        listings.append(
            {
                "listing_id": listing_id,
                "price_cents": price_cents,
                "float_value": float(float_value) if float_value is not None else None,
                "paint_seed": pattern,
                "image_url": image_url if isinstance(image_url, str) else None,
                "item_url": source_url or storefront_url(market_hash_name),
            }
        )
    return {
        "source_url": source_url or storefront_url(market_hash_name),
        "page_items": len(items),
        "exact_matches": exact_matches,
        "is_partial": len(items) >= PAGE_SIZE and exact_matches < limit,
        "listings": listings,
    }


def _usd_cents(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _phase_slug(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return "".join(character for character in value.casefold() if character.isalnum()) or None


def _same_market_name(
    full: Any, market_hash_name: str, asset_phase: Any, expected_phase: str | None
) -> bool:
    if not isinstance(full, str):
        return False
    actual_phase = _phase_slug(asset_phase)
    if full == market_hash_name:
        return expected_phase is None or actual_phase is None or expected_phase == actual_phase
    if expected_phase is None or expected_phase != actual_phase:
        return False
    # Doppler and Gamma Doppler listings sometimes insert the phase just
    # before the wear suffix, while catalog market_hash_name omits it.
    if not isinstance(asset_phase, str) or not asset_phase.strip():
        return False
    wear_start = market_hash_name.rfind(" (")
    if wear_start < 0:
        return False
    expected_full = (
        market_hash_name[:wear_start]
        + " " + asset_phase.strip()
        + market_hash_name[wear_start:]
    )
    return full == expected_full
