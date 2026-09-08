"""CS.Money storefront snapshot persistence, backed by PostgreSQL.

CS.Money has no public listings API. ``backend/app/marketplaces/csmoney.py``
drives a real browser to load the storefront and captures the ``sell-orders``
responses it makes while scrolling. This module turns that raw capture into
rows in the same ``marketplace_listings`` table the other marketplaces use,
so CS.Money's price can be compared like CSFloat's or CSGO Market's.
"""

from __future__ import annotations

from typing import Any

from .database import get_connection

MARKETPLACE = "CS.MONEY"
STORE_URL = "https://cs.money/ru/csgo/store/"

# Doppler/Gamma Doppler phases are a small, fixed set Valve hasn't changed in
# years. CS.Money bakes the phase into the display name (e.g. "... Gamma
# Doppler Emerald (Minimal Wear)"), but Steam's real market_hash_name never
# includes it -- all phases of one weapon+wear share one name. The catalogue
# instead keeps one *skin* row per phase (see seed_catalog.py), distinguished
# by ``skins.raw_data ->> 'phase'``. This table lets us strip the phase word
# back out of CS.Money's name and use it to pick the right skin.
_PHASE_DISPLAY_BY_SLUG = {
    "phase1": "Phase 1",
    "phase2": "Phase 2",
    "phase3": "Phase 3",
    "phase4": "Phase 4",
    "ruby": "Ruby",
    "sapphire": "Sapphire",
    "blackpearl": "Black Pearl",
    "emerald": "Emerald",
}

_INSERT_LISTING_SQL = """
    INSERT INTO marketplace_listings (
        marketplace, variant_id, listing_id, price_cents, item_url,
        float_value, quantity, is_available, fetched_at
    ) VALUES (
        %(marketplace)s, %(variant_id)s, %(listing_id)s, %(price_cents)s,
        %(item_url)s, %(float_value)s, NULL, TRUE, NOW()
    )
    ON CONFLICT (marketplace, variant_id) DO UPDATE SET
        listing_id = EXCLUDED.listing_id,
        price_cents = EXCLUDED.price_cents,
        item_url = EXCLUDED.item_url,
        float_value = EXCLUDED.float_value,
        is_available = TRUE,
        fetched_at = NOW()
"""


def store_snapshot(responses: list[dict[str, Any]]) -> int:
    """Persist the cheapest listing per skin found in one storefront capture.

    A scroll capture is a partial sample of the storefront, not a snapshot of
    the whole marketplace like CSFloat's/CSGO Market's price-list endpoints.
    So, unlike ``market_data.py``/``csgomarket_data.py``, skins missing from
    this capture are left untouched instead of being marked unavailable.

    Returns the number of local catalogue variants matched and stored.
    """
    best_by_name = _best_listing_per_name(responses)
    if not best_by_name:
        return 0

    plain_by_name: dict[str, dict[str, Any]] = {}
    phased_listings: list[dict[str, Any]] = []
    for listing in best_by_name.values():
        if listing["phase"] is not None:
            phased_listings.append(listing)
        else:
            plain_by_name[listing["catalog_name"]] = listing

    rows: list[dict[str, Any]] = []
    with get_connection() as connection:
        if plain_by_name:
            variants = connection.execute(
                "SELECT id, market_hash_name FROM skin_variants WHERE market_hash_name = ANY(%s)",
                (list(plain_by_name.keys()),),
            ).fetchall()
            rows.extend(
                _listing_row(variant["id"], plain_by_name[variant["market_hash_name"]])
                for variant in variants
            )

        for listing in phased_listings:
            variant = connection.execute(
                """
                SELECT sv.id
                FROM skin_variants sv
                JOIN skins s ON s.id = sv.skin_id
                WHERE sv.market_hash_name = %s AND s.raw_data ->> 'phase' = %s
                """,
                (listing["catalog_name"], listing["phase"]),
            ).fetchone()
            if variant is not None:
                rows.append(_listing_row(variant["id"], listing))

        if not rows:
            return 0

        with connection.cursor() as cursor:
            cursor.executemany(_INSERT_LISTING_SQL, rows)
        connection.execute(
            """
            INSERT INTO marketplace_syncs (marketplace, fetched_at)
            VALUES (%s, NOW())
            ON CONFLICT (marketplace) DO UPDATE SET fetched_at = NOW()
            """,
            (MARKETPLACE,),
        )
    return len(rows)


def _listing_row(variant_id: str, listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "marketplace": MARKETPLACE,
        "variant_id": variant_id,
        "listing_id": listing["listing_id"],
        "price_cents": listing["price_cents"],
        "item_url": listing["item_url"],
        "float_value": listing["float_value"],
    }


def _best_listing_per_name(responses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Flatten captured ``sell-orders`` responses into one row per market name.

    A single scroll can surface the same skin more than once (different bots,
    different prices); only the cheapest one is kept, matching the "current
    lowest price" every other marketplace adapter exposes.
    """
    best: dict[str, dict[str, Any]] = {}
    for response in responses:
        if not isinstance(response, dict):
            continue
        items = response.get("items")
        if not isinstance(items, list):
            continue
        for raw_item in items:
            listing = _normalize_item(raw_item)
            if listing is None:
                continue
            name = listing.pop("market_hash_name")
            current_best = best.get(name)
            if current_best is None or listing["price_cents"] < current_best["price_cents"]:
                best[name] = listing
    return best


def _normalize_item(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    asset = raw_item.get("asset")
    pricing = raw_item.get("pricing")
    if not isinstance(asset, dict) or not isinstance(pricing, dict):
        return None
    names = asset.get("names")
    market_hash_name = names.get("full") if isinstance(names, dict) else None
    price_cents = _dollars_to_cents(pricing.get("computed"))
    if not isinstance(market_hash_name, str) or price_cents is None:
        return None

    listing_id = raw_item.get("id")
    links = raw_item.get("links")
    item_url = links.get("3d") if isinstance(links, dict) else None
    float_value = asset.get("float")
    if not isinstance(float_value, (int, float)) or isinstance(float_value, bool):
        float_value = None

    phase = _phase_display(asset.get("phase"))
    catalog_name = market_hash_name
    if phase is not None:
        stripped = market_hash_name.replace(f" {phase} (", " (", 1)
        if stripped == market_hash_name:
            # Couldn't find the phase word where expected -- fall back to
            # plain name matching rather than guessing; it just won't match,
            # same as before this fix existed.
            phase = None
        else:
            catalog_name = stripped

    return {
        "market_hash_name": market_hash_name,
        "catalog_name": catalog_name,
        "phase": phase,
        "listing_id": str(listing_id) if isinstance(listing_id, (str, int)) else None,
        "price_cents": price_cents,
        "item_url": item_url if isinstance(item_url, str) else STORE_URL,
        "float_value": float(float_value) if float_value is not None else None,
    }


def _phase_display(value: Any) -> str | None:
    """Map CS.Money's phase slug (e.g. "black_pearl") to the catalogue's text."""
    if not isinstance(value, str):
        return None
    slug = "".join(ch for ch in value.lower() if ch.isalnum())
    return _PHASE_DISPLAY_BY_SLUG.get(slug)


def _dollars_to_cents(value: Any) -> int | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return None
    return round(value * 100)
