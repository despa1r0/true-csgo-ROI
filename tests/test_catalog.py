import pytest

from backend.app.catalog import _search_tokens
from backend.app.main import app
from backend.app.seed_catalog import (
    _is_marketplace_catalog_item,
    _specific_item_type,
    base_skin_name,
    prepare_catalog,
    prepare_non_skin_catalog,
    prepare_skin_collections,
)


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


def test_search_tokens_ignore_item_name_separators():
    assert _search_tokens("  AWP   | As  ") == ["AWP", "As"]


def test_flattens_grouped_skin_collections():
    grouped = [
        {
            "id": "skin-1",
            "collections": [
                {
                    "id": "collection-set-phoenix",
                    "name": "The Phoenix Collection",
                    "image": "https://example.test/phoenix.png",
                }
            ],
        }
    ]

    assert prepare_skin_collections(grouped) == [
        {
            "skin_id": "skin-1",
            "collection_id": "collection-set-phoenix",
            "collection_name": "The Phoenix Collection",
            "image_url": "https://example.test/phoenix.png",
        }
    ]


def test_normalizes_searchable_non_skin_items_and_market_variants():
    items, variants = prepare_non_skin_catalog(
        {
            "sticker": [
                {
                    "id": "sticker-1",
                    "name": "Sticker | Test",
                    "market_hash_name": "Sticker | Test",
                    "rarity": {
                        "id": "rarity_rare",
                        "name": "High Grade",
                        "color": "#4b69ff",
                    },
                    "image": "https://example.test/sticker.png",
                }
            ],
            "collectible": [
                {
                    "id": "collectible-1",
                    "name": "Series 1 Genuine Pin",
                    "type": "Pin",
                    "market_hash_name": "Series 1 Genuine Pin",
                }
            ],
        }
    )

    assert [item["item_type"] for item in items] == ["sticker", "pin"]
    assert variants[0]["id"] == "catalog-variant-sticker-1"
    assert variants[0]["market_hash_name"] == "Sticker | Test"
    assert variants[0]["wear_name"] is None
    assert variants[1]["skin_id"] == "collectible-1"


def test_excludes_non_marketplace_rewards_predictions_and_unknown_sources():
    items, variants = prepare_non_skin_catalog(
        {
            "sticker": [
                {
                    "id": "market-sticker",
                    "name": "Sticker | Live",
                    "market_hash_name": "Sticker | Live",
                },
                {
                    "id": "inventory-only-sticker",
                    "name": "Sticker Preview",
                    "market_hash_name": None,
                },
            ],
            "collectible": [
                {
                    "id": "operation-coin",
                    "name": "Operation Test Coin",
                    "type": "Operation Coin",
                    "market_hash_name": "Operation Test Coin",
                },
                {
                    "id": "genuine-pin",
                    "name": "Genuine Test Pin",
                    "type": "Pin",
                    "genuine": True,
                    "market_hash_name": "Genuine Test Pin",
                },
                {
                    "id": "market-pin",
                    "name": "Test Pin",
                    "type": "Pin",
                    "genuine": False,
                    "market_hash_name": "Test Pin",
                },
            ],
            "future_source": [
                {
                    "id": "predicted-item",
                    "name": "Predicted Item",
                    "market_hash_name": "Predicted Item",
                }
            ],
        }
    )

    assert [item["id"] for item in items] == ["market-sticker", "market-pin"]
    assert [variant["market_hash_name"] for variant in variants] == [
        "Sticker | Live",
        "Test Pin",
    ]
    assert len(items) == len(variants)


def test_marketplace_catalog_marker_requires_explicit_market_hash_name():
    assert _is_marketplace_catalog_item(
        "agent",
        {
            "name": "Special Agent Ava",
            "market_hash_name": "Special Agent Ava | FBI",
        },
    )
    assert not _is_marketplace_catalog_item(
        "agent", {"name": "Unreleased Agent", "market_hash_name": "  "}
    )
    assert not _is_marketplace_catalog_item(
        "collectible",
        {
            "name": "Gold Prediction Trophy",
            "type": "Pick'Em Trophy",
            "market_hash_name": "Gold Prediction Trophy",
        },
    )


@pytest.mark.parametrize(
    ("source_type", "name", "expected_item_type"),
    [
        ("container", "Kilowatt Case", "case"),
        ("sticker", "Sticker | Test", "sticker"),
        ("charm", "Charm | Test", "charm"),
        ("agent", "Special Agent Test | FBI", "agent"),
        ("music_kit", "Music Kit | Test", "music_kit"),
        ("patch", "Patch | Test", "patch"),
        ("graffiti", "Sealed Graffiti | Test", "graffiti"),
        ("sticker_slab", "Sticker Slab | Test", "sticker_slab"),
        (
            "souvenir_charm",
            "Souvenir Charm | Test Highlight",
            "souvenir_charm",
        ),
    ],
)
def test_keeps_supported_exact_name_marketplace_item_types(
    source_type, name, expected_item_type
):
    items, variants = prepare_non_skin_catalog(
        {
            source_type: [
                {
                    "id": f"{source_type}-1",
                    "name": name,
                    "market_hash_name": name,
                }
            ]
        }
    )

    assert [item["item_type"] for item in items] == [expected_item_type]
    assert [variant["market_hash_name"] for variant in variants] == [name]


def test_splits_container_types_for_catalogue_filtering():
    assert _specific_item_type("container", {"name": "Kilowatt Case"}) == "case"
    assert (
        _specific_item_type("container", {"name": "Austin 2025 Souvenir Package"})
        == "souvenir_package"
    )
    assert (
        _specific_item_type("container", {"name": "Paris 2023 Legends Sticker Capsule"})
        == "capsule"
    )


def test_complete_catalog_search_exposes_item_type_filter():
    parameters = {
        parameter["name"]
        for parameter in app.openapi()["paths"]["/api/items/search"]["get"][
            "parameters"
        ]
    }

    assert {"q", "item_type", "weapon", "rarity", "collection", "limit"} <= parameters
