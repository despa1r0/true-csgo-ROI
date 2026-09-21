from backend.app.main import app
from backend.app.routers.csgomarket import router


CSGOMARKET_PATHS = {
    "/api/skins/{skin_id}/market/csgomarket",
    "/api/skins/{skin_id}/market/csgomarket/listings",
    "/api/variants/{variant_id}/market/csgomarket",
}


def test_csgomarket_public_routes_remain_unique_and_compatible():
    paths = app.openapi()["paths"]

    assert CSGOMARKET_PATHS <= paths.keys()
    for path in CSGOMARKET_PATHS:
        assert list(paths[path]) == ["get"]
        assert sum(route.path == path for route in router.routes) == 1

    parameters = {
        parameter["name"]: parameter
        for parameter in paths[
            "/api/skins/{skin_id}/market/csgomarket/listings"
        ]["get"]["parameters"]
    }
    assert parameters["sort_by"]["schema"]["default"] == "lowest_price"
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert {"has_stickers", "has_charm"} <= parameters.keys()
