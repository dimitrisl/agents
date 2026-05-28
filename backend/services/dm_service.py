import logging
from backend.core.ai_client import generate_ai_response, generate_ai_json
from backend.core.prompts import (
    RANDOM_ENCOUNTER_PROMPT,
    RIDDLE_PROMPT,
    NPC_PROMPT,
    SESSION_PREP_PROMPT,
)
from backend.core.constants import EDITION_2014
from backend.core.schemas import EncounterSchema

logger = logging.getLogger("DnDAssistant.DMService")


def generate_random_encounter(
    party_size: int,
    avg_level: int,
    location: str,
    edition: str = EDITION_2014,
    difficulty: str = "Medium",
) -> dict:
    """Generates a flavorful random encounter."""
    prompt = RANDOM_ENCOUNTER_PROMPT.format(
        edition=edition,
        party_size=party_size,
        avg_level=avg_level,
        location=location,
        difficulty=difficulty,
    )
    result = generate_ai_json(prompt)
    if result:
        try:
            return EncounterSchema(**result).model_dump()
        except Exception as e:
            logger.warning(
                f"Encounter generation failed validation: {e}. Returning raw result."
            )
            return result
    return None


def generate_riddle(location: str, edition: str = EDITION_2014) -> str:
    """Generates a thematic riddle based on the environment."""
    prompt = RIDDLE_PROMPT.format(
        edition=edition,
        location=location,
    )
    return generate_ai_response(prompt)


def generate_npc(npc_concept: str, edition: str = EDITION_2014) -> str:
    """Creates a thematic NPC."""
    prompt = NPC_PROMPT.format(
        edition=edition,
        npc_concept=npc_concept,
    )
    return generate_ai_response(prompt)


def generate_session_prep(campaign_notes: str, party_info: str) -> str:
    """Generates plot hooks and session developments."""
    prompt = SESSION_PREP_PROMPT.format(
        campaign_notes=campaign_notes,
        party_info=party_info,
    )
    return generate_ai_response(prompt)


def create_manual_npc(
    name: str,
    role: str,
    race: str,
    ac: int,
    hp_max: int,
    speed: int,
    char_level: int,
    stats: dict,
    weapons: list = None,
    features_traits: list = None,
    backstory: str = "",
    dnd_edition: str = "2014 Edition",
) -> dict:
    """Builds and validates a manual NPC character dictionary."""
    import uuid
    from backend.core.schemas import CharacterSchema

    if not name or not name.strip():
        raise ValueError("NPC name cannot be empty.")

    new_char_id = str(uuid.uuid4())[:8]

    # Ensure stats are formatted correctly
    stats_clean = {
        "STR": int(stats.get("STR", 10)),
        "DEX": int(stats.get("DEX", 10)),
        "CON": int(stats.get("CON", 10)),
        "INT": int(stats.get("INT", 10)),
        "WIS": int(stats.get("WIS", 10)),
        "CHA": int(stats.get("CHA", 10)),
    }

    weapons_clean = []
    if weapons:
        for w in weapons:
            weapons_clean.append(
                {
                    "name": str(w.get("name") or "Unknown Weapon"),
                    "attack_bonus": str(w.get("attack_bonus") or "+0"),
                    "damage_dice": str(w.get("damage_dice") or "1d4"),
                    "damage_bonus": str(w.get("damage_bonus") or "+0"),
                    "is_custom": True,
                }
            )

    features_clean = []
    if features_traits:
        for ft in features_traits:
            features_clean.append(
                {
                    "name": str(ft.get("name") or "Feature"),
                    "description": str(ft.get("description") or ""),
                }
            )

    char_dict = {
        "char_id": new_char_id,
        "is_npc": True,
        "char_name": name.strip(),
        "char_class": role[:20] if role else "Monster",
        "race": race.strip() if race else "Unknown",
        "background": "Manual NPC",
        "dnd_edition": dnd_edition,
        "char_level": max(1, int(char_level)),
        "armor_class": max(0, int(ac)),
        "hp_max": max(1, int(hp_max)),
        "hp_current": max(1, int(hp_max)),
        "speed": max(0, int(speed)),
        "stats": stats_clean,
        "features_traits": features_clean,
        "weapons": weapons_clean,
        "backstory": backstory.strip(),
        "equipment": [],
        "languages": ["Common"],
        "tool_proficiencies": [],
    }

    # Validate against CharacterSchema
    validated = CharacterSchema.model_validate(char_dict, strict=False)
    return validated.model_dump()
