"""Download ByMykel/CSGO-API data and import it into PostgreSQL."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen

from psycopg.types.json import Jsonb

from .database import ensure_schema, get_connection


DEFAULT_SOURCE_URL = (
    "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/"
    "public/api/en/skins_not_grouped.json"
)
DEFAULT_GROUPED_SOURCE_URL = (
    "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/"
    "public/api/en/skins.json"
)
DEFAULT_EXTRA_SOURCE_BASE_URL = (
    "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en"
)
EXTRA_CATALOG_FILES = {
    "container": "crates.json",
    "sticker": "stickers.json",
    "charm": "keychains.json",
    "agent": "agents.json",
    "collectible": "collectibles.json",
    "music_kit": "music_kits.json",
    "patch": "patches.json",
    "graffiti": "graffiti.json",
    "key": "keys.json",
    "sticker_slab": "sticker_slabs.json",
    "tool": "tools.json",
    "souvenir_charm": "highlights.json",
}

# Every supported non-skin type is queried by its exact Steam market hash name
# by all marketplace adapters. Source rows without that identifier represent
# inventory-only rewards, service medals, trophies, preview content, or other
# entries that cannot be priced reliably and must not enter the ROI catalogue.
SUPPORTED_EXTRA_SOURCE_TYPES = frozenset(EXTRA_CATALOG_FILES)


def download_catalog(url: str) -> list[dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "trueROI-catalog-importer/1.0"})
    with urlopen(request, timeout=120) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("The CSGO-API catalogue must be a JSON array")
    return payload


def base_skin_name(item: dict[str, Any]) -> str:
    name = str(item.get("name") or item.get("market_hash_name") or "").strip()
    name = re.sub(r"^(StatTrak™|Souvenir)\s+", "", name)
    wear = (item.get("wear") or {}).get("name")
    if wear and name.endswith(f" ({wear})"):
        name = name[: -(len(wear) + 3)]
    return name


def prepare_catalog(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    skins: dict[str, dict[str, Any]] = {}
    variants: list[dict[str, Any]] = []

    for item in items:
        skin_id = item.get("skin_id")
        variant_id = item.get("id")
        if not skin_id or not variant_id:
            continue

        weapon = item.get("weapon") or {}
        category = item.get("category") or {}
        pattern = item.get("pattern") or {}
        rarity = item.get("rarity") or {}
        wear = item.get("wear") or {}

        if skin_id not in skins:
            skins[skin_id] = {
                "id": skin_id,
                "name": base_skin_name(item),
                "description": item.get("description"),
                "image_url": item.get("image"),
                "weapon_id": weapon.get("id"),
                "weapon_name": weapon.get("name"),
                "category_id": category.get("id"),
                "category_name": category.get("name"),
                "pattern_id": pattern.get("id"),
                "pattern_name": pattern.get("name"),
                "rarity_id": rarity.get("id"),
                "rarity_name": rarity.get("name"),
                "rarity_color": rarity.get("color"),
                "min_float": item.get("min_float"),
                "max_float": item.get("max_float"),
                "paint_index": item.get("paint_index"),
                "has_stattrak": False,
                "has_souvenir": False,
                "raw_data": item,
            }

        skin = skins[skin_id]
        skin["has_stattrak"] = skin["has_stattrak"] or bool(item.get("stattrak"))
        skin["has_souvenir"] = skin["has_souvenir"] or bool(item.get("souvenir"))
        variants.append(
            {
                "id": variant_id,
                "skin_id": skin_id,
                "name": item.get("name") or item.get("market_hash_name") or variant_id,
                "market_hash_name": item.get("market_hash_name"),
                "wear_id": wear.get("id"),
                "wear_name": wear.get("name"),
                "stattrak": bool(item.get("stattrak")),
                "souvenir": bool(item.get("souvenir")),
                "image_url": item.get("image"),
                "raw_data": item,
            }
        )

    return list(skins.values()), variants


def prepare_non_skin_catalog(
    catalogues: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize every marketable CS2 item into the existing item/variant model.

    A non-skin has zero or one market variant. Keeping it in the same normalized
    tables lets price adapters use its exact ``market_hash_name`` without adding
    type-specific marketplace code.
    """
    items: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    for source_type, source_items in catalogues.items():
        for raw_item in source_items:
            if not _is_marketplace_catalog_item(source_type, raw_item):
                continue
            item_id = raw_item.get("id")
            name = raw_item.get("name") or raw_item.get("market_hash_name")
            if not isinstance(item_id, str) or not isinstance(name, str):
                continue
            item_type = _specific_item_type(source_type, raw_item)
            rarity = raw_item.get("rarity") or {}
            if not isinstance(rarity, dict):
                rarity = {}
            market_hash_name = raw_item["market_hash_name"].strip()
            has_stattrak = bool(raw_item.get("stattrak")) or name.startswith(
                "StatTrak™"
            )
            has_souvenir = name.startswith("Souvenir ")
            items.append(
                {
                    "id": item_id,
                    "name": name,
                    "item_type": item_type,
                    "description": raw_item.get("description"),
                    "image_url": raw_item.get("image"),
                    "weapon_id": None,
                    "weapon_name": None,
                    "category_id": item_type,
                    "category_name": raw_item.get("type") or item_type,
                    "pattern_id": None,
                    "pattern_name": None,
                    "rarity_id": rarity.get("id"),
                    "rarity_name": rarity.get("name"),
                    "rarity_color": rarity.get("color"),
                    "min_float": None,
                    "max_float": None,
                    "paint_index": None,
                    "has_stattrak": has_stattrak,
                    "has_souvenir": has_souvenir,
                    "raw_data": raw_item,
                }
            )
            variants.append(
                {
                    "id": f"catalog-variant-{item_id}",
                    "skin_id": item_id,
                    "name": market_hash_name,
                    "market_hash_name": market_hash_name,
                    "wear_id": None,
                    "wear_name": None,
                    "stattrak": has_stattrak,
                    "souvenir": has_souvenir,
                    "image_url": raw_item.get("image"),
                    "raw_data": raw_item,
                }
            )
    return items, variants


def _is_marketplace_catalog_item(
    source_type: str, item: dict[str, Any]
) -> bool:
    """Accept only source rows that can be addressed by marketplace APIs."""
    if source_type not in SUPPORTED_EXTRA_SOURCE_TYPES:
        return False
    market_hash_name = item.get("market_hash_name")
    if not isinstance(market_hash_name, str) or not market_hash_name.strip():
        return False
    # The collectibles feed also contains account-bound coins, medals,
    # Pick'Em trophies and unreleased definitions. Only non-genuine pins have
    # real market counterparts across the supported marketplaces.
    if source_type == "collectible":
        descriptor = str(item.get("type") or "").casefold()
        return "pin" in descriptor and not bool(item.get("genuine"))
    return True


def _specific_item_type(source_type: str, item: dict[str, Any]) -> str:
    """Split broad source files into useful catalogue filters."""
    descriptor = f"{item.get('type') or ''} {item.get('name') or ''}".casefold()
    if source_type == "container":
        if "souvenir" in descriptor:
            return "souvenir_package"
        if "capsule" in descriptor:
            return "capsule"
        if "graffiti" in descriptor:
            return "graffiti_box"
        if "music" in descriptor:
            return "music_kit_box"
        if "case" in descriptor:
            return "case"
    if source_type == "collectible" and "pin" in descriptor:
        return "pin"
    return source_type


def prepare_skin_collections(
    grouped_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flatten the grouped catalogue's collection metadata for PostgreSQL."""
    rows: list[dict[str, Any]] = []
    for item in grouped_items:
        skin_id = item.get("id")
        if not skin_id:
            continue
        for collection in item.get("collections") or []:
            if not isinstance(collection, dict):
                continue
            collection_id = collection.get("id")
            collection_name = collection.get("name")
            if not collection_id or not collection_name:
                continue
            rows.append(
                {
                    "skin_id": skin_id,
                    "collection_id": collection_id,
                    "collection_name": collection_name,
                    "image_url": collection.get("image"),
                }
            )
    return rows


def import_catalog(
    items: list[dict[str, Any]],
    grouped_items: list[dict[str, Any]] | None = None,
    extra_catalogues: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[int, int]:
    skins, variants = prepare_catalog(items)
    collections = prepare_skin_collections(grouped_items or [])
    if extra_catalogues:
        extra_items, extra_variants = prepare_non_skin_catalog(extra_catalogues)
        skins.extend(extra_items)
        variants.extend(extra_variants)
        for source_items in extra_catalogues.values():
            collections.extend(prepare_skin_collections(source_items))
    imported_ids = {skin["id"] for skin in skins}
    collections = [
        collection
        for collection in collections
        if collection["skin_id"] in imported_ids
    ]
    if not skins or not variants:
        raise ValueError("The downloaded catalogue contains no usable skins")

    with get_connection() as connection:
        ensure_schema(connection)
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO skins (
                    id, name, item_type, description, image_url, weapon_id, weapon_name,
                    category_id, category_name, pattern_id, pattern_name,
                    rarity_id, rarity_name, rarity_color, min_float, max_float,
                    paint_index, has_stattrak, has_souvenir, raw_data
                ) VALUES (
                    %(id)s, %(name)s, %(item_type)s, %(description)s, %(image_url)s,
                    %(weapon_id)s, %(weapon_name)s, %(category_id)s, %(category_name)s,
                    %(pattern_id)s, %(pattern_name)s, %(rarity_id)s, %(rarity_name)s,
                    %(rarity_color)s, %(min_float)s, %(max_float)s, %(paint_index)s,
                    %(has_stattrak)s, %(has_souvenir)s, %(raw_data)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    item_type = EXCLUDED.item_type,
                    description = EXCLUDED.description,
                    image_url = EXCLUDED.image_url,
                    weapon_id = EXCLUDED.weapon_id,
                    weapon_name = EXCLUDED.weapon_name,
                    category_id = EXCLUDED.category_id,
                    category_name = EXCLUDED.category_name,
                    pattern_id = EXCLUDED.pattern_id,
                    pattern_name = EXCLUDED.pattern_name,
                    rarity_id = EXCLUDED.rarity_id,
                    rarity_name = EXCLUDED.rarity_name,
                    rarity_color = EXCLUDED.rarity_color,
                    min_float = EXCLUDED.min_float,
                    max_float = EXCLUDED.max_float,
                    paint_index = EXCLUDED.paint_index,
                    has_stattrak = EXCLUDED.has_stattrak,
                    has_souvenir = EXCLUDED.has_souvenir,
                    raw_data = EXCLUDED.raw_data,
                    updated_at = NOW()
                """,
                [
                    {
                        **skin,
                        "item_type": skin.get("item_type", "skin"),
                        "raw_data": Jsonb(skin["raw_data"]),
                    }
                    for skin in skins
                ],
            )
            cursor.executemany(
                """
                INSERT INTO skin_variants (
                    id, skin_id, name, market_hash_name, wear_id, wear_name,
                    stattrak, souvenir, image_url, raw_data
                ) VALUES (
                    %(id)s, %(skin_id)s, %(name)s, %(market_hash_name)s,
                    %(wear_id)s, %(wear_name)s, %(stattrak)s, %(souvenir)s,
                    %(image_url)s, %(raw_data)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    skin_id = EXCLUDED.skin_id,
                    name = EXCLUDED.name,
                    market_hash_name = EXCLUDED.market_hash_name,
                    wear_id = EXCLUDED.wear_id,
                    wear_name = EXCLUDED.wear_name,
                    stattrak = EXCLUDED.stattrak,
                    souvenir = EXCLUDED.souvenir,
                    image_url = EXCLUDED.image_url,
                    raw_data = EXCLUDED.raw_data,
                    updated_at = NOW()
                """,
                [
                    {**variant, "raw_data": Jsonb(variant["raw_data"])}
                    for variant in variants
                ],
            )
            if grouped_items is not None:
                cursor.execute("DELETE FROM skin_collections")
            if collections:
                cursor.executemany(
                    """
                    INSERT INTO skin_collections (
                        skin_id, collection_id, collection_name, image_url
                    ) VALUES (
                        %(skin_id)s, %(collection_id)s, %(collection_name)s,
                        %(image_url)s
                    )
                    ON CONFLICT (skin_id, collection_id) DO UPDATE SET
                        collection_name = EXCLUDED.collection_name,
                        image_url = EXCLUDED.image_url
                    """,
                    collections,
                )
        connection.execute(
            "DELETE FROM skin_variants WHERE NOT (id = ANY(%s))",
            ([variant["id"] for variant in variants],),
        )
        connection.execute(
            "DELETE FROM skins WHERE NOT (id = ANY(%s))",
            ([skin["id"] for skin in skins],),
        )
    return len(skins), len(variants)


def main() -> None:
    source_url = os.getenv("CATALOG_SOURCE_URL", DEFAULT_SOURCE_URL)
    grouped_source_url = os.getenv(
        "CATALOG_GROUPED_SOURCE_URL", DEFAULT_GROUPED_SOURCE_URL
    )
    print(f"Downloading skin catalogue from {source_url}", flush=True)
    items = download_catalog(source_url)
    print(f"Downloading grouped skin metadata from {grouped_source_url}", flush=True)
    grouped_items = download_catalog(grouped_source_url)
    extra_base_url = os.getenv(
        "CATALOG_EXTRA_SOURCE_BASE_URL", DEFAULT_EXTRA_SOURCE_BASE_URL
    ).rstrip("/")
    extra_catalogues = {}
    for item_type, filename in EXTRA_CATALOG_FILES.items():
        source = f"{extra_base_url}/{filename}"
        print(f"Downloading {item_type} catalogue from {source}", flush=True)
        extra_catalogues[item_type] = download_catalog(source)
    skin_count, variant_count = import_catalog(
        items, grouped_items, extra_catalogues
    )
    print(
        f"Catalogue is ready: {skin_count} skins, {variant_count} variants",
        flush=True,
    )


if __name__ == "__main__":
    main()
