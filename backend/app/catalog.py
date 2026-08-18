"""Временный каталог для демонстрации поиска.

Позже он будет заменён таблицей skins в PostgreSQL. Здесь нет рыночных цен.
"""

DEMO_SKINS = [
    "AK-47 | Redline (Field-Tested)",
    "AK-47 | Redline (Minimal Wear)",
    "StatTrak™ AK-47 | Redline (Field-Tested)",
    "StatTrak™ AK-47 | Redline (Minimal Wear)",
    "USP-S | Cortex (Field-Tested)",
    "AWP | Neo-Noir (Field-Tested)",
]


def find_skins(query: str, limit: int = 5) -> list[str]:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return []

    return [
        skin for skin in DEMO_SKINS if normalized_query in skin.casefold()
    ][:limit]
