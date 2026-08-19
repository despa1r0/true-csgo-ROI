from backend.app.seed_catalog import base_skin_name, prepare_catalog


def source_item(**overrides):
    item = {
        "id": "skin-1_2",
        "skin_id": "skin-1",
        "name": "AK-47 | Redline (Field-Tested)",
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "description": "A test skin",
        "weapon": {"id": "weapon_ak47", "name": "AK-47"},
        "category": {"id": "rifles", "name": "Rifles"},
        "pattern": {"id": "redline", "name": "Redline"},
        "rarity": {"id": "classified", "name": "Classified", "color": "#d32ce6"},
        "wear": {"id": "wear_2", "name": "Field-Tested"},
        "min_float": 0.10,
        "max_float": 0.70,
        "paint_index": "282",
        "stattrak": False,
        "souvenir": False,
        "image": "https://example.test/redline.png",
    }
    item.update(overrides)
    return item


def test_removes_variant_prefix_and_wear_from_base_name():
    item = source_item(name="StatTrak™ AK-47 | Redline (Field-Tested)")

    assert base_skin_name(item) == "AK-47 | Redline"


def test_groups_source_variants_under_one_skin():
    normal = source_item()
    stattrak = source_item(
        id="skin-1_st_2",
        name="StatTrak™ AK-47 | Redline (Field-Tested)",
        market_hash_name="StatTrak™ AK-47 | Redline (Field-Tested)",
        stattrak=True,
    )

    skins, variants = prepare_catalog([normal, stattrak])

    assert len(skins) == 1
    assert skins[0]["name"] == "AK-47 | Redline"
    assert skins[0]["has_stattrak"] is True
    assert len(variants) == 2
