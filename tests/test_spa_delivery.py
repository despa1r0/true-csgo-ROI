import asyncio

import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.main import SPAStaticFiles, resolve_frontend_directory


def _scope(path: str):
    return {"type": "http", "method": "GET", "path": path, "headers": []}


@pytest.fixture
def react_dist(tmp_path):
    dist = tmp_path / "frontend-react" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<main>React SPA</main>", encoding="utf-8")
    return dist


def test_static_mode_resolves_only_react_dist(react_dist):
    assert (
        resolve_frontend_directory("static", project_dir=react_dist.parents[1])
        == react_dist
    )


def test_static_mode_fails_clearly_when_react_dist_is_missing(tmp_path):
    legacy_frontend = tmp_path / "frontend"
    legacy_frontend.mkdir()
    (legacy_frontend / "index.html").write_text("legacy", encoding="utf-8")

    with pytest.raises(RuntimeError, match="React production bundle is missing"):
        resolve_frontend_directory("static", project_dir=tmp_path)


def test_development_mode_does_not_require_a_bundle(tmp_path):
    assert resolve_frontend_directory("development", project_dir=tmp_path) is None


def test_client_side_calculator_route_returns_spa_entrypoint(react_dist):
    files = SPAStaticFiles(directory=react_dist, html=True)

    response = asyncio.run(files.get_response("calculator", _scope("/calculator")))

    assert response.status_code == 200
    assert response.media_type == "text/html"


def test_unknown_api_route_stays_a_real_404(react_dist):
    files = SPAStaticFiles(directory=react_dist, html=True)

    with pytest.raises(StarletteHTTPException) as error:
        asyncio.run(files.get_response("api/does-not-exist", _scope("/api/does-not-exist")))

    assert error.value.status_code == 404
