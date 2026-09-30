from datetime import datetime, timedelta, timezone

import pytest

from backend.app import csmoney_data


def state(variant_id, *, source="storefront", age=0, error=None, partial=False):
    return {
        "id": variant_id, "market_hash_name": variant_id, "wear_name": "Field-Tested",
        "stattrak": variant_id == "stattrak", "souvenir": variant_id == "souvenir",
        "image_url": None, "fetched_at": (
            datetime.now(timezone.utc) - timedelta(hours=age) if age is not None else None
        ),
        "last_attempt_at": datetime.now(timezone.utc), "last_error": error,
        "is_partial": partial, "quote_source": source,
        "summary_price_cents": 2578, "summary_quantity": 1519,
        "summary_item_url": "https://example.com/summary",
    }


def listing(variant_id, *, age=0):
    return {
        "listing_id": "lot-" + variant_id, "variant_id": variant_id,
        "price_cents": 2600, "item_url": "https://example.com/lot",
        "float_value": None, "paint_seed": None, "image_url": None,
        "stickers": [], "charms": [],
        "fetched_at": datetime.now(timezone.utc) - timedelta(hours=age),
    }


def mock_cache(monkeypatch, variants, rows):
    monkeypatch.setenv("CSMONEY_CACHE_TTL_SECONDS", "1800")
    monkeypatch.setattr(csmoney_data, "_skin_context", lambda _id: (
        {"id": "skin", "name": "Redline", "image_url": None}, variants,
    ))
    queued = []
    monkeypatch.setattr(csmoney_data, "enqueue_variants", lambda ids, **_kwargs: queued.extend(ids))

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, params):
            self.selected = params[1]
            return self

        def fetchall(self):
            return [row for row in rows if row["variant_id"] in self.selected]

    monkeypatch.setattr(csmoney_data, "get_connection", Connection)
    monkeypatch.setattr(csmoney_data, "load_variant_context", lambda variant_id: {
        "skin_id": "skin", "market_hash_name": variant_id,
    })
    return queued


@pytest.mark.parametrize("healthy_source", ["storefront", "wiki_market_summary"])
def test_any_variant_error_does_not_hide_healthy_sibling(monkeypatch, healthy_source):
    variants = [state("normal", source=healthy_source, partial=healthy_source != "storefront"),
                state("stattrak", age=None, error="http_403_challenge")]
    rows = [listing("normal")] if healthy_source == "storefront" else []
    mock_cache(monkeypatch, variants, rows)

    result = csmoney_data.get_csmoney_skin_listings("skin")

    assert result["error"] is None
    assert result["status"] == result["source_state"] == "partial"
    assert result["is_partial"] is True
    healthy, failed = result["variant_states"]
    assert healthy["source_state"] == (
        "listings_available" if rows else "summary_only"
    )
    assert failed["status"] == "unavailable"
    assert failed["error"] == "http_403_challenge"
    assert len(result["listings"]) == len(rows)

    failed_only = csmoney_data.get_csmoney_skin_listings("skin", variant="stattrak")
    assert failed_only["error"] == "http_403_challenge"
    assert failed_only["source_state"] == "provider_unavailable"
    assert failed_only["status"] == "unavailable"


@pytest.mark.parametrize("source,age,rows,expected", [
    ("storefront", 0, [listing("normal")], "listings_available"),
    ("wiki_market_summary", 0, [], "summary_only"),
    (None, None, [], "provider_unavailable"),
    ("storefront", 2, [listing("normal", age=2)], "stale"),
    ("wiki_market_summary", 2, [], "stale"),
    ("storefront", 0, [], "empty"),
    ("storefront", 0, [listing("normal", age=2)], "stale"),
])
def test_details_expose_source_state_without_inventing_listings(monkeypatch, source, age, rows, expected):
    mock_cache(monkeypatch, [state("normal", source=source, age=age)], rows)
    result = csmoney_data.get_csmoney_variant_details("normal")

    assert result["source_state"] == expected
    assert result["variant_states"][0]["source_state"] == expected
    assert result["stats"] == {"sales_count": None, "sales_per_day": None, "liquidity_score": None}
    assert result["sales"] == []
    if expected == "summary_only":
        assert result["listings"] == []
        assert result["overview"]["price_cents"] == 2578
        assert result["quote_source"] == "wiki_market_summary"
    if expected == "stale":
        assert result["stale"] is True
        assert all(row["stale"] for row in result["listings"])


def test_filters_do_not_change_source_availability(monkeypatch):
    mock_cache(monkeypatch, [state("normal")], [listing("normal")])
    result = csmoney_data.get_csmoney_skin_listings("skin", has_stickers=True)
    assert result["listings"] == []
    assert result["source_state"] == "listings_available"
    assert result["status"] == "ok"


def test_all_failed_variants_keep_aggregate_error(monkeypatch):
    mock_cache(monkeypatch, [state("normal", age=None, error="timeout"),
                             state("stattrak", age=None, error="malformed")], [])
    result = csmoney_data.get_csmoney_skin_listings("skin")
    assert result["source_state"] == "provider_unavailable"
    assert result["status"] == "unavailable"
    assert result["error"] == "timeout"


def test_stale_price_summary_excluded_from_roi_inputs(monkeypatch):
    row = state("normal", age=2)
    row.update(variant_id="normal", listing_id="lot-normal", price_cents=2600,
               item_url=None, float_value=None, quantity=1, is_available=True)
    monkeypatch.setenv("CSMONEY_CACHE_TTL_SECONDS", "1800")
    monkeypatch.setattr(csmoney_data, "enqueue_variants", lambda *_args, **_kwargs: None)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args):
            return self

        def fetchall(self):
            return [row]

    monkeypatch.setattr(csmoney_data, "get_connection", Connection)
    assert csmoney_data.get_csmoney_prices("skin")["variants"][0]["listing"] is None


def test_fresh_listing_precedes_stale_cheaper_listing_at_limit(monkeypatch):
    variants = [state("normal"), state("stattrak", age=2)]
    fresh = listing("normal")
    stale = listing("stattrak", age=2)
    stale["price_cents"] = 100
    mock_cache(monkeypatch, variants, [stale, fresh])
    result = csmoney_data.get_csmoney_skin_listings("skin", limit=1)
    assert [row["variant_id"] for row in result["listings"]] == ["normal"]


def test_mixed_variant_sources_are_reported_as_mixed(monkeypatch):
    variants = [state("normal"), state("stattrak", source="wiki_market_summary")]
    mock_cache(monkeypatch, variants, [listing("normal")])
    result = csmoney_data.get_csmoney_skin_listings("skin")
    assert result["quote_source"] == "mixed"
    assert [row["quote_source"] for row in result["variant_states"]] == [
        "storefront", "wiki_market_summary",
    ]


def test_empty_capture_has_no_quote_source(monkeypatch):
    mock_cache(monkeypatch, [state("normal")], [])
    result = csmoney_data.get_csmoney_variant_details("normal")
    assert result["source_state"] == "empty"
    assert result["quote_source"] is None
    assert result["variant_states"][0]["quote_source"] == "storefront"
