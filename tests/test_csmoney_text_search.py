from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app import csmoney_search, csmoney_worker
from backend.app.main import app
from backend.app.marketplaces.csmoney import (
    CsMoneyBlockedError, capture_search, storefront_url,
)
from backend.app.routers import csmoney as router


def test_api_uses_catalogue_before_enqueuing_and_returns_deduplicated_request(monkeypatch):
    calls = []
    request_id = uuid4()
    monkeypatch.setattr(router, "search_skins", lambda query, limit: [{"id": "known"}] if query == "known" else [])
    monkeypatch.setattr(router, "enqueue_search", lambda query: (calls.append(query) or {
        "request_id": request_id, "status": "queued",
    }))
    with pytest.raises(HTTPException) as error:
        router.create_csmoney_search(router.TextSearchRequest(query="known"))
    assert error.value.status_code == 409
    assert calls == []
    response = router.create_csmoney_search(router.TextSearchRequest(query="missing"))
    assert response == {"request_id": request_id, "status": "queued"}
    assert calls == ["missing"]


def test_text_search_adds_routes_without_changing_local_search_methods():
    paths = app.openapi()["paths"]
    assert list(paths["/api/items/search"]) == ["get"]
    assert list(paths["/api/skins/search"]) == ["get"]
    assert list(paths["/api/market/csmoney/search"]) == ["post"]
    assert list(paths["/api/market/csmoney/search/{request_id}"]) == ["get"]


def test_query_validation_and_expiry_status(monkeypatch):
    assert csmoney_search.normalize_query("  Rare  CHARM ") == ("Rare CHARM", "rare charm")
    for query in ("x", "x" * 101, "\n\t", "\u200bitem"):
        with pytest.raises(ValueError):
            csmoney_search.normalize_query(query)

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, *_args): return self
        def fetchone(self):
            return {"request_id": uuid4(), "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
                    "status": "complete", "result": {"listings": [1]}, "error": None}

    monkeypatch.setattr(csmoney_search, "get_connection", Connection)
    assert csmoney_search.get_search(uuid4())["status"] == "expired"
    assert csmoney_search.get_search(uuid4())["result"] is None


def test_identical_active_queries_share_database_job(monkeypatch):
    saved = {}

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, sql, params=None):
            self.sql, self.params = sql, params
            if "INSERT INTO" in sql and params[1] not in saved:
                saved[params[1]] = {"request_id": params[0], "status": "queued"}
                self.row = saved[params[1]]
            elif "SELECT request_id, status" in sql:
                self.row = saved[params[0]]
            else:
                self.row = None
            return self
        def fetchone(self): return self.row

    monkeypatch.setattr(csmoney_search, "get_connection", Connection)
    first = csmoney_search.enqueue_search("  Missing   Item ")
    second = csmoney_search.enqueue_search("missing item")
    assert first == second
    assert len(saved) == 1


class FakePage:
    def __init__(self, items, status=200, body=""):
        self.items, self.status, self.body = items, status, body
        self.url = None
    def goto(self, url, **_kwargs):
        self.url = url
        return SimpleNamespace(status=self.status)
    def locator(self, _selector):
        import json
        return SimpleNamespace(all_text_contents=lambda: [json.dumps({"inventory": {"items": self.items}})] if self.body == "" else [])
    def content(self): return self.body


def test_search_encodes_url_and_returns_actual_names_prices_and_links():
    page = FakePage([{"id": 42, "pricing": {"computed": "12.345"},
                      "asset": {"names": {"full": "Actual | Name"}, "float": 0.123,
                                "pattern": 7, "images": {"steam": "https://example.test/a.png"}}}])
    result = capture_search(page, "a & b/кейс")
    assert parse_qs(urlparse(page.url).query)["search"] == ["a & b/кейс"]
    assert page.url == storefront_url("a & b/кейс")
    assert result["listings"][0] == {
        "listing_id": "42", "item_name": "Actual | Name", "price_cents": 1235,
        "item_url": storefront_url("Actual | Name"), "float_value": 0.123, "paint_seed": 7,
        "image_url": "https://example.test/a.png", "phase": None,
    }


@pytest.mark.parametrize("status,body", [(403, ""), (429, ""), (200, "<title>Just a moment</title>Cloudflare")])
def test_security_response_blocks_without_partial_result(status, body):
    with pytest.raises(CsMoneyBlockedError):
        capture_search(FakePage([], status=status, body=body), "missing")


def test_worker_reuses_context_closes_tab_and_never_writes_catalogue(monkeypatch):
    actions = []
    request_id = uuid4()
    tab = SimpleNamespace(close=lambda: actions.append("close"))
    context = SimpleNamespace(new_page=lambda: (actions.append("new_page") or tab))
    existing_page = SimpleNamespace(context=context)
    monkeypatch.setattr(csmoney_worker, "claim_search", lambda: {"request_id": request_id, "query": "missing"})
    monkeypatch.setattr(csmoney_worker, "capture_search", lambda page, query: (
        actions.append((page, query)) or {"listings": [{"listing_id": "1"}]}
    ))
    monkeypatch.setattr(csmoney_worker, "finish_search", lambda *args, **kwargs: actions.append((args, kwargs)))
    assert csmoney_worker.process_search(existing_page)
    assert actions[0] == "new_page"
    assert actions[1] == (tab, "missing")
    assert actions[2][0] == (request_id, "complete")
    assert actions[-1] == "close"


def test_search_result_is_stored_only_in_the_text_queue(monkeypatch):
    statements = []

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def execute(self, sql, _params): statements.append(sql)

    monkeypatch.setattr(csmoney_search, "get_connection", Connection)
    csmoney_search.finish_search(uuid4(), "complete", result={"listings": [{"listing_id": "1"}]})
    assert len(statements) == 1
    assert "UPDATE csmoney_text_search_jobs" in statements[0]
    assert all(table not in statements[0] for table in
               ("skins ", "skin_variants ", "marketplace_listings ", "marketplace_active_listings "))


@pytest.mark.parametrize("code", [403, 429])
def test_worker_opens_circuit_and_blocks_next_search(code, monkeypatch):
    actions = []
    tab = SimpleNamespace(close=lambda: actions.append("close"))
    page = SimpleNamespace(context=SimpleNamespace(new_page=lambda: tab))
    monkeypatch.setattr(csmoney_worker, "claim_search", lambda: {"request_id": uuid4(), "query": "missing"})
    monkeypatch.setattr(csmoney_worker, "capture_search", lambda *_args: (_ for _ in ()).throw(
        CsMoneyBlockedError(f"CS.MONEY page returned {code}")))
    monkeypatch.setattr(csmoney_worker, "finish_search", lambda *args, **kwargs: actions.append((args, kwargs)))
    with pytest.raises(CsMoneyBlockedError):
        csmoney_worker.process_search(page)
    assert actions[0][0][1] == "blocked"
    assert "result" not in actions[0][1]
    assert actions[1] == "close"
    assert csmoney_worker.process_search(None, circuit_open=True)
    assert actions[2][0][1] == "blocked"
