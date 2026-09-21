from datetime import datetime, timezone

from backend.app import csgomarket_data


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params):
        if "SELECT id, name, image_url FROM skins" in query:
            return FakeResult([{"id": "skin-1", "name": "AK-47 | Redline", "image_url": "skin.png"}])
        return FakeResult(
            [
                {
                    "id": "normal-ft",
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                    "wear_name": "Field-Tested",
                    "stattrak": False,
                    "souvenir": False,
                    "image_url": "normal.png",
                },
                {
                    "id": "st-ft",
                    "market_hash_name": "StatTrak™ AK-47 | Redline (Field-Tested)",
                    "wear_name": "Field-Tested",
                    "stattrak": True,
                    "souvenir": False,
                    "image_url": None,
                },
            ]
        )


def test_skin_listing_search_filters_and_enriches_market_rows(monkeypatch):
    calls = []

    def fake_listings(market_hash_name, *, limit, with_stickers):
        calls.append((market_hash_name, limit, with_stickers))
        return [
            {
                "listing_id": "listing-1",
                "market_hash_name": market_hash_name,
                "price_cents": 1234,
                "item_url": "https://example.test/listing",
                "float_value": 0.2,
                "stickers": [{"id": "1"}],
                "charms": [],
                "stattrak": market_hash_name.startswith("StatTrak™"),
                "souvenir": False,
            }
        ]

    monkeypatch.setattr(csgomarket_data, "get_connection", FakeConnection)
    monkeypatch.setattr(csgomarket_data, "get_active_listings", fake_listings)

    result = csgomarket_data.get_csgomarket_skin_listings(
        "skin-1",
        wear="field-tested",
        variant="normal",
        min_float=0.1,
        max_float=0.3,
        has_stickers=True,
    )

    assert calls == [("AK-47 | Redline (Field-Tested)", 50, True)]
    assert result["marketplace"] == "CSGO Market"
    assert result["listings"][0]["marketplace_id"] == "csgomarket"
    assert result["listings"][0]["variant_id"] == "normal-ft"
    assert result["listings"][0]["wear_name"] == "Field-Tested"
    assert result["listings"][0]["image_url"] == "normal.png"


def test_charm_filter_returns_no_csgomarket_listings(monkeypatch):
    monkeypatch.setattr(csgomarket_data, "get_connection", FakeConnection)

    result = csgomarket_data.get_csgomarket_skin_listings("skin-1", has_charm=True)

    assert result["listings"] == []
    assert result["error"] is None


def test_detail_marks_sales_float_as_unavailable():
    response = csgomarket_data._detail_response(
        {
            "variant_id": "normal-ft",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "price_cents": 1200,
            "active_listings": 3,
            "item_url": "https://example.test/item",
        },
        {
            "sales_count": 1,
            "sales": [{"price_cents": 1100, "sold_at": "2026-01-01T00:00:00Z", "float_value": None}],
            "listings": [],
            "buy_orders": [],
            "sell_orders": [],
        },
        cached=False,
        stale=False,
    )

    assert response["stats"]["sales_float_available"] is False
    assert "не передаёт float" in response["stats"]["sales_float_note"]


def test_failed_detail_component_is_retried_within_ttl(monkeypatch):
    old_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    context = {
        "variant_id": "variant-1",
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "name": "AK-47 | Redline",
        "price_cents": 1200,
        "active_listings": 1,
        "item_url": None,
    }
    state = {
        "cached": {
            "sales_count": 1,
            "liquidity_score": None,
            "liquidity_label": "unavailable",
            "listings": [{"listing_id": "old-listing", "price_cents": 1200}],
            "sales": [{"price_cents": 1100, "sold_at": "2026-01-01T00:00:00Z"}],
            "buy_orders": [{"price_cents": 1000, "quantity": 1}],
            "sell_orders": [{"price_cents": 1300, "quantity": 1}],
            "listings_error": None,
            "sales_error": None,
            "buy_orders_error": None,
            "listings_fetched_at": old_timestamp,
            "sales_fetched_at": old_timestamp,
            "buy_orders_fetched_at": old_timestamp,
            "fetched_at": old_timestamp,
            "listings_is_fresh": False,
            "sales_is_fresh": False,
            "buy_orders_is_fresh": False,
            "is_fresh": False,
        }
    }
    listing_calls = []

    def fake_load(_variant_id, _ttl_seconds):
        return context, state["cached"]

    def fake_store(_variant_id, detail):
        stored = dict(detail)
        stored["listings_is_fresh"] = stored["listings_error"] is None
        stored["sales_is_fresh"] = stored["sales_error"] is None
        stored["buy_orders_is_fresh"] = stored["buy_orders_error"] is None
        stored["is_fresh"] = all(
            stored[name]
            for name in (
                "listings_is_fresh",
                "sales_is_fresh",
                "buy_orders_is_fresh",
            )
        )
        state["cached"] = stored

    def failed_listings(*_args, **_kwargs):
        listing_calls.append("attempt")
        raise csgomarket_data.CsgoMarketRequestError("listings unavailable")

    monkeypatch.setattr(csgomarket_data, "_load_variant_detail_cache", fake_load)
    monkeypatch.setattr(csgomarket_data, "_store_variant_details", fake_store)
    monkeypatch.setattr(csgomarket_data, "get_active_listings", failed_listings)
    monkeypatch.setattr(
        csgomarket_data,
        "get_sales_history",
        lambda *_args, **_kwargs: [
            {"price_cents": 1150, "sold_at": "2026-01-02T00:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        csgomarket_data,
        "get_order_book",
        lambda *_args, **_kwargs: {
            "buy_orders": [{"price_cents": 1050, "quantity": 2}],
            "sell_orders": [{"price_cents": 1250, "quantity": 2}],
        },
    )

    first = csgomarket_data.get_csgomarket_variant_details("variant-1")
    second = csgomarket_data.get_csgomarket_variant_details("variant-1")

    assert listing_calls == ["attempt", "attempt"]
    assert first["components"]["listings"]["status"] == "stale"
    assert second["components"]["listings"]["status"] == "stale"
    assert second["components"]["sales"]["status"] == "fresh"
    assert second["components"]["buy_orders"]["status"] == "fresh"
    assert state["cached"]["listings_fetched_at"] == old_timestamp
    assert state["cached"]["sales_fetched_at"] > old_timestamp
