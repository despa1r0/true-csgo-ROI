from backend.app.main import app
from backend.app.routers.csfloat import router


CSFLOAT_PATHS = {
    "/api/skins/{skin_id}/market/csfloat",
    "/api/skins/{skin_id}/market/csfloat/listings",
    "/api/variants/{variant_id}/market/csfloat",
    "/api/listings/{listing_id}/market/csfloat/quick-sell",
}


def test_csfloat_public_routes_remain_unique_and_compatible():
    paths = app.openapi()["paths"]

    assert CSFLOAT_PATHS <= paths.keys()
    for path in CSFLOAT_PATHS:
        assert list(paths[path]) == ["get"]
        assert sum(route.path == path for route in router.routes) == 1

    parameters = {
        parameter["name"]: parameter
        for parameter in paths[
            "/api/skins/{skin_id}/market/csfloat/listings"
        ]["get"]["parameters"]
    }
    assert parameters["sort_by"]["schema"]["default"] == "best_deal"
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert {"has_stickers", "has_charm"} <= parameters.keys()
