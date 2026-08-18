from backend.app.catalog import find_skins


def test_finds_redline_variants_without_external_request():
    results = find_skins("redline")

    assert len(results) == 4
    assert all("Redline" in item for item in results)
