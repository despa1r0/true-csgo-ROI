from datetime import datetime, timedelta, timezone

import pytest

from backend.app import csmoney_wiki


NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def test_wiki_history_matches_exact_variant_and_keeps_recent_usd_quotes(monkeypatch):
    requests = []

    def fake_query(query, variables):
        requests.append(variables)
        if "id" in variables:
            return {"skin": {"hash_name": "AK-47 | Redline", "name_ids": [
                {"name": "AK-47 | Redline (Field-Tested)", "name_id": 77},
                {"name": "StatTrak™ AK-47 | Redline (Field-Tested)", "name_id": 2630},
            ]}}
        return {"price_trader_log": [{"name_id": 77, "values": [
            {"time": int((NOW - timedelta(days=2)).timestamp()), "price_trader_new": 29.555},
            {"time": int(NOW.timestamp()), "price_trader_new": 29.56},
        ]}]}

    monkeypatch.setattr(csmoney_wiki, "_query", fake_query)
    points = csmoney_wiki.fetch_price_history(
        "AK-47 | Redline", "AK-47 | Redline (Field-Tested)", now=NOW,
    )

    assert requests == [{"id": "ak-47-redline"}, {"name_ids": [77]}]
    assert [point["price_cents"] for point in points] == [2956, 2956]


def test_wiki_old_history_is_not_presented_as_current():
    old = int((NOW - timedelta(days=5)).timestamp())
    with pytest.raises(csmoney_wiki.WikiPriceError, match="recent point"):
        csmoney_wiki.parse_price_history(
            [{"name_id": 77, "values": [{"time": old, "price_trader_new": 20}]}],
            name_id=77, now=NOW,
        )


def test_wiki_variant_mismatch_is_rejected(monkeypatch):
    monkeypatch.setattr(csmoney_wiki, "_query", lambda *_: {"skin": {
        "hash_name": "AK-47 | Redline", "name_ids": [
            {"name": "StatTrak™ AK-47 | Redline (Field-Tested)", "name_id": 2630},
        ],
    }})
    with pytest.raises(csmoney_wiki.WikiPriceError, match="variant name"):
        csmoney_wiki.fetch_price_history(
            "AK-47 | Redline", "AK-47 | Redline (Field-Tested)", now=NOW,
        )


def test_wiki_invalid_prices_and_future_points_are_discarded():
    points = csmoney_wiki.parse_price_history(
        [{"name_id": 77, "values": [
            {"time": int(NOW.timestamp()), "price_trader_new": "NaN"},
            {"time": int((NOW + timedelta(days=2)).timestamp()), "price_trader_new": 12},
            {"time": int(NOW.timestamp()), "price_trader_new": 29.56},
        ]}],
        name_id=77, now=NOW,
    )
    assert len(points) == 1
    assert points[0]["price_cents"] == 2956


def test_recent_cache_with_old_latest_point_is_refreshed(monkeypatch):
    current = datetime.now(timezone.utc)
    queried = []

    class FakeCursor:
        def fetchone(self):
            return {
                "points": [{"at": (current - timedelta(days=4)).isoformat(), "price_cents": 2000}],
                "latest_at": current - timedelta(days=4),
                "fetched_at": current - timedelta(hours=1),
                "error": None,
            }

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, *_args):
            queried.append(sql)
            return FakeCursor()

    monkeypatch.setattr(csmoney_wiki, "load_variant_context", lambda _id: {
        "item_name": "AK-47 | Redline", "market_hash_name": "AK-47 | Redline (Field-Tested)",
    })
    monkeypatch.setattr(csmoney_wiki, "get_connection", FakeConnection)
    monkeypatch.setattr(csmoney_wiki, "fetch_price_history", lambda *_args, **_kwargs: [
        {"at": current.isoformat(), "price_cents": 2956},
    ])

    result = csmoney_wiki.get_variant_price_history("variant")

    assert result["points"][0]["price_cents"] == 2956
    assert any("INSERT INTO csmoney_wiki_price_history" in sql for sql in queried)
