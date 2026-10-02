from backend.app.main import app
from backend.app.routers import csmoney
from backend.app.routers.csmoney import router


CSMONEY_PATHS = {
    "/api/skins/{skin_id}/market/csmoney",
    "/api/skins/{skin_id}/market/csmoney/listings",
    "/api/variants/{variant_id}/market/csmoney",
    "/api/variants/{variant_id}/market/csmoney/price-history",
}


def test_csmoney_public_routes_remain_unique_and_compatible():
    paths = app.openapi()["paths"]

    assert CSMONEY_PATHS <= paths.keys()
    for path in CSMONEY_PATHS:
        assert list(paths[path]) == ["get"]
        assert sum(route.path == path for route in router.routes) == 1

    parameters = {
        parameter["name"]: parameter
        for parameter in paths[
            "/api/skins/{skin_id}/market/csmoney/listings"
        ]["get"]["parameters"]
    }
    assert parameters["sort_by"]["schema"]["default"] == "lowest_price"
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert {"has_stickers", "has_charm"} <= parameters.keys()


def test_csmoney_routes_preserve_explicit_provider_states(monkeypatch):
    aggregate = {
        "listings": [], "error": None, "status": "partial", "source_state": "partial",
        "variant_states": [
            {"variant_id": "normal", "source_state": "summary_only", "status": "partial", "error": None},
            {"variant_id": "stattrak", "source_state": "provider_unavailable", "status": "unavailable", "error": "timeout"},
        ],
    }
    details = {"variant_id": "normal", "listings": [], "source_state": "summary_only"}
    monkeypatch.setattr(csmoney, "get_csmoney_skin_listings", lambda *_args, **_kwargs: aggregate)
    monkeypatch.setattr(csmoney, "get_csmoney_variant_details", lambda _id: details)
    assert csmoney.skin_csmoney_listings(
        "skin", variant="any", min_float=None, max_float=None,
        min_price_cents=None, max_price_cents=None, limit=30,
    ) == aggregate
    assert csmoney.variant_csmoney_details("normal") == details
