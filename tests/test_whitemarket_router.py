from backend.app.main import app
from backend.app.routers.whitemarket import router


WHITEMARKET_PATHS = {
    "/api/skins/{skin_id}/market/whitemarket",
    "/api/skins/{skin_id}/market/whitemarket/listings",
    "/api/variants/{variant_id}/market/whitemarket",
    "/api/variants/{variant_id}/market/whitemarket/listings",
    "/api/variants/{variant_id}/market/whitemarket/quick-sell",
}


def test_whitemarket_public_routes_remain_unique_and_compatible():
    paths = app.openapi()["paths"]

    assert WHITEMARKET_PATHS <= paths.keys()
    for path in WHITEMARKET_PATHS:
        assert list(paths[path]) == ["get"]
        assert sum(route.path == path for route in router.routes) == 1

    skin_parameters = {
        parameter["name"]: parameter
        for parameter in paths[
            "/api/skins/{skin_id}/market/whitemarket/listings"
        ]["get"]["parameters"]
    }
    variant_parameters = {
        parameter["name"]: parameter
        for parameter in paths[
            "/api/variants/{variant_id}/market/whitemarket/listings"
        ]["get"]["parameters"]
    }
    assert skin_parameters["sort_by"]["schema"]["default"] == "lowest_price"
    assert skin_parameters["limit"]["schema"]["maximum"] == 50
    assert {"has_stickers", "has_charm"} <= variant_parameters.keys()
