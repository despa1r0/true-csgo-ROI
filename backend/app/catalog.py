"""Read-only catalogue queries used by the HTTP API."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .database import get_connection


WEAR_ORDER = {
    "Factory New": 0,
    "Minimal Wear": 1,
    "Field-Tested": 2,
    "Well-Worn": 3,
    "Battle-Scarred": 4,
}


def search_skins(
    query: str,
    *,
    weapon: str | None = None,
    rarity: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    normalized = query.strip()
    if len(normalized) < 2:
        return []

    conditions = ["s.name ILIKE %s"]
    parameters: list[Any] = [f"%{normalized}%"]
    if weapon:
        conditions.append("s.weapon_id = %s")
        parameters.append(weapon)
    if rarity:
        conditions.append("s.rarity_id = %s")
        parameters.append(rarity)

    parameters.extend([normalized.casefold(), f"{normalized}%", limit])
    sql = f"""
        SELECT
            s.id,
            s.name,
            s.image_url,
            s.weapon_id,
            s.weapon_name,
            s.rarity_id,
            s.rarity_name,
            s.rarity_color,
            s.min_float,
            s.max_float,
            s.has_stattrak,
            s.has_souvenir,
            COUNT(v.id)::INTEGER AS variant_count
        FROM skins s
        LEFT JOIN skin_variants v ON v.skin_id = s.id
        WHERE {' AND '.join(conditions)}
        GROUP BY s.id
        ORDER BY
            CASE WHEN LOWER(s.name) = %s THEN 0
                 WHEN s.name ILIKE %s THEN 1
                 ELSE 2 END,
            similarity(LOWER(s.name), %s) DESC,
            s.name
        LIMIT %s
    """
    # The third ranking parameter is the normalized query again.
    parameters.insert(-1, normalized.casefold())

    with get_connection() as connection:
        return list(connection.execute(sql, parameters).fetchall())


def get_skin(skin_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        skin = connection.execute(
            """
            SELECT id, name, description, image_url, weapon_id, weapon_name,
                   category_id, category_name, pattern_id, pattern_name,
                   rarity_id, rarity_name, rarity_color, min_float, max_float,
                   paint_index, has_stattrak, has_souvenir
            FROM skins
            WHERE id = %s
            """,
            (skin_id,),
        ).fetchone()
        if skin is None:
            return None

        variants = list(
            connection.execute(
                """
                SELECT id, name, market_hash_name, wear_id, wear_name,
                       stattrak, souvenir, image_url
                FROM skin_variants
                WHERE skin_id = %s
                """,
                (skin_id,),
            ).fetchall()
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for variant in variants:
        grouped[variant["wear_name"] or "Без качества"].append(variant)

    qualities = [
        {"wear": wear, "variants": sorted(items, key=_variant_order)}
        for wear, items in sorted(
            grouped.items(), key=lambda item: WEAR_ORDER.get(item[0], 99)
        )
    ]
    result = dict(skin)
    result["qualities"] = qualities
    return result


def get_catalog_filters() -> dict[str, list[dict[str, Any]]]:
    with get_connection() as connection:
        weapons = list(
            connection.execute(
                """
                SELECT weapon_id AS id, weapon_name AS name, COUNT(*)::INTEGER AS count
                FROM skins
                WHERE weapon_id IS NOT NULL
                GROUP BY weapon_id, weapon_name
                ORDER BY weapon_name
                """
            ).fetchall()
        )
        rarities = list(
            connection.execute(
                """
                SELECT rarity_id AS id, rarity_name AS name, rarity_color AS color,
                       COUNT(*)::INTEGER AS count
                FROM skins
                WHERE rarity_id IS NOT NULL
                GROUP BY rarity_id, rarity_name, rarity_color
                ORDER BY MIN(COALESCE(min_float, 0)), rarity_name
                """
            ).fetchall()
        )
    return {"weapons": weapons, "rarities": rarities}


def catalogue_size() -> dict[str, int]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT (SELECT COUNT(*) FROM skins)::INTEGER AS skins,
                   (SELECT COUNT(*) FROM skin_variants)::INTEGER AS variants
            """
        ).fetchone()
    return dict(row)


def _variant_order(variant: dict[str, Any]) -> tuple[bool, bool]:
    return (variant["souvenir"], variant["stattrak"])
