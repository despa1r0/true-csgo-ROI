from backend.app.main import app
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
