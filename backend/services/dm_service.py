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
    party_size: int, avg_level: int, location: str, edition: str = EDITION_2014
) -> dict:
    """Generates a flavorful random encounter."""
    prompt = RANDOM_ENCOUNTER_PROMPT.format(
        edition=edition,
        party_size=party_size,
        avg_level=avg_level,
        location=location,
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
