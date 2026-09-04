import asyncio

import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.main import FRONTEND_DIR, SPAStaticFiles


def _scope(path: str):
    return {"type": "http", "method": "GET", "path": path, "headers": []}


def test_client_side_calculator_route_returns_spa_entrypoint():
    files = SPAStaticFiles(directory=FRONTEND_DIR, html=True)

    response = asyncio.run(files.get_response("calculator", _scope("/calculator")))

    assert response.status_code == 200
    assert response.media_type == "text/html"


def test_unknown_api_route_stays_a_real_404():
    files = SPAStaticFiles(directory=FRONTEND_DIR, html=True)

    with pytest.raises(StarletteHTTPException) as error:
        asyncio.run(files.get_response("api/does-not-exist", _scope("/api/does-not-exist")))

    assert error.value.status_code == 404
