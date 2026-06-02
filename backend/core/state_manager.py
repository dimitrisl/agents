import logging
import uuid
from typing import Any, Dict

logger = logging.getLogger("DnDAssistant.StateManager")

# Field definitions for consistent access
CHARACTER_FIELDS = [
    "char_id",
    "char_name",
    "char_class",
    "subclass",
    "char_level",
    "race",
    "gender",
    "background",
    "alignment",
    "backstory",
    "armor_class",
    "hp_max",
    "speed",
    "proficiency_bonus",
    "stats",
    "saving_throws",
    "skills",
    "skill_proficiencies",
    "skill_expertise",
    "weapons",
    "equipment",
    "features_traits",
    "spells",
    "prepared_spells",
    "spell_slots",
    "concentrating_on",
    "spell_ability",
    "spell_save_dc",
    "spell_attack_bonus",
    "hit_dice",
    "passive_perception",
    "personality_traits",
    "ideals",
    "bonds",
    "flaws",
    "char_portrait",
    "dnd_edition",
    "advancements",
    "weapon_masteries",
    "playstyle_guide",
    "active_campaign",
    "saving_throw_values",
    "initiative_modifier",
    "languages",
    "tool_proficiencies",
    "hp_current",
    "hit_dice_used",
    "conditions",
]


def get_default_character() -> Dict[str, Any]:
    """Returns a fresh character dictionary with default values."""
    return {
        "char_id": str(uuid.uuid4())[:8],
        "char_name": "New Hero",
        "char_class": "Paladin",
        "subclass": "Oath of Devotion",
        "char_level": 5,
        "race": "Human",
        "gender": "Male",
        "dnd_edition": "2014 Edition",
        "background": "Soldier",
        "alignment": "Lawful Good",
        "backstory": "A valiant paladin who swore an oath of devotion to protect the innocent.",
        "armor_class": 18,
        "hp_max": 44,
        "hp_current": 44,
        "hit_dice_used": 0,
        "conditions": [],
        "speed": 30,
        "proficiency_bonus": 3,
        "stats": {"STR": 18, "DEX": 12, "CON": 15, "INT": 10, "WIS": 14, "CHA": 16},
        "saving_throws": ["WIS", "CHA"],
        "skills": {"Athletics": 7, "Intimidation": 6, "Persuasion": 6},
        "skill_proficiencies": ["Athletics", "Intimidation", "Persuasion"],
        "weapons": [
            {"name": "Longsword", "attack_bonus": "+7", "damage": "1d8+4 slashing"}
        ],
        "equipment": [
            {"name": "Chain mail", "equipped": True},
            {"name": "Shield", "equipped": True},
        ],
        "features_traits": [
            {
                "name": "Divine Smite",
                "description": "Expend a spell slot to deal radiant damage.",
            }
        ],
        "spells": {"level_1": ["Bless", "Cure Wounds"], "level_2": ["Find Steed"]},
        "prepared_spells": ["Bless", "Cure Wounds", "Find Steed"],
        "spell_slots": {
            "level_1": {"max": 4, "used": 0},
            "level_2": {"max": 2, "used": 0},
        },
        "concentrating_on": None,
        "spell_ability": "CHA",
        "spell_save_dc": 14,
        "spell_attack_bonus": "+6",
        "hit_dice": "5d10",
        "passive_perception": 12,
        "personality_traits": "I'm always polite and respectful.",
        "ideals": "Responsibility. I do what I must and obey just authority.",
        "bonds": "I'll never forget the crushing defeat my company suffered.",
        "flaws": "I have little respect for anyone who is not a proven warrior.",
        "saving_throw_values": {},
        "skill_expertise": [],
        "advancements": [],
        "weapon_masteries": [],
        "playstyle_guide": "",
        "initiative_modifier": 0,
        "languages": ["Common"],
        "tool_proficiencies": [],
    }


def _set_val(obj: Any, key: str, val: Any):
    """Universal setter for dict or session_state."""
    import streamlit as st

    if isinstance(obj, dict) or obj == st.session_state:
        obj[key] = val
    else:
        setattr(obj, key, val)


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Universal getter for dict or session_state."""
    import streamlit as st

    if isinstance(obj, dict) or obj == st.session_state:
        return obj.get(key, default)
    return getattr(obj, key, default)


def init_session_state(state: Any, force: bool = False):
    """Initializes session state using the universal setters."""
    # App UI state
    if force or not _get_val(state, "character_active"):
        _set_val(state, "character_active", False)
    if force or not _get_val(state, "player_view"):
        _set_val(state, "player_view", "sheet")

    # Character data
    if force or not _get_val(state, "char_name"):
        defaults = get_default_character()
        for k, v in defaults.items():
            _set_val(state, k, v)

    extra_fields = {
        "roll_history": [],
        "combat_active": False,
        "needs_validation": False,
        "dnd_edition": "2014 Edition",
        "dnd_edition_toggle": False,
        "temp_forged_char": None,
        "edit_mode": False,
        "validation_result": None,
        "active_roll": None,
        "last_saved_char": None,
        # DM Workspace state
        "party": [],
        "active_campaign_name": None,
        "campaign_notes": "",
        "campaign_party_files": [],
        "session_prep_result": None,
        "encounter_result": None,
        "npc_result": None,
        "riddle_result": None,
        "initiative_order": [],
        "active_turn_index": 0,
    }
    for k, v in extra_fields.items():
        if force or _get_val(state, k) is None:
            _set_val(state, k, v)


def get_character_dict(state: Any) -> Dict[str, Any]:
    """Extracts character data into a clean dictionary."""
    char_data = {}
    for field in CHARACTER_FIELDS:
        val = _get_val(state, field)

        # Cleanup equipment/features if they are strings or models
        if field == "equipment" and isinstance(val, list):
            val = [
                {"name": item, "equipped": False}
                if isinstance(item, str)
                else (item.model_dump() if hasattr(item, "model_dump") else item)
                for item in val
            ]

        char_data[field] = val
    return char_data


def update_session_from_dict(state: Any, data: Dict[str, Any]):
    """Updates state from a dictionary with robust schema defaults."""
    if not data:
        return

    _set_val(state, "character_active", True)

    from backend.core.schemas import CharacterSchema
    from pydantic_core import PydanticUndefined

    for field in CHARACTER_FIELDS:
        if field in data:
            _set_val(state, field, data[field])
        else:
            # Derive the correct default from the Pydantic schema definition
            schema_field = CharacterSchema.model_fields.get(field)
            default = None
            if schema_field is not None:
                # 1. Check for simple default
                if schema_field.default is not PydanticUndefined:
                    default = schema_field.default
                # 2. Check for default_factory
                elif schema_field.default_factory is not None:
                    try:
                        default = schema_field.default_factory()
                    except Exception:
                        default = None

            # 3. Hardcoded fallbacks for critical structures if still None
            if default is None:
                if field == "stats":
                    default = {
                        "STR": 10,
                        "DEX": 10,
                        "CON": 10,
                        "INT": 10,
                        "WIS": 10,
                        "CHA": 10,
                    }
                elif field in [
                    "skills",
                    "spells",
                    "saving_throw_values",
                    "spell_slots",
                ]:
                    default = {}
                elif field in [
                    "equipment",
                    "features_traits",
                    "weapons",
                    "saving_throws",
                    "skill_proficiencies",
                    "skill_expertise",
                    "advancements",
                    "weapon_masteries",
                    "prepared_spells",
                ]:
                    default = []

            _set_val(state, field, default)

    if "dnd_edition" in data:
        _set_val(state, "dnd_edition_toggle", "2024" in str(data["dnd_edition"]))

    # Final vitals sync
    hp_max = _get_val(state, "hp_max") or 10
    if _get_val(state, "hp_current") is None:
        _set_val(state, "hp_current", hp_max)
    if _get_val(state, "conditions") is None:
        _set_val(state, "conditions", [])
    if _get_val(state, "hit_dice_used") is None:
        _set_val(state, "hit_dice_used", 0)
