import logging
import json
from backend.ai_client import generate_ai_response, generate_ai_json
from backend.prompts import (
    RULES_ORACLE_PROMPT,
    BUILD_VALIDATION_PROMPT,
    PDF_PARSING_STEP1_PROMPT,
    PDF_PARSING_STEP2_PROMPT,
)
from backend.constants import EDITION_2014

from backend.schemas import CharacterSchema, BuildValidationSchema

logger = logging.getLogger("DnDAssistant.RulesService")


def query_rules(query: str, edition: str = EDITION_2014) -> str:
    """Uses AI to answer questions about D&D rules."""
    prompt = RULES_ORACLE_PROMPT.format(
        edition=edition,
        query=query,
    )
    return generate_ai_response(prompt)


def validate_character_build(char_data: dict) -> dict:
    """Uses AI to validate a character's build."""
    edition = char_data.get("dnd_edition", EDITION_2014)
    # Ensure char_data matches schema before sending
    validated_char = CharacterSchema(**char_data)

    prompt = BUILD_VALIDATION_PROMPT.format(
        char_json=validated_char.model_dump_json(indent=2),
        edition=edition,
    )
    result = generate_ai_json(prompt)
    if result:
        return BuildValidationSchema(**result).model_dump()
    return {"is_valid": True, "issues": [], "suggestions": []}


def parse_character_from_text(sheet_text: str, edition: str = EDITION_2014) -> dict:
    """
    Parses raw text extracted from a D&D Character Sheet PDF into the app's JSON structure.
    Uses a 2-step chained process for maximum precision.
    """
    logger.info("Starting Chained Character Parsing (Step 1: Core Stats)...")

    # STEP 1: Core Statistics & Identity
    step1_prompt = PDF_PARSING_STEP1_PROMPT.format(
        edition=edition,
        sheet_text=sheet_text,
    )
    core_data = generate_ai_json(step1_prompt)
    if not core_data:
        logger.error("Step 1 of chained parsing failed.")
        return None

    logger.info(
        f"Step 1 Complete (Name: {core_data.get('char_name')}). Starting Step 2..."
    )

    # STEP 2: Combat, Equipment, Spells & Lore
    step2_prompt = PDF_PARSING_STEP2_PROMPT.format(
        edition=edition,
        core_json=json.dumps(core_data),
        sheet_text=sheet_text,
    )
    combat_data = generate_ai_json(step2_prompt)

    # Merge the results
    final_raw = {**core_data, **(combat_data or {})}

    try:
        # Validate against schema to ensure data integrity
        validated = CharacterSchema(**final_raw)
        logger.info("Chained parsing successfully completed and validated.")
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"Parsed data failed validation: {e}. Returning raw data.")
        return final_raw
