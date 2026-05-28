import pytest
from backend.services.dm_service import create_manual_npc


def test_create_manual_npc_valid():
    stats = {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8}
    weapons = [{"name": "Bite", "attack_bonus": "+4", "damage_dice": "1d6+2"}]
    features = [{"name": "Pack Tactics", "description": "Advantage if ally is nearby"}]

    npc = create_manual_npc(
        name="Wolf Boss",
        role="Beast",
        race="Wolf",
        ac=13,
        hp_max=30,
        speed=40,
        char_level=2,
        stats=stats,
        weapons=weapons,
        features_traits=features,
        backstory="A large scary wolf.",
        dnd_edition="2024 Revision",
    )

    assert npc["char_name"] == "Wolf Boss"
    assert npc["char_class"] == "Beast"
    assert npc["race"] == "Wolf"
    assert npc["armor_class"] == 13
    assert npc["hp_max"] == 30
    assert npc["hp_current"] == 30
    assert npc["speed"] == 40
    assert npc["char_level"] == 2
    assert npc["stats"]["STR"] == 15
    assert npc["stats"]["CHA"] == 8
    assert len(npc["weapons"]) == 1
    assert npc["weapons"][0]["name"] == "Bite"
    assert npc["weapons"][0]["attack_bonus"] == "+4"
    assert npc["weapons"][0]["is_custom"] is True
    assert len(npc["features_traits"]) == 1
    assert npc["features_traits"][0]["name"] == "Pack Tactics"
    assert npc["backstory"] == "A large scary wolf."
    assert npc["dnd_edition"] == "2024 Revision"
    assert npc["is_npc"] is True


def test_create_manual_npc_missing_name():
    stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
    with pytest.raises(ValueError, match="NPC name cannot be empty"):
        create_manual_npc(
            name="",
            role="Monster",
            race="Unknown",
            ac=10,
            hp_max=10,
            speed=30,
            char_level=1,
            stats=stats,
        )
