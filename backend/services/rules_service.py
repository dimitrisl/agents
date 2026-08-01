import functools
import json
import logging
import re

import streamlit as st

from backend.core.ai_client import generate_ai_json, generate_ai_response
from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.prompts import (
    PDF_PARSING_STEP1_PROMPT,
    PDF_PARSING_STEP2_PROMPT,
    RULE_COMPARISON_PROMPT,
    RULES_ORACLE_PROMPT,
)
from backend.core.schemas import CharacterSchema
from backend.repositories.rules_repository import RulesRepository
from backend.utils.api_client import fetch_feat_from_api

logger = logging.getLogger("DnDAssistant.RulesService")


@functools.lru_cache(maxsize=1)
def _get_rules_repo():
    return RulesRepository()


@st.cache_data(show_spinner=False)
def query_rules(query: str, edition: str = EDITION_2014) -> str:
    """Uses AI to answer questions about D&D rules."""
    prompt = RULES_ORACLE_PROMPT.format(
        edition=edition,
        query=query,
    )
    return generate_ai_response(prompt)


@st.cache_data(show_spinner=False)
def compare_rules(query: str) -> str:
    """Uses AI to compare 2014 and 2024 rules."""
    prompt = RULE_COMPARISON_PROMPT.format(query=query)
    return generate_ai_response(prompt)


def autofix_character_build(char_data: dict) -> dict:
    """Validates character build against edition rules deterministically, applies corrections, and resynchronizes mechanics."""
    from backend.services.stats_service import sync_character_stats
    from backend.services.validation_service import deterministic_validate_build

    # 1. Deterministic Validation & Corrections
    corrected_char = deterministic_validate_build(char_data)

    # We create a dummy validation result to keep compatibility with any frontend code expecting it
    validation = {"is_valid": True, "issues": [], "suggestions": [], "corrections": {}}

    edition = corrected_char.get("dnd_edition", EDITION_2014)
    # Check if character contains 2024 indicators (masteries, origin feats, etc.)
    if (
        "2024" in str(edition)
        or corrected_char.get("weapon_masteries")
        or any("origin feat" in str(f).lower() for f in corrected_char.get("features_traits", []))
    ):
        edition = "2024 Edition"
        corrected_char["dnd_edition"] = edition

    char_class = corrected_char.get("char_class", "Fighter")
    level = corrected_char.get("char_level", 1)

    # Edition 2024 Rule: Subclasses are gained exclusively at Level 3
    if "2024" in edition and level < 3:
        corrected_char["subclass"] = ""

    # Re-sync derived stats using mechanics engine for the specific edition
    class_data = _get_rules_repo().get_class_progression(char_class, edition)
    synced_char = sync_character_stats(corrected_char, class_data)

    try:
        validated = CharacterSchema.model_validate(synced_char, strict=False)
        return {"validation_result": validation, "character": validated.model_dump()}
    except Exception as e:
        logger.warning(f"Autofix validation failed: {e}")
        return {"validation_result": validation, "character": synced_char}


def parse_character_from_text(sheet_text: str, edition: str = EDITION_2014) -> dict:
    """
    Parses raw text extracted from a D&D Character Sheet PDF into the app's JSON structure.
    Uses a 2-step chained process for maximum precision.
    """
    if (
        "2024" in sheet_text
        or "mastery" in sheet_text.lower()
        or "origin feat" in sheet_text.lower()
    ):
        edition = "2024 Edition"

    logger.info(f"Starting Chained Character Parsing (Edition: {edition}, Step 1: Core Stats)...")

    # STEP 1: Core Statistics & Identity
    step1_prompt = PDF_PARSING_STEP1_PROMPT.format(
        edition=edition,
        sheet_text=sheet_text,
    )
    core_data = generate_ai_json(step1_prompt)
    if not core_data:
        logger.error("Step 1 of chained parsing failed.")
        return None

    logger.info(f"Step 1 Complete (Name: {core_data.get('char_name')}). Starting Step 2...")

    # STEP 2: Combat, Equipment, Spells & Lore
    step2_prompt = PDF_PARSING_STEP2_PROMPT.format(
        edition=edition,
        core_json=json.dumps(core_data),
        sheet_text=sheet_text,
    )
    combat_data = generate_ai_json(step2_prompt)

    # Merge the results
    final_raw = {**core_data, **(combat_data or {})}
    final_raw["dnd_edition"] = edition

    # Synchronize derived stats according to edition rules
    from backend.services.stats_service import sync_character_stats

    class_data = _get_rules_repo().get_class_progression(
        final_raw.get("char_class", "Fighter"), edition
    )
    final_raw = sync_character_stats(final_raw, class_data)

    try:
        # Validate against schema to ensure data integrity
        validated = CharacterSchema(**final_raw)
        logger.info("Chained parsing successfully completed and validated.")
        return validated.model_dump()
    except Exception as e:
        logger.warning(
            f"Parsed data failed validation: {e}. Falling back to clean schema representation."
        )
        # Attempt to construct a safe fallback dictionary
        fallback_data = {
            "char_name": str(final_raw.get("char_name") or "New Hero"),
            "char_class": str(final_raw.get("char_class") or "Paladin"),
            "race": str(final_raw.get("race") or "Human"),
            "background": str(final_raw.get("background") or "Acolyte"),
        }
        # Copy basic scalar/identifying fields safely
        basic_fields = [
            "char_id",
            "gender",
            "char_level",
            "subclass",
            "alignment",
            "backstory",
            "armor_class",
            "hp_max",
            "speed",
            "proficiency_bonus",
            "personality_traits",
            "ideals",
            "bonds",
            "flaws",
            "languages",
            "tool_proficiencies",
            "dnd_edition",
        ]
        for key in basic_fields:
            if key in final_raw:
                fallback_data[key] = final_raw[key]

        try:
            validated = CharacterSchema.model_validate(fallback_data, strict=False)
            return validated.model_dump()
        except Exception as fallback_err:
            logger.error(
                f"Fallback validation failed: {fallback_err}. Returning default character."
            )
            from backend.core.state_manager import get_default_character

            default_char = get_default_character()
            # Overlay simple fields
            for k in [
                "char_name",
                "char_class",
                "subclass",
                "char_level",
                "race",
                "background",
            ]:
                if final_raw.get(k):
                    default_char[k] = final_raw[k]
            return default_char


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

    # Normalize text to lower case and collapse whitespace for robust parsing
    norm_desc = re.sub(r"\s+", " ", description).strip().lower()

    # Remove basic punctuation that might break simple matches
    norm_desc = re.sub(r"[.,;:]", "", norm_desc)

    # 1. HP bonus (Tough)
    if "hit point maximum increases by an amount equal to twice your level" in norm_desc:
        mechanics["hp_bonus_per_level"] = 2
    elif "hit point maximum increases by 1 for every level" in norm_desc:
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
        if re.search(rf"increase your {full_name} score by 1", norm_desc):
            mechanics["stat_bonus"][short_name] = 1

    # 3. Stat choice bonuses (e.g. "Strength or Dexterity")
    choice_match = re.search(
        r"increase your (strength|dexterity|constitution|intelligence|wisdom|charisma) or (strength|dexterity|constitution|intelligence|wisdom|charisma) score by 1",
        norm_desc,
    )
    if choice_match:
        mechanics["has_stat_choice"] = True
        mechanics["stat_choice_options"] = [
            stat_map[choice_match.group(1)],
            stat_map[choice_match.group(2)],
        ]

    return mechanics


def get_static_class_features(class_name: str, level: int, edition: str = EDITION_2014) -> list:
    """Fetches features from the knowledge base if available."""
    return _get_rules_repo().get_features_at_level(class_name, level, edition)


def analyze_feat(feat_name: str, edition: str = EDITION_2014) -> dict:
    """Uses local static DB first, then API, then regex parsing for mechanical extraction."""
    # 1. Try local static DB first
    try:
        local_feats = _get_rules_repo().get_all_feats(edition)
        local_match = next(
            (f for f in local_feats if f.get("name", "").lower() == feat_name.lower()),
            None,
        )
        if local_match:
            return {
                "description": local_match.get("description", ""),
                "source": f"Local Database ({'2024' if edition == EDITION_2024 else '2014'})",
                "stat_bonus": local_match.get(
                    "stat_bonus",
                    {"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0},
                ),
                "hp_bonus_per_level": local_match.get("hp_bonus_per_level", 0),
                "has_stat_choice": local_match.get("has_stat_choice", False),
                "stat_choice_options": local_match.get("stat_choice_options", []),
            }
    except Exception as e:
        logger.warning(f"Failed to lookup feat {feat_name} locally: {e}")

    # 2. Try API second
    api_data = fetch_feat_from_api(feat_name)

    if api_data:
        description = api_data["description"]
        # Use REGEX (no AI) to extract structured data from official text
        mechanics = regex_parse_feat_attributes(description)
        return {"description": description, "source": api_data["source"], **mechanics}

    # No AI Fallback as per deterministic validation rule
    # If a homebrew feat is not in the database, it must be added to the database.
    return {
        "description": "Unknown Feat. Please add it to the local rules database.",
        "source": "Unknown",
        "stat_bonus": {"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0},
        "hp_bonus_per_level": 0,
        "has_stat_choice": False,
        "stat_choice_options": [],
    }
