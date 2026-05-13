import logging
from backend.ai_client import generate_ai_response, generate_ai_json
from backend.services.rules_service import (
    get_static_class_features,
)
from backend.prompts import (
    CHARACTER_FORGE_PROMPT,
    BUILD_SUGGESTION_PROMPT,
    PLAYSTYLE_GUIDE_PROMPT,
    LEVEL_UP_ANALYSIS_PROMPT,
)
from backend.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    BACKGROUNDS_2014,
    SPECIES_2024,
    CLASSES_2024,
    BACKGROUNDS_2024,
    GENDERS,
)

from backend.schemas import CharacterSchema, LevelUpAnalysisSchema

logger = logging.getLogger("DnDAssistant.ForgeService")


def forge_character(
    target_level: int,
    forge_race: str,
    forge_class: str,
    forge_background: str,
    concept: str,
    name: str = "AI Choice",
    gender: str = "AI Choice",
    stats_mode: str = "standard",
    alignment: str = "AI Choice",
    edition: str = EDITION_2014,
    subclass: str = None,
) -> dict:
    """Generates a full D&D character using AI."""
    if edition == EDITION_2014:
        current_races = RACES_2014
        current_classes = CLASSES_2014
        current_backgrounds = BACKGROUNDS_2014
    else:
        current_races = SPECIES_2024
        current_classes = CLASSES_2024
        current_backgrounds = BACKGROUNDS_2024

    race_prompt = (
        forge_race
        if forge_race != "AI Choice"
        else f"Choose one from: {', '.join(current_races)}"
    )
    class_prompt = (
        forge_class
        if forge_class != "AI Choice"
        else f"Choose one from: {', '.join(current_classes)}"
    )
    bg_prompt = (
        forge_background
        if forge_background != "AI Choice"
        else f"Choose one from: {', '.join(current_backgrounds)}"
    )
    gender_prompt = (
        gender if gender != "AI Choice" else f"Choose from: {', '.join(GENDERS)}"
    )

    name_instruction = (
        f"The character's name MUST be: {name}"
        if name != "AI Choice"
        else "Assign them a creative and thematic name."
    )

    if stats_mode == "standard":
        stats_instruction = "You MUST use the Standard Array (15, 14, 13, 12, 10, 8) for their base ability scores, distributed optimally for their class/race."
    else:
        stats_instruction = "You must assign them a balanced, high-quality array of 6 ability scores (equivalent to rolling 4d6 drop lowest)."

    prompt = CHARACTER_FORGE_PROMPT.format(
        target_level=target_level,
        edition=edition,
        name_instruction=name_instruction,
        gender=gender_prompt,
        race=race_prompt,
        class_name=class_prompt,
        background=bg_prompt,
        concept=concept,
        subclass=subclass if subclass else "AI Choice",
        alignment=alignment,
        current_races=current_races,
        current_classes=current_classes,
        current_backgrounds=current_backgrounds,
        stats_instruction=stats_instruction,
    )

    result = generate_ai_json(prompt)
    if result:
        result["dnd_edition"] = edition
        # Ensure char_id is present
        if not result.get("char_id"):
            import uuid

            result["char_id"] = str(uuid.uuid4())[:8]

        try:
            return CharacterSchema(**result).model_dump()
        except Exception as e:
            logger.warning(
                f"Forged character failed validation: {e}. Returning raw result."
            )
            return result
    return None


def get_build_suggestion(
    char_level: int,
    char_class: str,
    char_name: str,
    stats: dict,
    edition: str = EDITION_2014,
) -> str:
    """Provides a short creative build or multiclass suggestion."""
    prompt = BUILD_SUGGESTION_PROMPT.format(
        char_level=char_level,
        char_class=char_class,
        edition=edition,
        char_name=char_name,
        str_val=stats.get("STR", 10),
        dex_val=stats.get("DEX", 10),
        con_val=stats.get("CON", 10),
        int_val=stats.get("INT", 10),
        wis_val=stats.get("WIS", 10),
        cha_val=stats.get("CHA", 10),
    )
    return generate_ai_response(prompt)


def generate_playstyle_guide(char_data: dict) -> str:
    """Generates a detailed strategic and roleplay guide for a character."""
    prompt = PLAYSTYLE_GUIDE_PROMPT.format(
        edition=char_data.get("dnd_edition", EDITION_2014),
        name=char_data.get("char_name", "Unknown"),
        class_name=char_data.get("char_class", "Unknown"),
        subclass=char_data.get("subclass", "N/A"),
        level=char_data.get("char_level", 1),
        race=char_data.get("race", "Unknown"),
        background=char_data.get("background", "Unknown"),
        stats=char_data.get("stats", {}),
        features=[f.get("name") for f in char_data.get("features_traits", [])],
    )
    return generate_ai_response(prompt)


def analyze_level_up(char_data: dict) -> dict:
    """Uses AI to determine what changes occur when leveling up."""
    current_level = char_data.get("char_level", 1)
    target_level = current_level + 1
    edition = char_data.get("dnd_edition", EDITION_2014)

    prompt = LEVEL_UP_ANALYSIS_PROMPT.format(
        edition=edition,
        current_level=current_level,
        target_level=target_level,
        char_class=char_data.get("char_class"),
        subclass=char_data.get("subclass", "None"),
        race=char_data.get("race"),
        stats=char_data.get("stats"),
    )
    static_features_readiness = False
    result = generate_ai_json(prompt)
    if result:
        if static_features_readiness:
            # MERGE: Check static knowledge base for features
            static_features = get_static_class_features(
                char_data.get("char_class"), target_level, edition
            )
            if static_features:
                logger.info(
                    f"Found {len(static_features)} static features for {char_data.get('char_class')} level {target_level}"
                )
                # Ensure static features are in the automatic_changes
                existing_names = [
                    f.get("name") for f in result.get("automatic_changes", [])
                ]
                for sf in static_features:
                    if sf.get("name") not in existing_names:
                        result.setdefault("automatic_changes", []).append(sf)
        try:
            return LevelUpAnalysisSchema(**result).model_dump()
        except Exception as e:
            logger.warning(
                f"Level up analysis failed validation: {e}. Returning raw result."
            )
            return result
    return None
