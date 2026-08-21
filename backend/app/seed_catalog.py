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
) -> tuple[int, int]:
    skins, variants = prepare_catalog(items)
    collections = prepare_skin_collections(grouped_items or [])
    if not skins or not variants:
        raise ValueError("The downloaded catalogue contains no usable skins")

    with get_connection() as connection:
        ensure_schema(connection)
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO skins (
                    id, name, description, image_url, weapon_id, weapon_name,
                    category_id, category_name, pattern_id, pattern_name,
                    rarity_id, rarity_name, rarity_color, min_float, max_float,
                    paint_index, has_stattrak, has_souvenir, raw_data
                ) VALUES (
                    %(id)s, %(name)s, %(description)s, %(image_url)s,
                    %(weapon_id)s, %(weapon_name)s, %(category_id)s, %(category_name)s,
                    %(pattern_id)s, %(pattern_name)s, %(rarity_id)s, %(rarity_name)s,
                    %(rarity_color)s, %(min_float)s, %(max_float)s, %(paint_index)s,
                    %(has_stattrak)s, %(has_souvenir)s, %(raw_data)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
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
                [{**skin, "raw_data": Jsonb(skin["raw_data"])} for skin in skins],
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
    skin_count, variant_count = import_catalog(items, grouped_items)
    print(
        f"Catalogue is ready: {skin_count} skins, {variant_count} variants",
        flush=True,
    )


if __name__ == "__main__":
    main()
