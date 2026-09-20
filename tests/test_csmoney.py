import pytest

from backend.app import csmoney_data
from backend.app.marketplaces.csmoney import (
    CsMoneyRequestError,
    extract_capture,
    storefront_url,
)


NAME = "AK-47 | Redline (Field-Tested)"


def item(listing_id, price, name=NAME, *, phase=None):
    return {
        "id": listing_id,
        "pricing": {"computed": price},
        "asset": {
            "names": {"full": name},
            "phase": phase,
            "float": 0.245,
            "pattern": 87,
            "images": {"steam": "https://example.com/item.png"},
        },
    }


def test_exact_variant_keeps_ten_cheapest_individual_usd_listings():
    items = [item("other", "25.00", "AK-47 | Redline (Minimal Wear)")]
    items += [item(str(index), f"{26 + index / 100:.2f}") for index in range(12)]
    items.append(item("0", "26.12"))
    result = extract_capture(items, NAME)

    assert result["source_url"] == storefront_url(NAME)
    assert [listing["listing_id"] for listing in result["listings"]] == [str(i) for i in range(10)]
    assert [listing["price_cents"] for listing in result["listings"]] == list(range(2600, 2610))
    assert result["listings"][0]["float_value"] == 0.245
    assert result["listings"][0]["paint_seed"] == 87
    assert result["exact_matches"] == 12
    assert result["is_partial"] is False


def test_full_page_with_fewer_than_ten_matches_is_partial():
    items = [item(str(i), i + 1, "Other Skin") for i in range(60)]
    items[10] = item("target", 11, NAME)
    result = extract_capture(items, NAME)

    assert result["exact_matches"] == 1
    assert result["is_partial"] is True


def test_phase_is_matched_without_mixing_other_phases():
    catalog_name = "★ Karambit | Doppler (Factory New)"
    items = [
        item("phase-1", 100, "★ Karambit | Doppler Phase 1 (Factory New)", phase="Phase 1"),
        item("ruby", 200, "★ Karambit | Doppler Ruby (Factory New)", phase="Ruby"),
    ]
    result = extract_capture(items, catalog_name, phase="Ruby")

    assert [listing["listing_id"] for listing in result["listings"]] == ["ruby"]


def test_unsorted_or_invalid_prices_reject_capture():
    with pytest.raises(CsMoneyRequestError, match="not sorted"):
        extract_capture([item("1", "20.00"), item("2", "19.99")], NAME)
    with pytest.raises(CsMoneyRequestError, match="invalid computed price"):
        extract_capture([item("1", "NaN")], NAME)


def test_unresolved_full_page_invalidates_old_quote_without_deleting_old_rows(monkeypatch):
    statements = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, _params):
            statements.append(sql)

    monkeypatch.setattr(csmoney_data, "get_connection", FakeConnection)
    stored = csmoney_data.store_variant_capture(
        "variant", {"page_items": 60, "is_partial": True, "listings": []}
    )

    assert stored == 0
    assert any("fetched_at = NULL" in sql for sql in statements)
    assert not any("DELETE FROM marketplace_active_listings" in sql for sql in statements)
