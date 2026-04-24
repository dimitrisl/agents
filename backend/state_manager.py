import logging
import uuid

logger = logging.getLogger("DnDAssistant.StateManager")


def init_session_state(session_state):
    """Initializes default Streamlit session state variables."""
    if "char_name" not in session_state:
        logger.debug("Initializing default session state variables.")
        session_state.char_id = str(uuid.uuid4())[:8]
        session_state.char_name = "Eldred the Valiant"
        session_state.char_class = "Paladin"
        session_state.char_level = 5
        session_state.race = "Human"
        session_state.background = "Soldier"
        session_state.alignment = "Lawful Good"
        session_state.backstory = (
            "A valiant paladin who swore an oath of devotion to protect the innocent."
        )
        session_state.armor_class = 18
        session_state.hp_max = 44
        session_state.speed = 30
        session_state.proficiency_bonus = 3
        session_state.stats = {
            "STR": 18,
            "DEX": 12,
            "CON": 15,
            "INT": 10,
            "WIS": 14,
            "CHA": 16,
        }
        session_state.saving_throws = ["WIS", "CHA"]
        session_state.skills = {"Athletics": 7, "Intimidation": 6, "Persuasion": 6}
        session_state.weapons = [
            {"name": "Longsword", "attack_bonus": "+7", "damage": "1d8+4 slashing"}
        ]
        session_state.equipment = ["Chain mail", "Shield", "Explorer's pack"]
        session_state.features_traits = [
            {
                "name": "Divine Smite",
                "description": "Expend a spell slot to deal radiant damage.",
            }
        ]
        session_state.spells = {
            "level_1": ["Bless", "Cure Wounds", "Shield of Faith"],
            "level_2": ["Find Steed", "Lesser Restoration"],
        }

        session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get an AI recommendation based on your current stats!"
        session_state.encounter_result = ""
        session_state.campaign_notes = "The Party enters the lower levels. You need to prepare encounters for the Goblin warren."
        session_state.npc_result = ""


def get_character_dict(session_state) -> dict:
    """Extracts character data from the Streamlit session state into a dictionary."""
    return {
        "char_id": getattr(session_state, "char_id", str(uuid.uuid4())[:8]),
        "char_name": session_state.char_name,
        "char_class": session_state.char_class,
        "char_level": session_state.char_level,
        "race": session_state.race,
        "background": session_state.background,
        "alignment": session_state.alignment,
        "backstory": session_state.backstory,
        "armor_class": session_state.armor_class,
        "hp_max": session_state.hp_max,
        "speed": session_state.speed,
        "proficiency_bonus": session_state.proficiency_bonus,
        "stats": session_state.stats,
        "saving_throws": session_state.saving_throws,
        "skills": session_state.skills,
        "weapons": session_state.weapons,
        "equipment": session_state.equipment,
        "features_traits": session_state.features_traits,
        "spells": session_state.spells,
    }


def update_session_from_dict(session_state, data: dict):
    """Updates Streamlit session state variables from a character dictionary."""
    session_state.char_id = data.get("char_id", str(uuid.uuid4())[:8])
    session_state.char_name = data.get("char_name", "Unknown")
    session_state.char_class = data.get("char_class", "Commoner")
    session_state.char_level = data.get("char_level", 1)
    session_state.race = data.get("race", "Unknown")
    session_state.background = data.get("background", "Unknown")
    session_state.alignment = data.get("alignment", "Unknown")
    session_state.backstory = data.get("backstory", "")
    session_state.armor_class = data.get("armor_class", 10)
    session_state.hp_max = data.get("hp_max", 10)
    session_state.speed = data.get("speed", 30)
    session_state.proficiency_bonus = data.get("proficiency_bonus", 2)
    session_state.saving_throws = data.get("saving_throws", [])
    session_state.skills = data.get("skills", {})
    session_state.weapons = data.get("weapons", [])
    session_state.equipment = data.get("equipment", [])
    session_state.features_traits = data.get("features_traits", [])
    session_state.spells = data.get("spells", {})
    if "stats" in data:
        session_state.stats = data["stats"]
