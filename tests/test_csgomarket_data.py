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
