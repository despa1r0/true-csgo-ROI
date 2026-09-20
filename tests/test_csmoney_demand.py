from datetime import datetime, timedelta, timezone

from backend.app import csmoney_demand
from backend.app import csgomarket


NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def sale(when):
    return {"sold_at": when.isoformat().replace("+00:00", "Z")}


def row(variant_id, *, csfloat=None, csgomarket=None, cf_error=None, cm_error=None):
    return {
        "variant_id": variant_id,
        "market_hash_name": f"Item {variant_id} (Field-Tested)",
        "csfloat_sales": csfloat,
        "csfloat_sales_error": cf_error,
        "csfloat_fetched_at": NOW - timedelta(hours=1),
        "csgomarket_sales": csgomarket,
        "csgomarket_sales_error": cm_error,
        "csgomarket_fetched_at": NOW - timedelta(hours=1),
        "signal_source": None,
        "signal_count": None,
        "signal_status": None,
        "signal_checked_at": None,
    }


def test_prefers_csfloat_and_falls_back_to_csgomarket_for_missing_window():
    rows = [
        row("a", csfloat=[sale(NOW - timedelta(hours=1))], csgomarket=[sale(NOW)] * 3),
        row("b", csfloat=[sale(NOW - timedelta(days=8))], csgomarket=[sale(NOW)] * 2),
        row("c", csfloat=[], csgomarket=[sale(NOW)]),
        row("d", csfloat=[sale(NOW)], csgomarket=[sale(NOW)] * 4, cf_error="timeout"),
        row("e", csfloat=[], csgomarket=[]),
    ]

    ranked = csmoney_demand.rank_cached_sales(rows, now=NOW)

    assert [(entry["variant_id"], entry["sales_count_7d"], entry["sales_source"])
            for entry in ranked] == [
        ("d", 4, "CSGO Market"),
        ("b", 2, "CSGO Market"),
        ("a", 1, "CSFloat"),
        ("c", 1, "CSGO Market"),
    ]


def test_counts_only_valid_sales_within_seven_days_and_fresh_cache():
    boundary = NOW - timedelta(days=7)
    fresh = row("fresh", csfloat=[
        sale(boundary), sale(NOW), sale(boundary - timedelta(seconds=1)),
        sale(NOW + timedelta(seconds=1)), {"sold_at": "bad date"},
        {"sold_at": "2026-09-20T10:00:00"}, {}, "not a sale",
    ])
    stale = row("stale", csfloat=[sale(NOW)] * 100)
    stale["csfloat_fetched_at"] = NOW - timedelta(days=2)
    future = row("future", csfloat=[sale(NOW)])
    future["csfloat_fetched_at"] = NOW + timedelta(minutes=1)

    ranked = csmoney_demand.rank_cached_sales([stale, fresh, future], now=NOW)

    assert [entry["variant_id"] for entry in ranked] == ["fresh"]
    assert ranked[0]["sales_count_7d"] == 2


def test_falls_back_when_csfloat_cache_stale_or_sales_error():
    stale = row("stale", csfloat=[sale(NOW)] * 4, csgomarket=[sale(NOW)] * 2)
    stale["csfloat_fetched_at"] = NOW - timedelta(days=2)
    bad_csgomarket = row("error", csfloat=[], csgomarket=[sale(NOW)] * 3,
                         cm_error="request failed")

    ranked = csmoney_demand.rank_cached_sales([stale, bad_csgomarket], now=NOW)

    assert len(ranked) == 1
    assert ranked[0]["variant_id"] == "stale"
    assert ranked[0]["sales_source"] == "CSGO Market"


def test_rank_uses_persisted_signal_when_detail_cache_is_missing():
    persisted = row("persisted")
    persisted.update({
        "signal_source": "CSGO Market",
        "signal_count": 8,
        "signal_status": "observed",
        "signal_checked_at": NOW - timedelta(hours=2),
    })
    unknown = row("unknown")
    unknown.update({
        "signal_source": "CSGO Market",
        "signal_count": None,
        "signal_status": "unobserved",
        "signal_checked_at": NOW - timedelta(hours=2),
    })

    ranked = csmoney_demand.rank_cached_sales([persisted, unknown], now=NOW)

    assert [entry["variant_id"] for entry in ranked] == ["persisted"]
    assert ranked[0]["sales_count_7d"] == 8


def test_database_entrypoint_uses_cache_without_external_requests(monkeypatch):
    class FakeCursor:
        def fetchall(self):
            return [row("a", csfloat=[sale(NOW)])]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query):
            assert "marketplace_variant_details" in query
            return FakeCursor()

    monkeypatch.setattr(csmoney_demand, "get_connection", FakeConnection)

    ranked = csmoney_demand.get_observed_sales_priorities(limit=1, now=NOW)

    assert ranked == [{
        "variant_id": "a",
        "market_hash_name": "Item a (Field-Tested)",
        "sales_count_7d": 1,
        "sales_source": "CSFloat",
    }]


def test_targeted_fallback_makes_one_csgomarket_call_only_on_cache_miss(monkeypatch):
    current = row("a", csfloat=[])

    class FakeCursor:
        def fetchone(self):
            return current

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params):
            assert params == ("a",)
            assert "WHERE v.id = %s" in query
            return FakeCursor()

    calls = []

    def fake_sales(name, *, limit):
        calls.append((name, limit))
        return [sale(NOW - timedelta(hours=2)), sale(NOW - timedelta(days=8))]

    monkeypatch.setattr(csmoney_demand, "get_connection", FakeConnection)
    monkeypatch.setattr(csgomarket, "get_sales_history", fake_sales)
    monkeypatch.setattr(csmoney_demand, "_save_signal", lambda *_args: None)

    assert csmoney_demand.get_targeted_sales_priority("a", now=NOW) is None
    fallback = csmoney_demand.get_targeted_sales_priority(
        "a", now=NOW, fetch_csgomarket_on_miss=True
    )
    assert fallback["sales_count_7d"] == 1
    assert fallback["sales_source"] == "CSGO Market"
    assert calls == [("Item a (Field-Tested)", 200)]

    current = row("a", csfloat=[sale(NOW)])
    cached = csmoney_demand.get_targeted_sales_priority(
        "a", now=NOW, fetch_csgomarket_on_miss=True
    )
    assert cached["sales_source"] == "CSFloat"
    assert len(calls) == 1

    current = row("a", csfloat=[])
    current["signal_checked_at"] = NOW - timedelta(hours=23)
    current["signal_status"] = "unobserved"
    assert csmoney_demand.get_targeted_sales_priority(
        "a", now=NOW, fetch_csgomarket_on_miss=True
    ) is None
    assert len(calls) == 1


def test_gradual_refresh_limits_requests_and_persists_errors(monkeypatch):
    rows = [
        row("cached", csfloat=[sale(NOW)]),
        row("miss", csfloat=[]),
        row("error", csfloat=[]),
        row("deferred", csfloat=[]),
    ]
    saves = []

    class FakeCursor:
        def fetchall(self):
            return rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, params):
            assert "ds.checked_at <= %s" in query
            assert params == (NOW - timedelta(days=1), 20)
            return FakeCursor()

    def fake_sales(name, *, limit):
        assert limit == 200
        if "error" in name:
            raise csgomarket.CsgoMarketRequestError("temporary failure")
        return []

    monkeypatch.setattr(csmoney_demand, "get_connection", FakeConnection)
    monkeypatch.setattr(csmoney_demand, "_save_signal", lambda *args: saves.append(args))
    monkeypatch.setattr(csgomarket, "get_sales_history", fake_sales)

    stats = csmoney_demand.refresh_missing_demand_signals(
        batch_size=20, max_requests=2, now=NOW
    )

    assert stats == {
        "checked": 3, "requests": 2, "observed": 1,
        "unobserved": 1, "errors": 1,
    }
    assert [entry[0] for entry in saves] == ["cached", "miss", "error"]
    assert saves[1][2:4] == (None, "unobserved")
    assert saves[2][2:5] == (None, "error", "temporary failure")
