import pytest

from backend.app import csmoney_worker
from backend.app.marketplaces.csmoney import CsMoneyRequestError


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
        csmoney_worker.process_one(object())

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
