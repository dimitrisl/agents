from unittest.mock import MagicMock
from backend.core.state_manager import (
    get_default_character,
    init_session_state,
    get_character_dict,
    update_session_from_dict,
    CHARACTER_FIELDS,
)


def test_get_default_character():
    char = get_default_character()
    assert isinstance(char, dict)
    assert "char_id" in char
    assert char["char_name"] == "New Hero"
    assert len(char["stats"]) == 6


def test_init_session_state_fresh():
    state = MagicMock()
    # Mocking that attributes don't exist
    state.character_active = None
    state.player_view = None
    state.char_name = None

    # Simple mock for get/set logic if state doesn't have the attribute
    state_dict = {}

    def mock_getattr(name, default=None):
        return state_dict.get(name, default)

    def mock_setattr(name, value):
        state_dict[name] = value
        setattr(state, name, value)

    # We need to bypass the MagicMock behavior for getattr to use our helper
    # Actually state_manager uses isinstance(obj, dict) or getattr
    # Let's just use a dict as state to test the dict branch
    state_dict = {}
    init_session_state(state_dict)

    assert state_dict["character_active"] is False
    assert state_dict["char_name"] == "New Hero"
    assert state_dict["stats"]["STR"] == 18
    assert state_dict["dnd_edition"] == "2014 Edition"
    assert state_dict["dnd_edition_toggle"] is False


def test_get_character_dict():
    state = {field: "value_" + field for field in CHARACTER_FIELDS}
    # Special handling for equipment in state_manager
    state["equipment"] = [{"name": "Sword", "equipped": True}]

    char_dict = get_character_dict(state)
    assert char_dict["char_name"] == "value_char_name"
    assert char_dict["equipment"][0]["name"] == "Sword"


def test_update_session_from_dict():
    state = {}
    data = {
        "char_name": "Updated Name",
        "stats": {"STR": 20, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    }
    update_session_from_dict(state, data)

    assert state["char_name"] == "Updated Name"
    assert state["stats"]["STR"] == 20
    assert state["character_active"] is True
    # Verify defaults come from Pydantic schema (NOT hardcoded 0)
    assert state["hp_max"] == 10  # CharacterSchema default is 10
    assert state["armor_class"] == 10  # CharacterSchema default is 10
    assert state["speed"] == 30  # CharacterSchema default is 30
    assert state["proficiency_bonus"] == 2  # CharacterSchema default is 2
    assert state["backstory"] == ""

    # Verify dnd_edition_toggle updates correctly
    state2 = {}
    data2 = {"dnd_edition": "2024 Revision (5.5e)"}
    update_session_from_dict(state2, data2)
    assert state2["dnd_edition_toggle"] is True

    state3 = {}
    data3 = {"dnd_edition": "2014 Edition"}
    update_session_from_dict(state3, data3)
    assert state3["dnd_edition_toggle"] is False


def test_init_session_state_force():
    state = {"char_name": "Existing Hero"}
    init_session_state(state, force=True)
    assert state["char_name"] == "New Hero"
