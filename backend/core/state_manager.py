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
    """Universal setter for dict or object."""
    if isinstance(obj, dict):
        obj[key] = val
    else:
        setattr(obj, key, val)


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Universal getter for dict or object."""
    if isinstance(obj, dict):
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
    """Updates state from a dictionary."""
    if not data:
        return

    _set_val(state, "character_active", True)

    for field in CHARACTER_FIELDS:
        if field in data:
            _set_val(state, field, data[field])
        else:
            # Set defaults for missing fields to prevent bleed
            default = None
            if field == "stats":
                default = {
                    "STR": 10,
                    "DEX": 10,
                    "CON": 10,
                    "INT": 10,
                    "WIS": 10,
                    "CHA": 10,
                }
            elif field in ["skills", "spells", "saving_throw_values"]:
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
            elif field in [
                "char_name",
                "backstory",
                "personality_traits",
                "ideals",
                "bonds",
                "flaws",
                "playstyle_guide",
                "race",
                "gender",
                "background",
                "alignment",
                "subclass",
                "hit_dice",
                "spell_attack_bonus",
            ]:
                default = ""
            elif field in [
                "armor_class",
                "hp_max",
                "speed",
                "proficiency_bonus",
                "passive_perception",
                "initiative_modifier",
                "char_level",
                "spell_save_dc",
            ]:
                default = 0
            _set_val(state, field, default)

    if "dnd_edition" in data:
        _set_val(state, "dnd_edition_toggle", "2024" in str(data["dnd_edition"]))
