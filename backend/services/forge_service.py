import functools
import logging
import uuid

from backend.core.ai_client import generate_ai_json, generate_ai_response
from backend.core.constants import (
    EDITION_2014,
    GENDERS,
)
from backend.core.prompts import (
    CHARACTER_FORGE_PROMPT,
    MANUAL_CHARACTER_ENRICH_PROMPT,
    PLAYSTYLE_GUIDE_PROMPT,
)
from backend.core.schemas import CharacterSchema
from backend.core.state_manager import get_default_character
from backend.repositories.rules_repository import RulesRepository
from backend.services.mechanics_service import sync_character_stats
from backend.services.rules_service import (
    autofix_character_build,
)
from backend.services.validation_service import deterministic_validate_build

logger = logging.getLogger("DnDAssistant.ForgeService")


@functools.lru_cache(maxsize=1)
def _get_rules_repo():
    return RulesRepository()


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
    custom_preferences: str = None,
    auto_spells: bool = True,
    auto_feats: bool = True,
) -> dict:
    """Generates a full D&D character using AI."""
    repo = _get_rules_repo()
    current_races = repo.get_available_races(edition)
    current_classes = repo.get_available_classes(edition)
    current_backgrounds = repo.get_available_backgrounds(edition)

    race_prompt = (
        forge_race
        if forge_race != "AI Choice"
        else f"Choose one from: {', '.join([r['name'] for r in current_races])}"
    )
    class_prompt = (
        forge_class
        if forge_class != "AI Choice"
        else f"Choose one from: {', '.join(current_classes)}"
    )
    bg_prompt = (
        forge_background
        if forge_background != "AI Choice"
        else f"Choose one from: {', '.join([b['name'] for b in current_backgrounds])}"
    )
    gender_prompt = gender if gender != "AI Choice" else f"Choose from: {', '.join(GENDERS)}"

    name_instruction = (
        f"The character's name MUST be: {name}"
        if name != "AI Choice"
        else "Assign them a creative and thematic name."
    )

    if stats_mode == "standard":
        stats_instruction = "You MUST use the Standard Array (15, 14, 13, 12, 10, 8) for their base ability scores, distributed optimally for their class/race."
    else:
        stats_instruction = "You must assign them a balanced, high-quality array of 6 ability scores (equivalent to rolling 4d6 drop lowest)."

    pref_instructions = []
    if custom_preferences and custom_preferences.strip():
        pref_instructions.append(
            f"USER CUSTOM BUILD PREFERENCES (FEATS, SPELLS, ASIs):\n{custom_preferences}"
        )
    if not auto_spells:
        pref_instructions.append(
            "DO NOT auto-select spells for this character. Leave 'spells' as an empty dictionary {} and 'prepared_spells' as an empty list []."
        )
    if not auto_feats:
        pref_instructions.append(
            "DO NOT auto-select Feats or ASIs for this character. Leave 'advancements' as an empty list [] and do NOT add Feat traits."
        )

    custom_pref_inst = "\n".join(pref_instructions) if pref_instructions else ""

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
        custom_preferences_instruction=custom_pref_inst,
    )

    result = generate_ai_json(prompt)
    if not result:
        logger.warning("AI JSON generation returned None. Generating default fallback character.")
        result = get_default_character()
        result.update(
            {
                "char_name": name if name != "AI Choice" else "Forged Hero",
                "gender": gender if gender != "AI Choice" else "Male",
                "char_class": forge_class if forge_class != "AI Choice" else "",
                "subclass": subclass if subclass and subclass != "AI Choice" else None,
                "char_level": target_level,
                "race": forge_race if forge_race != "AI Choice" else "Human",
                "background": forge_background if forge_background != "AI Choice" else "Soldier",
                "alignment": alignment if alignment != "AI Choice" else "True Neutral",
                "concept": concept or "",
                "dnd_edition": edition,
            }
        )

    result["dnd_edition"] = edition
    if not result.get("char_id"):
        result["char_id"] = str(uuid.uuid4())[:8]

    if not auto_spells:
        result["spells"] = {}
        result["prepared_spells"] = []
    if not auto_feats:
        result["advancements"] = []
        if "features_traits" in result and isinstance(result["features_traits"], list):
            result["features_traits"] = [
                f
                for f in result["features_traits"]
                if not (isinstance(f, dict) and f.get("name", "").lower().startswith("feat:"))
            ]

    # Synchronize derived stats (HP, AC, Proficiency, etc.)
    class_data = _get_rules_repo().get_class_progression(result.get("char_class"), edition)
    result = sync_character_stats(result, class_data)

    # D&D Rules Autofix & Deep Validation
    try:
        autofix_result = autofix_character_build(result)
        result = autofix_result.get("character", result)
    except Exception as e:
        logger.error(f"Rule autofix failed during AI forge: {e}")

    # Mandatory Schema & Build Validation
    try:
        validated = CharacterSchema.model_validate(result, strict=False)
        return validated.model_dump()
    except Exception as e:
        logger.warning(
            f"Forged character failed initial validation: {e}. Coercing schema defaults."
        )

        fallback = get_default_character()
        for k, v in result.items():
            if v is not None:
                try:
                    fallback[k] = v
                except Exception:
                    pass
        try:
            return CharacterSchema.model_validate(fallback, strict=False).model_dump()
        except Exception as e2:
            logger.error(f"Fallback validation failed: {e2}. Returning clean default character.")
            return CharacterSchema.model_validate(
                get_default_character(), strict=False
            ).model_dump()


def forge_character_manual(
    target_level: int,
    race: str,
    char_class: str,
    background: str,
    subclass: str,
    alignment: str,
    gender: str,
    name: str,
    base_stats: dict,
    skill_proficiencies: list,
    saving_throws: list,
    spell_ability: str,
    concept: str,
    edition: str = EDITION_2014,
    custom_preferences: str = None,
    auto_spells: bool = True,
    auto_feats: bool = True,
) -> dict:
    """Enriches and builds a manual character based on user selections and AI helper."""
    pref_instructions = []
    if custom_preferences and custom_preferences.strip():
        pref_instructions.append(
            f"USER CUSTOM BUILD PREFERENCES (FEATS, SPELLS, ASIs):\n{custom_preferences}"
        )
    if not auto_spells:
        pref_instructions.append(
            "DO NOT auto-select spells for this character. Leave 'spells' as an empty dictionary {} and 'prepared_spells' as an empty list []."
        )
    if not auto_feats:
        pref_instructions.append(
            "DO NOT auto-select Feats or ASIs for this character. Leave 'advancements' as an empty list [] and do NOT add Feat traits."
        )

    custom_pref_inst = "\n".join(pref_instructions) if pref_instructions else ""

    prompt = MANUAL_CHARACTER_ENRICH_PROMPT.format(
        edition=edition,
        name=name,
        gender=gender,
        race=race,
        class_name=char_class,
        subclass=subclass if subclass else "None",
        target_level=target_level,
        background=background,
        alignment=alignment,
        base_stats=base_stats,
        skill_proficiencies=skill_proficiencies,
        saving_throws=saving_throws,
        spell_ability=spell_ability,
        concept=concept,
        custom_preferences_instruction=custom_pref_inst,
    )
    result = generate_ai_json(prompt)
    if not result:
        result = {}

    # Merge manual choices
    result["char_name"] = name
    result["gender"] = gender
    result["char_class"] = char_class
    result["subclass"] = subclass
    result["char_level"] = target_level
    result["race"] = race
    result["background"] = background
    result["alignment"] = alignment
    result["stats"] = base_stats
    result["saving_throws"] = saving_throws
    result["skill_proficiencies"] = skill_proficiencies
    result["spell_ability"] = spell_ability
    result["dnd_edition"] = edition

    result["char_id"] = str(uuid.uuid4())[:8]

    if not auto_spells:
        result["spells"] = {}
        result["prepared_spells"] = []
    if not auto_feats:
        result["advancements"] = []
        if "features_traits" in result and isinstance(result["features_traits"], list):
            result["features_traits"] = [
                f
                for f in result["features_traits"]
                if not (isinstance(f, dict) and f.get("name", "").lower().startswith("feat:"))
            ]

    # Synchronize derived stats (HP, AC, Proficiency, etc.)
    class_data = _get_rules_repo().get_class_progression(char_class, edition)
    result = sync_character_stats(result, class_data)

    # D&D Rules Autofix & Deep Validation
    try:
        autofix_result = autofix_character_build(result)
        result = autofix_result.get("character", result)
    except Exception as e:
        logger.error(f"Rule autofix failed during manual forge: {e}")

    # Mandatory Schema & Build Validation
    try:
        validated = CharacterSchema.model_validate(result, strict=False)
        return validated.model_dump()
    except Exception as e:
        logger.warning(
            f"Manual character failed initial validation: {e}. Coercing schema defaults."
        )

        fallback = get_default_character()
        fallback.update({k: v for k, v in result.items() if v is not None})
        return CharacterSchema.model_validate(fallback, strict=False).model_dump()


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
    """Determines level up changes deterministically without an LLM call."""
    import math

    from backend.repositories.rules_repository import RulesRepository
    from backend.services.progression_service import get_level_up_vitals

    current_level = char_data.get("char_level", 1)
    target_level = current_level + 1
    edition = char_data.get("dnd_edition", EDITION_2014)
    char_class = char_data.get("char_class", "Fighter")

    rules_repo = RulesRepository()
    static_features = rules_repo.get_features_at_level(char_class, target_level, edition)

    try:
        vitals = get_level_up_vitals(
            char_class=char_class,
            current_level=current_level,
            con_score=char_data.get("stats", {}).get("CON", 10),
            edition=edition,
            features=char_data.get("features_traits", []),
        )
        hp_increase = vitals.get("average_hp_gain", 0)
    except Exception:
        hp_increase = 6

    updated_pb = math.ceil(target_level / 4) + 1

    choices = []

    # 1. Subclass
    current_subclass = char_data.get("subclass")
    if not current_subclass:
        subclasses = rules_repo.get_subclasses(char_class, edition)
        if subclasses:
            subclass_level = 3
            if edition == EDITION_2014:
                if char_class in ["Cleric", "Sorcerer", "Warlock"]:
                    subclass_level = 1
                elif char_class in ["Wizard", "Druid"]:
                    subclass_level = 2

            if target_level == subclass_level:
                choices.append(
                    {
                        "type": "subclass",
                        "label": f"Choose your {char_class} Subclass",
                        "options": subclasses,
                        "ai_recommendation": f"Any of these official subclasses will work perfectly for your {char_class}.",
                    }
                )

    # 2. ASI/Feat
    if target_level in [4, 8, 12, 16, 19]:
        choices.append(
            {
                "type": "feat",
                "label": "Choose a Feat or Ability Score Improvement",
                "options": ["+2 to one Stat", "+1 to two Stats"]
                + [f["name"] for f in rules_repo.get_all_feats(edition)],
                "ai_recommendation": "A standard ASI/Feat level. Pick what suits your build best.",
            }
        )

    # 3. Spells (Simplified generic spell choice for casters)
    spellcasters = [
        "Bard",
        "Cleric",
        "Druid",
        "Paladin",
        "Ranger",
        "Sorcerer",
        "Warlock",
        "Wizard",
        "Artificer",
    ]
    if char_class in spellcasters:
        spells = sorted([s["name"] for s in rules_repo.get_all_spells(edition)])

        # Bard Magical Secrets overrides
        if char_class == "Bard" and target_level in [10, 14, 18]:
            choices.append(
                {
                    "type": "spell_secret_1",
                    "label": "Magical Secrets: Choose 1st Spell (Any Class)",
                    "options": spells,
                    "ai_recommendation": "Magical Secrets allows you to pick from ANY class list.",
                }
            )
            choices.append(
                {
                    "type": "spell_secret_2",
                    "label": "Magical Secrets: Choose 2nd Spell (Any Class)",
                    "options": spells,
                    "ai_recommendation": "Magical Secrets allows you to pick from ANY class list.",
                }
            )
        elif char_class == "Bard" and target_level == 6 and current_subclass == "College of Lore":
            choices.append(
                {
                    "type": "spell_secret_1",
                    "label": "Additional Magical Secrets: Choose 1st Spell (Any Class)",
                    "options": spells,
                    "ai_recommendation": "Lore Bards get Magical Secrets early!",
                }
            )
            choices.append(
                {
                    "type": "spell_secret_2",
                    "label": "Additional Magical Secrets: Choose 2nd Spell (Any Class)",
                    "options": spells,
                    "ai_recommendation": "Lore Bards get Magical Secrets early!",
                }
            )
        else:
            choices.append(
                {
                    "type": "spell",
                    "label": f"Learn/Prepare a {char_class} Spell",
                    "options": spells,
                    "ai_recommendation": "Explore the official spell list.",
                }
            )

    # 4. Expertise
    skills = [
        "Acrobatics",
        "Animal Handling",
        "Arcana",
        "Athletics",
        "Deception",
        "History",
        "Insight",
        "Intimidation",
        "Investigation",
        "Medicine",
        "Nature",
        "Perception",
        "Performance",
        "Persuasion",
        "Religion",
        "Sleight of Hand",
        "Stealth",
        "Survival",
    ]
    if char_class == "Bard" and target_level in [3, 10]:
        choices.append(
            {
                "type": "expertise_1",
                "label": "Choose 1st skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick a skill you are already proficient in.",
            }
        )
        choices.append(
            {
                "type": "expertise_2",
                "label": "Choose 2nd skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick another skill for Expertise.",
            }
        )
    elif char_class == "Rogue" and target_level in [1, 6]:
        choices.append(
            {
                "type": "expertise_1",
                "label": "Choose 1st skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick a skill you are already proficient in.",
            }
        )
        choices.append(
            {
                "type": "expertise_2",
                "label": "Choose 2nd skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick another skill for Expertise.",
            }
        )

    return {
        "automatic_changes": static_features,
        "hp_increase": hp_increase,
        "new_total_hp": char_data.get("hp_max", 0) + hp_increase,
        "choices_required": choices,
        "updated_proficiency_bonus": updated_pb,
        "updated_spell_slots": {},
        "new_spells_known": [],
        "new_features": static_features,
    }


def process_character_update(
    current_char: dict,
    stat_updates: dict = None,
    equipment_deltas: dict = None,
    weapon_deltas: dict = None,
    homebrew_content: list[dict] | None = None,
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
            logger.info(f"APPLYING EDITS FOR ROW {idx_str}: {changes}")
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

    updated_char, _ = deterministic_validate_build(updated_char)

    # 3. Synchronize derived stats
    class_data = _get_rules_repo().get_class_progression(
        updated_char.get("char_class"), updated_char.get("dnd_edition")
    )
    return sync_character_stats(updated_char, class_data, weapon_deltas, homebrew_content)
