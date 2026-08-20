import pytest
from pydantic import ValidationError

from backend.core.schemas import EncounterSchema
from backend.services.dm_service import create_manual_npc
from server.routers.dm_router import EncounterRequest


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


def test_encounter_request_takes_the_real_party():
    payload = EncounterRequest(party_size=6, avg_level=12, difficulty="Deadly")

    assert payload.party_size == 6
    assert payload.avg_level == 12
    assert payload.difficulty == "Deadly"


@pytest.mark.parametrize(
    "field,value",
    [
        ("party_size", 0),
        ("avg_level", 0),
        ("avg_level", 25),
        ("difficulty", "Impossible"),
    ],
)
def test_encounter_request_rejects_an_unbalanceable_party(field, value):
    """An encounter for zero heroes reads as a real one — it must not be generated."""
    with pytest.raises(ValidationError):
        EncounterRequest(**{field: value})


def test_encounter_keeps_a_monster_that_came_back_without_dex():
    """A null DEX used to void the whole encounter, and initiative rolled on None."""
    encounter = EncounterSchema(
        encounter_text="Ghouls stir in the crypt.",
        monsters=[
            {
                "name": "Ghoul",
                "hp": 22,
                "ac": 12,
                "dex": None,
                "quantity": None,
                "statblock_summary": "...",
            }
        ],
    )

    assert encounter.monsters[0].dex == 10
    assert encounter.monsters[0].quantity == 1


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
