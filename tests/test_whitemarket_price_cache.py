"""WhiteMarket price refresh should preserve usable cached variants on failure."""

from datetime import datetime, timezone

from backend.app import market_data
from backend.app.marketplaces.whitemarket import WhitemarketRequestError


def _install_cache(monkeypatch, variants, cached_rows):
    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, sql, _parameters):
            return FakeCursor(
                variants if sql.lstrip().startswith("SELECT id, market_hash_name")
                else cached_rows
            )

    monkeypatch.setattr(market_data, "get_connection", FakeConnection)


def _cached(variant_id, *, fresh):
    return {
        "variant_id": variant_id,
        "listing_id": f"listing-{variant_id}",
        "price_cents": 1000,
        "item_url": "https://white.market/item/test",
        "float_value": None,
        "quantity": 1,
        "is_available": True,
        "fetched_at": datetime.now(timezone.utc),
        "is_fresh": fresh,
    }


def test_invalid_partner_token_stops_variant_fanout_and_keeps_fresh_cache(monkeypatch):
    variants = [
        {"id": "fresh", "market_hash_name": "Fresh Skin"},
        {"id": "stale", "market_hash_name": "Stale Skin"},
        {"id": "missing", "market_hash_name": "Missing Skin"},
    ]
    _install_cache(monkeypatch, variants, [_cached("fresh", fresh=True), _cached("stale", fresh=False)])
    calls = []

    def rejected(name):
        calls.append(name)
        raise WhitemarketRequestError("WhiteMarket rejected partner token (HTTP 403)")

    monkeypatch.setattr(market_data, "get_whitemarket_cheapest_listing", rejected)
    monkeypatch.setattr(market_data, "_store_whitemarket_listing_rows", lambda _rows: None)

    result = market_data.get_whitemarket_prices("skin-1")

    assert calls == ["Stale Skin"]
    by_id = {item["variant_id"]: item for item in result["variants"]}
    assert by_id["fresh"]["listing"]["stale"] is False
    assert by_id["fresh"]["error"] is None
    assert by_id["stale"]["listing"]["stale"] is True
    assert "partner token" in by_id["stale"]["error"]
    assert by_id["missing"]["listing"] is None
    assert "partner token" in by_id["missing"]["error"]


def test_successful_variant_remains_fresh_when_another_variant_fails(monkeypatch):
    variants = [
        {"id": "first", "market_hash_name": "First Skin"},
        {"id": "second", "market_hash_name": "Second Skin"},
    ]
    _install_cache(monkeypatch, variants, [_cached("second", fresh=False)])
    saved = []

    def fetch(name):
        if name == "Second Skin":
            raise WhitemarketRequestError("WhiteMarket temporarily unavailable (HTTP 500)")
        return {
            "listing_id": "new-listing", "price_cents": 900,
            "item_url": "https://white.market/item/new", "quantity": 2,
        }

    monkeypatch.setattr(market_data, "get_whitemarket_cheapest_listing", fetch)
    monkeypatch.setattr(market_data, "_store_whitemarket_listing_rows", lambda rows: saved.extend(rows))

    result = market_data.get_whitemarket_prices("skin-1")

    by_id = {item["variant_id"]: item for item in result["variants"]}
    assert by_id["first"]["listing"]["price_cents"] == 900
    assert by_id["first"]["listing"]["stale"] is False
    assert by_id["first"]["error"] is None
    assert by_id["second"]["listing"]["stale"] is True
    assert "HTTP 500" in by_id["second"]["error"]
    assert [row["variant_id"] for row in saved] == ["first"]


def test_one_variant_server_error_does_not_hide_other_variants(monkeypatch):
    variants = [
        {"id": "first", "market_hash_name": "First Skin"},
        {"id": "second", "market_hash_name": "Second Skin"},
    ]
    _install_cache(monkeypatch, variants, [])
    calls = []

    def fetch(name):
        calls.append(name)
        if name == "First Skin":
            raise WhitemarketRequestError("WhiteMarket temporarily unavailable (HTTP 500)")
        return {"listing_id": "second-listing", "price_cents": 1200}

    monkeypatch.setattr(market_data, "get_whitemarket_cheapest_listing", fetch)
    monkeypatch.setattr(market_data, "_store_whitemarket_listing_rows", lambda _rows: None)

    result = market_data.get_whitemarket_prices("skin-1")

    by_id = {item["variant_id"]: item for item in result["variants"]}
    assert calls == ["First Skin", "Second Skin"]
    assert by_id["first"]["listing"] is None
    assert "HTTP 500" in by_id["first"]["error"]
    assert by_id["second"]["listing"]["stale"] is False
    assert by_id["second"]["error"] is None
