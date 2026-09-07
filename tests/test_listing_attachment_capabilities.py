"""Current marketplace capabilities for sticker and charm listing filters.

The listing API supports attachment presence filters (``has_stickers`` and
``has_charm``), not filtering listings by a particular attachment name or id.
Standalone sticker/charm items are covered by the complete catalogue search.
These tests intentionally document that boundary as well as the different
implementation offered by each marketplace.
"""

from backend.app import csgomarket_data, market_data
from backend.app.main import app
from backend.app.marketplaces import whitemarket


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeCsfloatConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params):
        if "FROM skins WHERE id" in query:
            return FakeResult(
                [
                    {
                        "id": "skin-1",
                        "name": "AK-47 | Redline",
                        "image_url": "skin.png",
                        "paint_index": "282",
                        "min_float": 0.1,
                        "max_float": 0.7,
                    }
                ]
            )
        return FakeResult(
            [
                {
                    "id": "variant-ft",
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                }
            ]
        )


class FakeCsgoMarketConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params):
        if "SELECT id, name, image_url FROM skins" in query:
            return FakeResult(
                [
                    {
                        "id": "skin-1",
                        "name": "AK-47 | Redline",
                        "image_url": "skin.png",
                    }
                ]
            )
        return FakeResult(
            [
                {
                    "id": "variant-ft",
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                    "wear_name": "Field-Tested",
                    "stattrak": False,
                    "souvenir": False,
                    "image_url": "variant.png",
                }
            ]
        )


def _csfloat_listing(listing_id, *, stickers=None, charms=None):
    return {
        "listing_id": listing_id,
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "item_name": "AK-47 | Redline",
        "price_cents": 10_000,
        "stickers": stickers or [],
        "charms": charms or [],
    }


def test_csfloat_applies_sticker_and_charm_presence_filters_locally(monkeypatch):
    """CSFloat has both filters, implemented after a broader API fetch."""
    captured = {}

    def fake_search_market_listings(**kwargs):
        captured.update(kwargs)
        return [
            _csfloat_listing("plain"),
            _csfloat_listing("sticker", stickers=[{"name": "Sticker | Test"}]),
            _csfloat_listing("charm", charms=[{"name": "Charm | Test"}]),
            _csfloat_listing(
                "both",
                stickers=[{"name": "Sticker | Test"}],
                charms=[{"name": "Charm | Test"}],
            ),
        ]

    monkeypatch.setattr(market_data, "get_connection", FakeCsfloatConnection)
    monkeypatch.setattr(
        market_data, "search_market_listings", fake_search_market_listings
    )

    result = market_data.get_csfloat_skin_listings(
        "skin-1", has_stickers=True, has_charm=True, limit=10
    )

    assert captured["limit"] == 50
    assert [listing["listing_id"] for listing in result["listings"]] == ["both"]
    assert result["error"] is None


def test_whitemarket_passes_both_presence_filters_to_graphql(monkeypatch):
    """WhiteMarket supports both filters natively in its search input."""
    captured = {}

    def fake_graphql_request(_query, variables):
        captured.update(variables)
        return {"market_list": {"totalCount": 0, "edges": []}}

    monkeypatch.setattr(whitemarket, "_graphql_request", fake_graphql_request)

    listings = whitemarket.get_active_listings(
        "AK-47 | Redline (Field-Tested)",
        has_stickers=True,
        has_charm=True,
    )

    assert listings == []
    assert captured["search"]["csgoStickers"] is True
    assert captured["search"]["csgoCharm"] is True


def test_csgomarket_passes_sticker_presence_filter_to_market_api(monkeypatch):
    """CSGO Market can request listings that contain at least one sticker."""
    captured = {}

    def fake_active_listings(market_hash_name, *, limit, with_stickers):
        captured.update(
            market_hash_name=market_hash_name,
            limit=limit,
            with_stickers=with_stickers,
        )
        return [
            {
                "listing_id": "sticker-listing",
                "price_cents": 10_000,
                "float_value": 0.2,
                "stickers": [{"id": "123"}],
                "charms": [],
            }
        ]

    monkeypatch.setattr(
        csgomarket_data, "get_connection", FakeCsgoMarketConnection
    )
    monkeypatch.setattr(
        csgomarket_data, "get_active_listings", fake_active_listings
    )

    result = csgomarket_data.get_csgomarket_skin_listings(
        "skin-1", has_stickers=True
    )

    assert captured == {
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "limit": 50,
        "with_stickers": True,
    }
    assert [listing["listing_id"] for listing in result["listings"]] == [
        "sticker-listing"
    ]


def test_csgomarket_explicitly_returns_no_results_for_charm_filter(monkeypatch):
    """CSGO Market exposes no charm data, so the capability is unavailable."""

    def unexpected_market_call(*_args, **_kwargs):
        raise AssertionError("charm filtering must not call the CSGO Market API")

    monkeypatch.setattr(
        csgomarket_data, "get_connection", FakeCsgoMarketConnection
    )
    monkeypatch.setattr(
        csgomarket_data, "get_active_listings", unexpected_market_call
    )

    result = csgomarket_data.get_csgomarket_skin_listings(
        "skin-1", has_charm=True
    )

    assert result["listings"] == []
    assert result["error"] is None


def test_listing_api_supports_presence_but_not_attachment_name_filter():
    """Listing filters do not claim to select a particular attachment."""
    schema = app.openapi()
    listing_paths = (
        "/api/skins/{skin_id}/market/csfloat/listings",
        "/api/skins/{skin_id}/market/csgomarket/listings",
        "/api/skins/{skin_id}/market/whitemarket/listings",
    )
    unsupported_name_search_parameters = {
        "q",
        "sticker",
        "sticker_id",
        "sticker_name",
        "sticker_query",
        "charm",
        "charm_id",
        "charm_name",
        "charm_query",
    }

    for path in listing_paths:
        parameters = {
            parameter["name"]: parameter
            for parameter in schema["paths"][path]["get"]["parameters"]
        }
        assert parameters["has_stickers"]["schema"]["type"] == "boolean"
        assert parameters["has_stickers"]["schema"]["default"] is False
        assert parameters["has_charm"]["schema"]["type"] == "boolean"
        assert parameters["has_charm"]["schema"]["default"] is False
        assert not unsupported_name_search_parameters.intersection(parameters)
