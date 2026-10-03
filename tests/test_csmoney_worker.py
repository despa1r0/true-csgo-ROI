import logging
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from backend.app import csmoney_worker
from backend.app.marketplaces.csmoney import CsMoneyRequestError


PAGE = SimpleNamespace(context=SimpleNamespace(new_page=lambda: SimpleNamespace(close=lambda: None)))


def test_storefront_403_uses_exact_wiki_summary_and_trips_circuit(monkeypatch):
    actions = []
    monkeypatch.setattr(csmoney_worker, "claim_refresh_job", lambda: {
        "variant_id": "redline_ft", "attempts": 1,
    })
    monkeypatch.setattr(csmoney_worker, "load_variant_context", lambda _id: {
        "item_name": "AK-47 | Redline",
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
    })
    monkeypatch.setattr(csmoney_worker, "capture_variant", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(CsMoneyRequestError("CS.MONEY page returned 403"))
    ))
    monkeypatch.setattr(csmoney_worker, "fetch_market_summary", lambda *_args: {
        "price_cents": 2578, "quantity": 1519,
    })
    monkeypatch.setattr(csmoney_worker, "store_wiki_market_summary", lambda *args, **kwargs: (
        actions.append((args, kwargs))
    ))
    monkeypatch.setattr(csmoney_worker, "complete_refresh_job", lambda variant_id: (
        actions.append(("complete", variant_id))
    ))

    with pytest.raises(CsMoneyRequestError, match="403"):
        csmoney_worker.process_one(PAGE)

    assert actions[0][0] == ("redline_ft", {"price_cents": 2578, "quantity": 1519})
    assert actions[1] == ("complete", "redline_ft")


def test_wiki_only_mode_does_not_access_storefront(monkeypatch):
    monkeypatch.setattr(csmoney_worker, "claim_refresh_job", lambda: {
        "variant_id": "redline_ft", "attempts": 1,
    })
    monkeypatch.setattr(csmoney_worker, "load_variant_context", lambda _id: {
        "item_name": "AK-47 | Redline",
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
    })
    monkeypatch.setattr(csmoney_worker, "capture_variant", lambda *_args, **_kwargs: (
        pytest.fail("Storefront must be gated after a 403")
    ))
    monkeypatch.setattr(csmoney_worker, "fetch_market_summary", lambda *_args: {
        "price_cents": 2578, "quantity": 1519,
    })
    monkeypatch.setattr(csmoney_worker, "store_wiki_market_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(csmoney_worker, "complete_refresh_job", lambda _id: None)
    assert csmoney_worker.process_one(None)


@pytest.mark.parametrize("page", [None, PAGE])
def test_wiki_success_is_visible_at_info(monkeypatch, caplog, page):
    monkeypatch.setattr(csmoney_worker, "claim_refresh_job", lambda: {
        "variant_id": "redline_ft", "attempts": 1,
    })
    monkeypatch.setattr(csmoney_worker, "load_variant_context", lambda _id: {
        "item_name": "Redline", "market_hash_name": "Redline FT",
    })
    monkeypatch.setattr(csmoney_worker, "capture_variant", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(CsMoneyRequestError("403"))
    ))
    monkeypatch.setattr(csmoney_worker, "fetch_market_summary", lambda *_args: {
        "price_cents": 2578, "quantity": 1519,
    })
    monkeypatch.setattr(csmoney_worker, "store_wiki_market_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(csmoney_worker, "complete_refresh_job", lambda _id: None)
    with caplog.at_level(logging.INFO):
        if page is None:
            csmoney_worker.process_one(page)
        else:
            with pytest.raises(CsMoneyRequestError):
                csmoney_worker.process_one(page)
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.INFO
    assert "source=wiki_market_summary result=ok price_cents=2578 count=1519" in caplog.text


@pytest.mark.parametrize("page", [None, PAGE])
@pytest.mark.parametrize("error,expected", [
    (HTTPError("https://example.com/?token=SECRET", 403, "SECRET", {"Cookie": "SECRET"}, None),
     "http_403_challenge"),
    (HTTPError("https://example.com", 503, "SECRET", {}, None), "http_error"),
    (TimeoutError("SECRET"), "timeout"),
    (URLError(TimeoutError("SECRET")), "timeout"),
    (ValueError("SECRET"), "malformed"),
    (csmoney_worker.WikiPriceError("SECRET"), "malformed"),
    (csmoney_worker.WikiPriceError("SECRET", result="empty"), "empty"),
    (csmoney_worker.WikiPriceError("SECRET", result="network_error"), "network_error"),
    (OSError("SECRET"), "network_error"),
])
def test_wiki_failure_is_classified_and_redacted(monkeypatch, caplog, page, error, expected):
    actions = []
    monkeypatch.setattr(csmoney_worker, "claim_refresh_job", lambda: {
        "variant_id": "redline_ft", "attempts": 1,
    })
    monkeypatch.setattr(csmoney_worker, "load_variant_context", lambda _id: {
        "item_name": "Redline", "market_hash_name": "Redline FT",
    })
    monkeypatch.setattr(csmoney_worker, "capture_variant", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(CsMoneyRequestError("403"))
    ))
    monkeypatch.setattr(csmoney_worker, "fetch_market_summary", lambda *_args: (
        (_ for _ in ()).throw(error)
    ))
    monkeypatch.setattr(csmoney_worker, "record_refresh_error", lambda *args: actions.append(args))
    monkeypatch.setattr(csmoney_worker, "defer_refresh_job", lambda *args, **kwargs: actions.append((args, kwargs)))
    monkeypatch.setattr(csmoney_worker, "complete_refresh_job", lambda _id: pytest.fail("Failed job completed"))
    with caplog.at_level(logging.INFO):
        if page is None:
            assert csmoney_worker.process_one(page)
        else:
            with pytest.raises(CsMoneyRequestError):
                csmoney_worker.process_one(page)
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert f"source=wiki_market_summary result={expected}" in caplog.text
    assert "SECRET" not in caplog.text
    assert "SECRET" not in str(actions)
    assert actions[0][1].endswith(expected)
    assert actions[1][1] == {"seconds": 60}
