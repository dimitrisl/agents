import logging
from backend.core.ai_client import generate_ai_response, generate_ai_json
from backend.services.rules_service import (
    get_static_class_features,
)
from backend.core.prompts import (
    CHARACTER_FORGE_PROMPT,
    PLAYSTYLE_GUIDE_PROMPT,
    LEVEL_UP_ANALYSIS_PROMPT,
)
from backend.core.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    BACKGROUNDS_2014,
    SPECIES_2024,
    CLASSES_2024,
    BACKGROUNDS_2024,
    GENDERS,
)

from backend.core.schemas import CharacterSchema, LevelUpAnalysisSchema
from backend.services.mechanics_service import sync_character_stats
from backend.repositories.rules_repository import RulesRepository

logger = logging.getLogger("DnDAssistant.ForgeService")
_rules_repo = RulesRepository()


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

        # Synchronize derived stats (HP, AC, Proficiency, etc.)
        class_data = _rules_repo.get_class_progression(
            result.get("char_class"), edition
        )
        result = sync_character_stats(result, class_data)

        try:
            return CharacterSchema(**result).model_dump()
        except Exception as e:
            logger.warning(
                f"Forged character failed validation: {e}. Returning raw result."
            )
            return result
    return None


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


def analyze_level_up(char_data: dict, user_choices: dict = None) -> dict:
    """Uses AI to determine changes, incorporating any manual user choices."""
    current_level = char_data.get("char_level", 1)
    target_level = current_level + 1
    edition = char_data.get("dnd_edition", EDITION_2014)

    choice_context = ""
    if user_choices:
        choice_context = (
            "\nUser has already made the following manual choices for this level up:\n"
        )
        for k, v in user_choices.items():
            choice_context += f"- {k}: {v}\n"

    prompt = LEVEL_UP_ANALYSIS_PROMPT.format(
        edition=edition,
        current_level=current_level,
        target_level=target_level,
        char_class=char_data.get("char_class"),
        subclass=char_data.get("subclass", "None"),
        race=char_data.get("race"),
        stats=char_data.get("stats"),
    )
    if choice_context:
        prompt += choice_context
        prompt += "\nPlease fill in all OTHER automatic class features and spell slots, ignoring the choices already made above unless they trigger additional features."
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


def process_character_update(
    current_char: dict, stat_updates: dict = None, equipment_deltas: dict = None
) -> dict:
    """
    Processes character updates (stats and equipment) and returns synchronized character data.
    All calculations and data manipulation happen here, in the backend.
    """
    updated_char = current_char.copy()

    # 1. Apply Stat Updates & Level
    if stat_updates:
        for k, v in stat_updates.items():
            if k == "char_level":
                updated_char["char_level"] = v
            elif k in updated_char.get("stats", {}):
                updated_char["stats"][k] = v

    # 2. Apply Equipment Deltas
    if equipment_deltas:
        current_list = updated_char.get("equipment", [])

        # Apply edits
        for idx_str, changes in equipment_deltas.get("edited_rows", {}).items():
            import logging

            logging.getLogger("DnDAssistant").info(
                f"APPLYING EDITS FOR ROW {idx_str}: {changes}"
            )
            idx = int(idx_str)
            if idx < len(current_list):
                mapping = {
                    "Item": "name",
                    "Equipped": "equipped",
                    "Attuned": "attuned",
                    "AC": "ac_bonus",
                    "Mod 1": "mod1",
                    "Val 1": "val1",
                    "Mod 2": "mod2",
                    "Val 2": "val2",
                }
                for ui_key, val in changes.items():
                    backend_key = mapping.get(ui_key)
                    if backend_key:
                        current_list[idx][backend_key] = val

        # Apply additions
        for row in equipment_deltas.get("added_rows", []):
            current_list.append(
                {
                    "name": row.get("Item", "New Item"),
                    "equipped": row.get("Equipped", False),
                    "attuned": row.get("Attuned", False),
                    "ac_bonus": row.get("AC", 0),
                    "mod1": row.get("Mod 1", "None"),
                    "val1": row.get("Val 1", 0),
                    "mod2": row.get("Mod 2", "None"),
                    "val2": row.get("Val 2", 0),
                }
            )

        # Apply deletions
        deleted_indices = sorted(equipment_deltas.get("deleted_rows", []), reverse=True)
        for idx in deleted_indices:
            if idx < len(current_list):
                current_list.pop(idx)

        updated_char["equipment"] = current_list

    # 3. Synchronize derived stats
    class_data = _rules_repo.get_class_progression(
        updated_char.get("char_class"), updated_char.get("dnd_edition")
    )
    return sync_character_stats(updated_char, class_data)
