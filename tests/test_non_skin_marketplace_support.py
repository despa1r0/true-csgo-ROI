from backend.app import market_data


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeNonSkinConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params):
        if "FROM skins WHERE id" in query:
            return FakeResult(
                [
                    {
                        "id": "sticker-1",
                        "name": "Sticker | Test",
                        "item_type": "sticker",
                        "image_url": "sticker.png",
                        "paint_index": None,
                        "min_float": None,
                        "max_float": None,
                    }
                ]
            )
        return FakeResult(
            [
                {
                    "id": "catalog-variant-sticker-1",
                    "market_hash_name": "Sticker | Test",
                    "wear_name": None,
                    "stattrak": False,
                    "souvenir": False,
                    "image_url": "variant.png",
                }
            ]
        )


def test_csfloat_non_skin_listings_use_exact_market_name_without_paint_index(
    monkeypatch,
):
    calls = []

    def fake_active_listings(market_hash_name, *, limit):
        calls.append((market_hash_name, limit))
        return [
            {
                "listing_id": "listing-1",
                "price_cents": 125,
                "item_url": "https://csfloat.com/item/listing-1",
                "float_value": None,
                "stickers": [],
                "charms": [],
            }
        ]

    def unexpected_paint_search(**_kwargs):
        raise AssertionError("non-skin items must not use paint-index search")

    monkeypatch.setattr(market_data, "get_connection", FakeNonSkinConnection)
    monkeypatch.setattr(market_data, "get_active_listings", fake_active_listings)
    monkeypatch.setattr(
        market_data, "search_market_listings", unexpected_paint_search
    )

    result = market_data.get_csfloat_skin_listings(
        "sticker-1", sort_by="best_deal", min_price_cents=100, limit=30
    )

    assert calls == [("Sticker | Test", 10)]
    assert result["sort_by"] == "lowest_price"
    assert result["requested_sort_by"] == "best_deal"
    assert result["error"] is None
    assert result["listings"][0] == {
        "listing_id": "listing-1",
        "price_cents": 125,
        "item_url": "https://csfloat.com/item/listing-1",
        "float_value": None,
        "stickers": [],
        "charms": [],
        "marketplace": "CSFloat",
        "marketplace_id": "csfloat",
        "market_hash_name": "Sticker | Test",
        "variant_id": "catalog-variant-sticker-1",
        "wear_name": None,
        "image_url": "variant.png",
        "item_name": "Sticker | Test",
    }


def test_csfloat_non_skin_listings_keep_server_side_price_filters(monkeypatch):
    monkeypatch.setattr(market_data, "get_connection", FakeNonSkinConnection)
    monkeypatch.setattr(
        market_data,
        "get_active_listings",
        lambda *_args, **_kwargs: [
            {
                "listing_id": "too-cheap",
                "price_cents": 99,
                "float_value": None,
                "stickers": [],
                "charms": [],
            },
            {
                "listing_id": "accepted",
                "price_cents": 150,
                "float_value": None,
                "stickers": [],
                "charms": [],
            },
            {
                "listing_id": "too-expensive",
                "price_cents": 201,
                "float_value": None,
                "stickers": [],
                "charms": [],
            },
        ],
    )

    result = market_data.get_csfloat_skin_listings(
        "sticker-1", min_price_cents=100, max_price_cents=200
    )

    assert [listing["listing_id"] for listing in result["listings"]] == [
        "accepted"
    ]
