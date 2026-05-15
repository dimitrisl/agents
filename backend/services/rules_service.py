import logging
import json
import re
from backend.core.ai_client import generate_ai_response, generate_ai_json
from backend.core.prompts import (
    RULES_ORACLE_PROMPT,
    BUILD_VALIDATION_PROMPT,
    PDF_PARSING_STEP1_PROMPT,
    PDF_PARSING_STEP2_PROMPT,
    FEAT_ANALYSIS_PROMPT,
)
from backend.core.constants import EDITION_2014

from backend.core.schemas import CharacterSchema, BuildValidationSchema
from backend.repositories.rules_repository import RulesRepository
from backend.utils.api_client import fetch_feat_from_api

logger = logging.getLogger("DnDAssistant.RulesService")

_rules_repo = RulesRepository()


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


def regex_parse_feat_attributes(description: str) -> dict:
    """
    Parses mechanical bonuses from feat text using regex (no AI).
    Focuses on standard SRD patterns for HP and Stat boosts.
    """
    mechanics = {
        "stat_bonus": {"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0},
        "hp_bonus_per_level": 0,
        "has_stat_choice": False,
        "stat_choice_options": [],
    }

    # 1. HP bonus (Tough)
    if re.search(
        r"hit point maximum increases by an amount equal to twice your level",
        description,
        re.I,
    ):
        mechanics["hp_bonus_per_level"] = 2
    elif re.search(
        r"hit point maximum increases by 1 for every level", description, re.I
    ):
        mechanics["hp_bonus_per_level"] = 1

    # 2. Specific Stat bonuses (+1)
    stat_map = {
        "strength": "STR",
        "dexterity": "DEX",
        "constitution": "CON",
        "intelligence": "INT",
        "wisdom": "WIS",
        "charisma": "CHA",
    }
    for full_name, short_name in stat_map.items():
        if re.search(rf"Increase your {full_name} score by 1", description, re.I):
            mechanics["stat_bonus"][short_name] = 1

    # 3. Stat choice bonuses (e.g. "Strength or Dexterity")
    choice_match = re.search(
        r"Increase your (Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma) or (Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma) score by 1",
        description,
        re.I,
    )
    if choice_match:
        mechanics["has_stat_choice"] = True
        mechanics["stat_choice_options"] = [
            stat_map[choice_match.group(1).lower()],
            stat_map[choice_match.group(2).lower()],
        ]

    return mechanics


def get_static_class_features(
    class_name: str, level: int, edition: str = EDITION_2014
) -> list:
    """Fetches features from the knowledge base if available."""
    return _rules_repo.get_features_at_level(class_name, level, edition)


def analyze_feat(feat_name: str, edition: str = EDITION_2014) -> dict:
    """Uses API first, then regex parsing for mechanical extraction."""
    # Try API first
    api_data = fetch_feat_from_api(feat_name)

    if api_data:
        description = api_data["description"]
        # Use REGEX (no AI) to extract structured data from official text
        mechanics = regex_parse_feat_attributes(description)
        return {"description": description, "source": api_data["source"], **mechanics}

    # Full AI Fallback for Homebrew/Non-SRD (since it's not in the API)
    # We still use the AI here because if it's not in the official SRD,
    # we have no text to parse with regex!
    prompt = FEAT_ANALYSIS_PROMPT.format(
        feat_name=feat_name,
        edition=edition,
    )
    result = generate_ai_json(prompt)
    return result or {}
