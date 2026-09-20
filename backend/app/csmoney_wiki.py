"""Public CS.MONEY Wiki Trade price series, separate from completed sales.

The Wiki's ``price_trader_log`` is a daily Trade quote history. It is never
used as a sale, a Market ask, or an input to liquidity and profit calculations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from typing import Any
from urllib.request import Request, urlopen

from psycopg.types.json import Jsonb

from .csmoney_data import load_variant_context
from .database import get_connection


GRAPHQL_URL = "https://wiki.cs.money/api/graphql"
SOURCE_URL = "https://wiki.cs.money/"
CACHE_TTL = timedelta(hours=6)
ERROR_TTL = timedelta(minutes=15)
MAX_POINT_AGE = timedelta(hours=72)
MAX_HISTORY_AGE = timedelta(days=365)
MAX_RESPONSE_BYTES = 2_000_000


class WikiPriceError(ValueError):
    """Wiki data cannot be safely attributed to the requested variant."""


def _query(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        GRAPHQL_URL, data=body,
        headers={"Content-Type": "application/json", "User-Agent": "trueROI/1.0"},
    )
    with urlopen(request, timeout=12) as response:
        if "application/json" not in response.headers.get("Content-Type", ""):
            raise WikiPriceError("Wiki response is not JSON")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise WikiPriceError("Wiki response is too large")
    result = json.loads(payload)
    if not isinstance(result, dict) or result.get("errors") or not isinstance(result.get("data"), dict):
        raise WikiPriceError("Wiki GraphQL request failed")
    return result["data"]


def _slug(item_name: str) -> str:
    # Wiki's skin ID for "AK-47 | Redline" is "ak-47-redline".
    return "-".join(re.findall(r"[a-z0-9]+", item_name.casefold()))


def _usd_cents(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000"):
        return None
    try:
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None


def parse_price_history(
    entries: Any, *, name_id: int, now: datetime,
) -> list[dict[str, Any]]:
    """Keep valid daily USD quotes only when the newest point is recent."""
    if (not isinstance(entries, list) or len(entries) != 1
            or not isinstance(entries[0], dict) or entries[0].get("name_id") != name_id):
        raise WikiPriceError("Wiki returned a different variant")
    values = entries[0].get("values")
    if not isinstance(values, list):
        raise WikiPriceError("Wiki price history is missing")
    daily: dict[int, dict[str, Any]] = {}
    start = now - MAX_HISTORY_AGE
    for value in values:
        if not isinstance(value, dict):
            continue
        timestamp = value.get("time")
        price_cents = _usd_cents(value.get("price_trader_new"))
        if isinstance(timestamp, bool) or not isinstance(timestamp, int) or price_cents is None:
            continue
        try:
            at = datetime.fromtimestamp(timestamp, timezone.utc)
        except (OverflowError, OSError, ValueError):
            continue
        if at < start or at > now + timedelta(hours=24):
            continue
        daily[timestamp] = {"at": at.isoformat(), "price_cents": price_cents}
    points = [daily[key] for key in sorted(daily)]
    if not points or datetime.fromisoformat(points[-1]["at"]) < now - MAX_POINT_AGE:
        raise WikiPriceError("Wiki price history has no recent point")
    return points


def fetch_price_history(item_name: str, market_hash_name: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    skin_data = _query(
        "query($id: String!) { skin(input: {id: $id}) { hash_name name_ids { name name_id } } }",
        {"id": _slug(item_name)},
    ).get("skin")
    if not isinstance(skin_data, dict) or skin_data.get("hash_name") != item_name:
        raise WikiPriceError("Wiki skin name does not match the catalogue")
    name_ids = skin_data.get("name_ids")
    if not isinstance(name_ids, list):
        raise WikiPriceError("Wiki variant list is missing")
    matching = [entry for entry in name_ids
                if isinstance(entry, dict) and entry.get("name") == market_hash_name
                and isinstance(entry.get("name_id"), int)]
    if len(matching) != 1:
        raise WikiPriceError("Wiki variant name is unavailable or ambiguous")
    name_id = matching[0]["name_id"]
    rows = _query(
        "query($name_ids: [Int!]!) { price_trader_log(input: {name_ids: $name_ids}) "
        "{ name_id values { price_trader_new time } } }",
        {"name_ids": [name_id]},
    ).get("price_trader_log")
    return parse_price_history(rows, name_id=name_id, now=now)


def get_variant_price_history(variant_id: str) -> dict[str, Any] | None:
    context = load_variant_context(variant_id)
    if context is None:
        return None
    now = datetime.now(timezone.utc)
    with get_connection() as connection:
        cached = connection.execute(
            "SELECT points, latest_at, fetched_at, error FROM csmoney_wiki_price_history "
            "WHERE variant_id = %s", (variant_id,),
        ).fetchone()
    if cached:
        ttl = ERROR_TTL if cached["error"] else CACHE_TTL
        latest_at = cached["latest_at"]
        still_recent = not cached["points"] or (
            latest_at is not None and latest_at >= now - MAX_POINT_AGE
        )
        if cached["fetched_at"] >= now - ttl and still_recent:
            return _result(cached["points"], cached["latest_at"], cached["fetched_at"], cached["error"])
    try:
        points = fetch_price_history(context["item_name"], context["market_hash_name"], now=now)
        error = None
    except (WikiPriceError, OSError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        points = []
        error = str(exc)[:200]
    latest_at = datetime.fromisoformat(points[-1]["at"]) if points else None
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO csmoney_wiki_price_history
               (variant_id, points, latest_at, fetched_at, error)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (variant_id) DO UPDATE SET
               points = EXCLUDED.points, latest_at = EXCLUDED.latest_at,
               fetched_at = EXCLUDED.fetched_at, error = EXCLUDED.error""",
            (variant_id, Jsonb(points), latest_at, now, error),
        )
    return _result(points, latest_at, now, error)


def _result(points: list[dict[str, Any]], latest_at: datetime | None,
            fetched_at: datetime, error: str | None) -> dict[str, Any]:
    return {
        "source": "csmoney_wiki_trade_quote",
        "source_url": SOURCE_URL,
        "currency": "USD",
        "points": points,
        "latest_at": latest_at,
        "fetched_at": fetched_at,
        "error": error,
    }
