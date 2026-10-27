import functools
import logging
import random
import uuid

from backend.core.ai_client import generate_ai_json, generate_ai_response
from backend.core.constants import (
    EDITION_2014,
    GENDERS,
)
from backend.core.prompts import (
    CHARACTER_FORGE_PROMPT,
    LEVEL_UP_BUILD_RECOMMENDATIONS_PROMPT,
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
        stats_instruction = f"Assign the values from the Standard Array (15, 14, 13, 12, 10, 8) to the character's base ability scores. You MUST logically distribute these scores to best fit the primary ability scores of the {forge_class} class (e.g., highest to STR for Barbarian). DO NOT just assign them in descending order to STR, DEX, CON, INT, WIS, CHA."
    elif stats_mode == "point_buy":
        stats_instruction = f"Assign base ability scores using the standard Point Buy system (27 points total, stats between 8 and 15 before racial bonuses). You MUST logically distribute these scores to best fit the primary ability scores of the {forge_class} class."
    else:

        def roll_stat():
            rolls = [random.randint(1, 6) for _ in range(4)]
            rolls.remove(min(rolls))
            return sum(rolls)

        rolled_stats = sorted([roll_stat() for _ in range(6)], reverse=True)
        stats_instruction = f"Assign exactly these rolled scores: {rolled_stats} to the character's base ability scores. You MUST logically distribute these scores to best fit the primary ability scores of the {forge_class} class. DO NOT just assign them in descending order to STR, DEX, CON, INT, WIS, CHA."

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

    # Sanitize Hallucinations (Bug 5)
    result.pop("initiative_bonus", None)

    # Fix Custom Background (Bug 3 & 4)
    # Custom Background is now entirely handled by the AI prompt.
    if "custom" in str(result.get("background", "")).lower():
        pass

    result["dnd_edition"] = edition
    if not result.get("char_id"):
        result["char_id"] = str(uuid.uuid4())[:8]

    if not auto_spells:
        result["spells"] = {}
        result["prepared_spells"] = []
    else:
        # Flatten spells into prepared_spells for the UI
        spells_dict = result.get("spells", {})
        prepared = result.get("prepared_spells", [])
        if isinstance(spells_dict, dict):
            for lvl, spell_list in spells_dict.items():
                if isinstance(spell_list, list):
                    for spell_name in spell_list:
                        if spell_name not in prepared:
                            prepared.append(spell_name)
        result["prepared_spells"] = prepared
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
    chosen_spells: list = None,
    chosen_feats: list = None,
    chosen_equipment: list = None,
) -> dict:
    """Enriches and builds a manual character based on user selections and AI helper."""
    pref_instructions = []
    if custom_preferences and custom_preferences.strip():
        pref_instructions.append(
            f"USER CUSTOM BUILD PREFERENCES (FEATS, SPELLS, ASIs):\n{custom_preferences}"
        )
    if chosen_spells:
        pref_instructions.append(
            f"USER CHOSEN SPELLS (STRICTLY USE THESE): {', '.join(chosen_spells)}"
        )
    elif not auto_spells:
        pref_instructions.append(
            "DO NOT auto-select spells for this character. Leave 'spells' as an empty dictionary {} and 'prepared_spells' as an empty list []."
        )
    if chosen_feats:
        pref_instructions.append(
            f"USER CHOSEN FEATS (STRICTLY USE THESE): {', '.join(chosen_feats)}"
        )
    elif not auto_feats:
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
        logger.warning(
            "AI JSON generation returned None in manual forge. Generating default fallback character."
        )
        result = get_default_character()

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

    # Sanitize Hallucinations (Bug 5)
    result.pop("initiative_bonus", None)

    # Fix Custom Background (Bug 3 & 4)
    # Custom Background is now entirely handled by the AI prompt.
    if "custom" in str(result.get("background", "")).lower():
        pass

    # Add missing static class features (Bug 7)
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    all_static_features = []
    for lvl in range(1, target_level + 1):
        all_static_features.extend(repo.get_features_at_level(char_class, lvl, edition))

    existing_feat_names = {f.get("name", "").lower() for f in result.get("features_traits", [])}
    for feat in all_static_features:
        if feat.get("name", "").lower() not in existing_feat_names:
            result.setdefault("features_traits", []).append(feat)

    if chosen_spells is not None:
        all_rules_spells = {s["name"].lower(): s for s in repo.get_all_spells(edition)}
        spells_dict: dict[str, list[str]] = {}
        prepared: list[str] = []
        for s_name in chosen_spells:
            s_data = all_rules_spells.get(s_name.lower())
            lvl = s_data.get("level", 0) if s_data else 0
            lvl_key = "cantrips" if lvl == 0 else f"level_{lvl}"
            clean_name = s_data["name"] if s_data else s_name
            spells_dict.setdefault(lvl_key, []).append(clean_name)
            prepared.append(clean_name)
        result["spells"] = spells_dict
        result["prepared_spells"] = prepared
    elif not auto_spells:
        result["spells"] = {}
        result["prepared_spells"] = []
    else:
        # Flatten spells into prepared_spells for the UI
        spells_dict = result.get("spells", {})
        prepared = result.get("prepared_spells", [])
        if isinstance(spells_dict, dict):
            for lvl, spell_list in spells_dict.items():
                if isinstance(spell_list, list):
                    for spell_name in spell_list:
                        if spell_name not in prepared:
                            prepared.append(spell_name)
        result["prepared_spells"] = prepared

    if chosen_feats is not None:
        all_rules_feats = {f["name"].lower(): f for f in repo.get_all_feats(edition)}
        advancements = []
        feat_traits = []
        for f_name in chosen_feats:
            f_data = all_rules_feats.get(f_name.lower())
            name = f_data["name"] if f_data else f_name
            desc = f_data.get("description", "") if f_data else ""
            category = f_data.get("category", "General Feats") if f_data else "General Feats"
            adv_level = 1 if "origin" in category.lower() or "2024" in edition else 4
            advancements.append(
                {
                    "level": adv_level,
                    "type": "Feat",
                    "name": name,
                    "description": desc[:200],
                }
            )
            feat_traits.append(
                {
                    "name": f"Feat: {name}",
                    "description": desc,
                    "source": "Feat",
                }
            )
        result["advancements"] = advancements
        existing_traits = [
            f
            for f in result.get("features_traits", [])
            if not (isinstance(f, dict) and f.get("name", "").lower().startswith("feat:"))
        ]
        existing_traits.extend(feat_traits)
        result["features_traits"] = existing_traits
    elif not auto_feats:
        result["advancements"] = []
        if "features_traits" in result and isinstance(result["features_traits"], list):
            result["features_traits"] = [
                f
                for f in result["features_traits"]
                if not (isinstance(f, dict) and f.get("name", "").lower().startswith("feat:"))
            ]

    if chosen_equipment is not None:
        result["equipment"] = [{"name": it, "equipped": True} for it in chosen_equipment]

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
    # Extract flattened spell names
    raw_spells = char_data.get("spells", {})
    spell_names = []
    if isinstance(raw_spells, dict):
        for lvl_spells in raw_spells.values():
            if isinstance(lvl_spells, list):
                for s in lvl_spells:
                    spell_names.append(s.get("name") if isinstance(s, dict) else str(s))
    elif isinstance(raw_spells, list):
        for s in raw_spells:
            spell_names.append(s.get("name") if isinstance(s, dict) else str(s))

    weapon_names = [
        w.get("name") if isinstance(w, dict) else str(w) for w in char_data.get("weapons", [])
    ]

    prompt = PLAYSTYLE_GUIDE_PROMPT.format(
        edition=char_data.get("dnd_edition", EDITION_2014),
        name=char_data.get("char_name", "Unknown"),
        class_name=char_data.get("char_class", "Unknown"),
        subclass=char_data.get("subclass", "N/A"),
        level=char_data.get("char_level", 1),
        race=char_data.get("race", "Unknown"),
        background=char_data.get("background", "Unknown"),
        stats=char_data.get("stats", {}),
        weapons=weapon_names or "Standard weapons",
        spells=spell_names or "No spells recorded",
        features=[
            f.get("name") if isinstance(f, dict) else str(f)
            for f in char_data.get("features_traits", [])
        ],
    )
    return generate_ai_response(prompt)


def _has_asi(target_class: str, target_class_level: int) -> bool:
    cls_lower = (target_class or "").lower()
    if cls_lower == "fighter":
        return target_class_level in [4, 6, 8, 12, 14, 16, 19]
    elif cls_lower == "rogue":
        return target_class_level in [4, 8, 10, 12, 16, 19]
    return target_class_level in [4, 8, 12, 16, 19]


def _needs_subclass(
    target_class: str,
    target_class_level: int,
    current_subclass: str | None,
    edition: str,
) -> bool:
    if current_subclass and current_subclass not in ["N/A", "None", ""]:
        return False
    subclass_level = 3
    if edition == EDITION_2014:
        cls_title = (target_class or "").title()
        if cls_title in ["Cleric", "Sorcerer", "Warlock"]:
            subclass_level = 1
        elif cls_title in ["Wizard", "Druid"]:
            subclass_level = 2
    return target_class_level >= subclass_level


def _get_fallback_level_up_recommendations(
    char_data: dict,
    target_class: str,
    target_class_level: int,
    target_total_level: int,
    edition: str,
    needs_subclass: bool,
    available_subclasses: list[str],
    has_asi: bool,
    max_spell_level: int,
    known_spells: list[str] | None = None,
) -> list[dict]:
    """Generates 3 distinct deterministic archetype builds if the LLM is unavailable."""
    primary_stats = {
        "Barbarian": "STR",
        "Bard": "CHA",
        "Cleric": "WIS",
        "Druid": "WIS",
        "Fighter": "STR",
        "Monk": "DEX",
        "Paladin": "STR",
        "Ranger": "DEX",
        "Rogue": "DEX",
        "Sorcerer": "CHA",
        "Warlock": "CHA",
        "Wizard": "INT",
        "Artificer": "INT",
    }
    prim_stat = primary_stats.get(target_class, "STR")
    known_set = {k.strip().lower() for k in (known_spells or [])}

    repo = _get_rules_repo()
    all_class_spells = [
        s
        for s in repo.get_all_spells(edition)
        if target_class.lower() in [c.lower() for c in s.get("classes", [])]
        and s.get("name", "").strip().lower() not in known_set
    ]

    def _get_top_spells(school_keywords: list[str], fallback_list: list[str]) -> list[str]:
        if max_spell_level <= 0:
            return []
        # Filter for unlearned spells of highest available level (current tier)
        tier_spells = [
            s["name"]
            for s in all_class_spells
            if s.get("level", 0) == max_spell_level
            and (
                not school_keywords
                or any(kw in (s.get("school") or "").lower() for kw in school_keywords)
            )
        ]
        if not tier_spells:
            tier_spells = [
                s["name"] for s in all_class_spells if s.get("level", 0) == max_spell_level
            ]
        if not tier_spells:
            tier_spells = [
                s["name"] for s in all_class_spells if 0 < s.get("level", 0) <= max_spell_level
            ]
        # Deduplicate and exclude known
        tier_spells = [s for s in tier_spells if s.strip().lower() not in known_set]
        if tier_spells:
            return tier_spells[:2]
        return [s for s in fallback_list if s.strip().lower() not in known_set][:2]

    is_horizon_walker = "horizon" in str(char_data.get("subclass", "")).lower()
    ranger_offensive = (
        ["Lightning Arrow", "Conjure Animals", "Zephyr Strike"]
        if is_horizon_walker
        else ["Lightning Arrow", "Hunter's Mark", "Zephyr Strike"]
    )

    offensive_spells = {
        "Wizard": ["Fireball", "Scorching Ray", "Magic Missile"],
        "Sorcerer": ["Fireball", "Chaos Bolt", "Lightning Bolt"],
        "Warlock": ["Hunger of Hadar", "Hellish Rebuke", "Hex"],
        "Cleric": ["Spiritual Weapon", "Spirit Guardians", "Guiding Bolt"],
        "Druid": ["Moonbeam", "Call Lightning", "Produce Flame"],
        "Bard": ["Dissonant Whispers", "Shatter", "Vicious Mockery"],
        "Paladin": ["Thunderous Smite", "Wrathful Smite", "Destructive Wave"],
        "Ranger": ranger_offensive,
        "Artificer": ["Catapult", "Shocking Grasp", "Heat Metal"],
    }

    defensive_spells = {
        "Wizard": ["Shield", "Mirror Image", "Misty Step", "Absorb Elements"],
        "Sorcerer": ["Shield", "Misty Step", "Mirror Image", "Absorb Elements"],
        "Warlock": ["Armor of Agathys", "Misty Step", "Darkness"],
        "Cleric": ["Aid", "Shield of Faith", "Sanctuary", "Lesser Restoration"],
        "Druid": ["Barkskin", "Pass without Trace", "Goodberry", "Healing Word"],
        "Bard": ["Healing Word", "Invisibility", "Lesser Restoration"],
        "Paladin": ["Aid", "Cure Wounds", "Lesser Restoration"],
        "Ranger": ["Protection from Energy", "Pass without Trace", "Absorb Elements"],
        "Artificer": ["Shield", "Aid", "Absorb Elements"],
    }

    utility_spells = {
        "Wizard": ["Counterspell", "Fly", "Detect Magic", "Find Familiar"],
        "Sorcerer": ["Counterspell", "Haste", "Polymorph", "Fly"],
        "Warlock": ["Hypnotic Pattern", "Fly", "Counterspell", "Dimension Door"],
        "Cleric": ["Bless", "Revivify", "Dispel Magic", "Guidance"],
        "Druid": ["Entangle", "Spike Growth", "Plant Growth", "Faerie Fire"],
        "Bard": ["Hypnotic Pattern", "Faerie Fire", "Suggestion", "Hold Person"],
        "Paladin": ["Bless", "Find Steed", "Crusader's Mantle"],
        "Ranger": ["Plant Growth", "Wind Wall", "Silence"],
        "Artificer": ["Web", "Haste", "Revivify", "Mending"],
    }

    # Subclass choices per build
    sub_1 = available_subclasses[0] if needs_subclass and available_subclasses else None
    sub_2 = available_subclasses[1] if needs_subclass and len(available_subclasses) > 1 else sub_1
    sub_3 = (
        available_subclasses[2]
        if needs_subclass and len(available_subclasses) > 2
        else (available_subclasses[-1] if needs_subclass and available_subclasses else None)
    )

    # Feats per build
    is_caster = target_class in [
        "Wizard",
        "Sorcerer",
        "Warlock",
        "Cleric",
        "Druid",
        "Bard",
        "Artificer",
    ]
    feat_1 = f"+2 to {prim_stat}" if has_asi else None
    if has_asi and is_caster:
        feat_1 = f"War Caster (or +2 to {prim_stat})"
    elif has_asi and not is_caster:
        feat_1 = f"Great Weapon Master or Polearm Master (or +2 to {prim_stat})"

    feat_2 = "Sentinel or Tough (+2 CON alternative)" if has_asi else None
    feat_3 = f"Fey Touched (+1 {prim_stat}) or Alert" if has_asi else None

    next_asi_lvl = 12
    for m in [4, 6, 8, 10, 12, 14, 16, 19]:
        if m > target_class_level:
            next_asi_lvl = m
            break

    if not feat_1:
        feat_1 = (
            f"War Caster or +2 to {prim_stat} (at Level {next_asi_lvl} ASI)"
            if is_caster
            else f"Sharpshooter or +2 to {prim_stat} (at Level {next_asi_lvl} ASI)"
        )
    if not feat_2:
        feat_2 = f"Alert or Tough (+2 CON) (at Level {next_asi_lvl} ASI)"
    if not feat_3:
        feat_3 = f"Skill Expert or Fey Touched (at Level {next_asi_lvl} ASI)"

    # Spells per build (prioritize newly unlocked tier spells excluding known spells)
    spells_1 = _get_top_spells(["evocation", "necromancy"], offensive_spells.get(target_class, []))
    spells_2 = _get_top_spells(["abjuration"], defensive_spells.get(target_class, []))
    spells_3 = _get_top_spells(
        ["conjuration", "transmutation", "divination"], utility_spells.get(target_class, [])
    )

    if target_class == "Ranger":
        future_ms_1 = [
            f"Level 10: Hide in Plain Sight & Tier 3 Spells ({', '.join(spells_1) or 'Lightning Arrow'})",
            "Level 11: Planar Warrior scales to 2d8 force damage & Distant Strike (bonus 3rd attack + teleport)",
            f"Level 12: Major Feat Milestone - {feat_1}",
            "Level 13: Tier 4 Spells - Guardian of Nature (advantage on ranged attacks) & Freedom of Movement",
            "Level 15: Spectral Defense (Reaction: grant resistance to all damage from an attack)",
            "Level 17: Tier 5 Spells - Swift Quiver (4 longbow attacks per turn)",
        ]
        future_ms_2 = [
            f"Level 10: Natural Explorer (3rd terrain) & Tier 3 Spells ({', '.join(spells_2) or 'Wind Wall'})",
            "Level 11: Distant Strike (extreme battlefield mobility and repositioning)",
            f"Level 12: Defensive Feat Milestone - {feat_2}",
            "Level 13: Tier 4 Spells - Freedom of Movement (immune to paralysis, restraints, difficult terrain)",
            "Level 15: Spectral Defense (evade lethal blows across planes)",
        ]
        future_ms_3 = [
            f"Level 10: Camouflage & Utility Spells ({', '.join(spells_3) or 'Plant Growth'})",
            "Level 11: Distant Strike (tactical scouting and hit-and-run engagement)",
            f"Level 12: Utility Feat Milestone - {feat_3}",
            "Level 13: Tier 4 Spells - Locate Creature & Freedom of Movement",
            "Level 15: Spectral Defense (planar survivability)",
        ]
    else:
        future_ms_1 = [
            f"Level {target_class_level}: Specialization and class tier features",
            f"Level {next_asi_lvl}: Major ASI / Feat Milestone ({feat_1})",
            f"Level {min(20, target_class_level + 3)}: Advanced tier abilities and tactical scaling",
        ]
        future_ms_2 = [
            f"Level {target_class_level}: Defensive core and class features",
            f"Level {next_asi_lvl}: Defensive Feat Milestone ({feat_2})",
            f"Level {min(20, target_class_level + 3)}: Advanced tier abilities and resilience",
        ]
        future_ms_3 = [
            f"Level {target_class_level}: Utility toolkit and tactical expansion",
            f"Level {next_asi_lvl}: Utility Feat Milestone ({feat_3})",
            f"Level {min(20, target_class_level + 3)}: High-tier versatile spell and ability unlocks",
        ]

    return [
        {
            "build_name": f"The Focused Striker ({target_class} Specialization)",
            "theme": f"Maximize core combat efficiency, offensive output, and primary {prim_stat} scaling.",
            "playstyle_summary": "Focus on proactive engagements. Position to maximize your round-1 damage output and force enemies onto the defensive.",
            "pros": [
                f"Peak scaling for attack rolls and spell save DCs with high {prim_stat}",
                "Consistent single-target and multi-target threat",
                "Straightforward and devastating action economy",
            ],
            "cons": [
                "Less defensive redundancy when cornered",
                "Fewer utility options out of combat",
            ],
            "recommended_subclass": sub_1,
            "recommended_feat_or_asi": feat_1,
            "recommended_spells": spells_1,
            "key_tactics": [
                "Target high-threat priority enemies to break enemy action economy early",
                "Coordinate with frontline allies for flanking and advantage",
            ],
            "future_milestones": future_ms_1,
        },
        {
            "build_name": "The Resilient Anchor (Defensive / Protector)",
            "theme": "Prioritize survivability, concentration defense, and battlefield positioning.",
            "playstyle_summary": "Act as the party's backbone. Use defensive features and reactions to mitigate damage and control enemy movement.",
            "pros": [
                "High survivability and superior concentration saving throw protection",
                "Protects fragile backline allies from being overrun",
                "Extremely durable against attrition and prolonged battles",
            ],
            "cons": [
                "Moderate burst damage compared to pure offensive builds",
                "Requires careful positioning in tight spaces",
            ],
            "recommended_subclass": sub_2,
            "recommended_feat_or_asi": feat_2,
            "recommended_spells": spells_2,
            "key_tactics": [
                "Anchor chokepoints and position between threats and party casters",
                "Activate defensive buffs before stepping into contested terrain",
            ],
            "future_milestones": future_ms_2,
        },
        {
            "build_name": "The Versatile Tactician (Control / Utility)",
            "theme": "Expand tactical toolkit with crowd control, mobility, and out-of-combat utility.",
            "playstyle_summary": "Shape the battlefield. Use positioning, status effects, and versatile spells to disrupt enemy strategies.",
            "pros": [
                "Superior encounter manipulation and crowd control options",
                "High versatility in social, exploration, and stealth pillars",
                "Flexible reaction options to answer unexpected monster abilities",
            ],
            "cons": [
                "Demands careful spell slot and resource pacing",
                "Relies on party coordination to follow up on status effects",
            ],
            "recommended_subclass": sub_3,
            "recommended_feat_or_asi": feat_3,
            "recommended_spells": spells_3,
            "key_tactics": [
                "Open combat with area denial or crowd control on enemy clusters",
                "Keep mobility options available to peel away from heavy melee threats",
            ],
            "future_milestones": future_ms_3,
        },
    ]


def generate_level_up_build_recommendations(
    char_data: dict,
    target_class: str | None = None,
    target_level: int | None = None,
) -> dict:
    """
    Analyzes the character and returns up to 3 distinct, highly synergistic build paths
    for their upcoming level up.
    """
    from backend.services.stats_service import calculate_max_spell_slots

    repo = _get_rules_repo()
    edition = char_data.get("dnd_edition", EDITION_2014)
    classes = char_data.get("classes", [])
    current_total_level = char_data.get("char_level", 1)
    target_total_level = max(current_total_level + 1, target_level or (current_total_level + 1))
    target_class = target_class or char_data.get("char_class", "Fighter")

    # Current class level
    class_current_level = 0
    current_subclass = None
    if classes:
        for cls in classes:
            if cls.get("class_name", "").lower() == target_class.lower():
                class_current_level = cls.get("level", 0)
                current_subclass = cls.get("subclass")
                break
    else:
        if target_class.lower() == char_data.get("char_class", "Fighter").lower():
            class_current_level = current_total_level
            current_subclass = char_data.get("subclass")

    target_class_level = class_current_level + 1

    needs_sub = _needs_subclass(target_class, target_class_level, current_subclass, edition)
    available_subclasses = repo.get_subclasses(target_class, edition) if needs_sub else []
    has_asi = _has_asi(target_class, target_class_level)

    # Calculate max castable spell level for target class
    max_slots = calculate_max_spell_slots(
        target_class, target_class_level, current_subclass, edition=edition
    )
    max_spell_level = 0
    for i in range(1, 10):
        if max_slots.get(f"level_{i}", 0) > 0:
            max_spell_level = i

    # Collect ALL known/prepared spells across all tiers
    all_known_spells = []
    sp_dict = char_data.get("spells") or {}
    if isinstance(sp_dict, dict):
        for lvl_list in sp_dict.values():
            if isinstance(lvl_list, list):
                for s in lvl_list:
                    name = s.get("name") if isinstance(s, dict) else str(s)
                    if name and name not in all_known_spells:
                        all_known_spells.append(name)
    elif isinstance(sp_dict, list):
        for s in sp_dict:
            name = s.get("name") if isinstance(s, dict) else str(s)
            if name and name not in all_known_spells:
                all_known_spells.append(name)

    known_spells_str = ", ".join(all_known_spells) if all_known_spells else "None"

    # Fallback template generator helper
    def fallback_result():
        fallback_builds = _get_fallback_level_up_recommendations(
            char_data=char_data,
            target_class=target_class,
            target_class_level=target_class_level,
            target_total_level=target_total_level,
            edition=edition,
            needs_subclass=needs_sub,
            available_subclasses=available_subclasses,
            has_asi=has_asi,
            max_spell_level=max_spell_level,
            known_spells=all_known_spells,
        )
        return {
            "character_name": char_data.get("char_name", "Unknown"),
            "target_class": target_class,
            "target_level": target_total_level,
            "builds": fallback_builds,
        }

    # Format AI prompt
    try:
        # Collect weapons with details
        weapons_list = []
        for w in char_data.get("weapons", []):
            if isinstance(w, dict):
                w_str = w.get("name", "Weapon")
                dmg = (
                    w.get("damage")
                    or f"{w.get('damage_dice', '')} {w.get('damage_bonus', '')}".strip()
                )
                rng = w.get("range")
                props = w.get("properties")
                extra = []
                if dmg:
                    extra.append(f"Dmg: {dmg}")
                if rng and rng != "Melee":
                    extra.append(f"Range: {rng}")
                if props:
                    extra.append(props)
                if extra:
                    w_str += f" ({', '.join(extra)})"
                weapons_list.append(w_str)
        weapons_str = "; ".join(weapons_list) if weapons_list else "None specified"

        # Collect equipment
        eq_list = [
            eq.get("name")
            for eq in char_data.get("equipment", [])
            if isinstance(eq, dict) and eq.get("name")
        ]
        equipment_str = ", ".join(eq_list[:15]) if eq_list else "Standard gear"

        # Collect all features & traits
        all_features = [
            f.get("name")
            for f in char_data.get("features_traits", [])
            if isinstance(f, dict) and f.get("name")
        ]
        features_str = ", ".join(all_features) if all_features else "None"

        # Collect fighting style
        fighting_styles = [
            f
            for f in all_features
            if "fighting style" in f.lower()
            or any(
                s in f.lower()
                for s in ["archery", "dueling", "defense", "great weapon", "two-weapon"]
            )
        ]
        fighting_styles_str = ", ".join(fighting_styles) if fighting_styles else "None"

        prompt = LEVEL_UP_BUILD_RECOMMENDATIONS_PROMPT.format(
            edition=edition,
            current_level=current_total_level,
            target_level=target_total_level,
            target_class=target_class,
            target_class_level=target_class_level,
            name=char_data.get("char_name", "Unknown"),
            char_class=char_data.get("char_class", "Unknown"),
            subclass=current_subclass or char_data.get("subclass", "None"),
            race=char_data.get("race", "Unknown"),
            background=char_data.get("background", "Unknown"),
            stats=char_data.get("stats", {}),
            weapons=weapons_str,
            equipment=equipment_str,
            fighting_styles=fighting_styles_str,
            known_spells=known_spells_str,
            features=features_str,
            needs_subclass="YES" if needs_sub else "NO",
            available_subclasses=", ".join(available_subclasses)
            if available_subclasses
            else "None",
            has_asi="YES" if has_asi else "NO",
            max_spell_level=max_spell_level,
        )

        ai_response = generate_ai_json(prompt)
        if not ai_response or not isinstance(ai_response, dict):
            logger.warning("AI build recommendations returned non-dict response. Using fallback.")
            return fallback_result()

        raw_builds = ai_response.get("builds")
        if not isinstance(raw_builds, list) or len(raw_builds) == 0:
            logger.warning("AI build recommendations returned empty builds list. Using fallback.")
            return fallback_result()

        cleaned_builds = []
        for b in raw_builds[:3]:
            if not isinstance(b, dict):
                continue
            cleaned_builds.append(
                {
                    "build_name": str(b.get("build_name") or "Custom Archetype"),
                    "theme": str(b.get("theme") or ""),
                    "playstyle_summary": str(b.get("playstyle_summary") or ""),
                    "pros": [str(p) for p in b.get("pros", []) if p],
                    "cons": [str(c) for c in b.get("cons", []) if c],
                    "recommended_subclass": str(b.get("recommended_subclass"))
                    if b.get("recommended_subclass")
                    else None,
                    "recommended_feat_or_asi": str(b.get("recommended_feat_or_asi"))
                    if b.get("recommended_feat_or_asi")
                    else None,
                    "recommended_spells": [str(s) for s in b.get("recommended_spells", []) if s],
                    "key_tactics": [str(t) for t in b.get("key_tactics", []) if t],
                    "future_milestones": [str(m) for m in b.get("future_milestones", []) if m],
                }
            )

        if not cleaned_builds:
            return fallback_result()

        return {
            "character_name": char_data.get("char_name", "Unknown"),
            "target_class": target_class,
            "target_level": target_total_level,
            "builds": cleaned_builds,
        }
    except Exception as e:
        logger.error(
            f"Failed to generate AI build recommendations: {e}. Falling back to rule-based archetypes."
        )
        return fallback_result()


def analyze_level_up(char_data: dict, user_choices: dict = None) -> dict:
    """Determines level up changes deterministically without an LLM call."""
    import math

    from backend.repositories.rules_repository import RulesRepository
    from backend.services.progression_service import get_level_up_vitals

    classes = char_data.get("classes", [])
    user_choices = user_choices or {}

    target_class = user_choices.get("level_up_class", char_data.get("char_class", "Fighter"))

    # Calculate the current level of the TARGET class
    class_current_level = 0
    if classes:
        for cls in classes:
            if cls.get("class_name", "").lower() == target_class.lower():
                class_current_level = cls.get("level", 0)
                break
    else:
        if target_class.lower() == char_data.get("char_class", "Fighter").lower():
            class_current_level = char_data.get("char_level", 1)

    target_level = class_current_level + 1
    current_total_level = char_data.get("char_level", 1)
    target_total_level = current_total_level + 1

    if target_total_level > 20:
        raise ValueError("Character cannot exceed level 20.")

    edition = char_data.get("dnd_edition", "2014 Edition")

    # Override char_class to target_class for the rest of this function
    char_class = target_class

    rules_repo = RulesRepository()
    static_features = rules_repo.get_features_at_level(char_class, target_level, edition)

    try:
        vitals = get_level_up_vitals(
            char_class=char_class,
            current_level=class_current_level,
            con_score=char_data.get("stats", {}).get("CON", 10),
            edition=edition,
            features=char_data.get("features_traits", []),
        )
        hp_increase = max(1, vitals.get("average_hp_gain", 0))
    except Exception:
        hp_increase = 0

    custom_hp = user_choices.get("custom_hp_increase")
    if custom_hp is not None:
        try:
            hp_increase = max(1, int(custom_hp))
        except (ValueError, TypeError):
            pass

    updated_pb = math.ceil(target_total_level / 4) + 1

    choices = []

    # 1. Subclass
    current_subclass = None
    for cls in classes:
        if cls.get("class_name", "").lower() == char_class.lower():
            current_subclass = cls.get("subclass")
            break

    if not classes and char_class.lower() == char_data.get("char_class", "").lower():
        current_subclass = char_data.get("subclass")

    if not current_subclass:
        subclasses = rules_repo.get_subclasses(char_class, edition)
        if subclasses:
            subclass_level = 3
            if edition == EDITION_2014:
                if char_class.title() in ["Cleric", "Sorcerer", "Warlock"]:
                    subclass_level = 1
                elif char_class.title() in ["Wizard", "Druid"]:
                    subclass_level = 2

            if target_level >= subclass_level:
                choices.append(
                    {
                        "type": "subclass",
                        "label": f"Choose your {char_class} Subclass",
                        "options": subclasses,
                        "ai_recommendation": f"Any of these official subclasses will work perfectly for your {char_class}.",
                    }
                )

    # 2. ASI/Feat
    is_asi_level = any(
        "ability score improvement" in f.get("name", "").lower() for f in static_features
    )

    if is_asi_level:
        char_race = char_data.get("race", "").lower()
        allowed_feats = []
        for f in rules_repo.get_all_feats(edition):
            reqs = f.get("prerequisites", {}).get("other", [])
            if not reqs or any(r.lower() in char_race for r in reqs):
                allowed_feats.append(f["name"])

        choices.append(
            {
                "type": "feat",
                "label": "Choose a Feat or Ability Score Improvement",
                "options": ["+2 to one Stat", "+1 to two Stats"] + allowed_feats,
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
        from backend.services.stats_service import calculate_max_spell_slots

        max_slots = calculate_max_spell_slots(
            char_class, target_level, current_subclass, edition=edition
        )
        max_spell_level = 0
        for i in range(1, 10):
            if max_slots.get(f"level_{i}", 0) > 0:
                max_spell_level = i

        # Handle Warlock Mystic Arcanum or similar edge cases
        if char_class == "Warlock" and target_level >= 11:
            max_spell_level = max(max_spell_level, 6)
        if char_class == "Warlock" and target_level >= 13:
            max_spell_level = max(max_spell_level, 7)
        if char_class == "Warlock" and target_level >= 15:
            max_spell_level = max(max_spell_level, 8)
        if char_class == "Warlock" and target_level >= 17:
            max_spell_level = max(max_spell_level, 9)

        # Collect all spells already known by the character to exclude them
        known_spells_lower = set()
        sp_dict = char_data.get("spells") or {}
        if isinstance(sp_dict, dict):
            for lvl_list in sp_dict.values():
                if isinstance(lvl_list, list):
                    for s in lvl_list:
                        name = s.get("name") if isinstance(s, dict) else str(s)
                        if name:
                            known_spells_lower.add(name.strip().lower())
        elif isinstance(sp_dict, list):
            for s in sp_dict:
                name = s.get("name") if isinstance(s, dict) else str(s)
                if name:
                    known_spells_lower.add(name.strip().lower())

        all_spells = rules_repo.get_all_spells(edition)
        spells_level_map = {s["name"]: s.get("level", 0) for s in all_spells if "name" in s}

        spells = []
        magical_secrets_spells = []
        char_class_lower = char_class.lower()
        for s in all_spells:
            s_name = s.get("name", "")
            if not s_name or s_name.strip().lower() in known_spells_lower:
                continue
            s_level = s.get("level", 0)
            if 0 < s_level <= max_spell_level:
                magical_secrets_spells.append(s_name)
                s_classes = [c.lower() for c in s.get("classes", [])]
                if not s_classes or char_class_lower in s_classes:
                    spells.append(s_name)

        # Sort spells: highest level (newest tier) first, then alphabetical
        spells.sort(key=lambda n: (-spells_level_map.get(n, 0), n))
        magical_secrets_spells.sort(key=lambda n: (-spells_level_map.get(n, 0), n))

        # Dynamic AI recommendation focused on the highest unlocked tier
        top_candidates = [s for s in spells if spells_level_map.get(s, 0) == max_spell_level][:3]
        if top_candidates:
            ai_spell_rec = f"Top new choices for Tier {max_spell_level} (Level {target_level}+): {', '.join(top_candidates)}."
        elif spells:
            ai_spell_rec = f"Consider high-synergy picks like {spells[0]}."
        else:
            ai_spell_rec = f"Explore unlearned spells for your {char_class}."

        # Bard Magical Secrets overrides
        if char_class == "Bard" and target_level in [10, 14, 18]:
            choices.append(
                {
                    "type": "spell_secret_1",
                    "label": "Magical Secrets: Choose 1st Spell (Any Class)",
                    "options": magical_secrets_spells,
                    "ai_recommendation": f"Pick high-impact spells up to Level {max_spell_level} from any class list.",
                }
            )
            choices.append(
                {
                    "type": "spell_secret_2",
                    "label": "Magical Secrets: Choose 2nd Spell (Any Class)",
                    "options": magical_secrets_spells,
                    "ai_recommendation": f"Pick high-impact spells up to Level {max_spell_level} from any class list.",
                }
            )
        elif char_class == "Bard" and target_level == 6 and current_subclass == "College of Lore":
            choices.append(
                {
                    "type": "spell_secret_1",
                    "label": "Additional Magical Secrets: Choose 1st Spell (Any Class)",
                    "options": magical_secrets_spells,
                    "ai_recommendation": f"Lore Bards get Magical Secrets early! Choose up to Level {max_spell_level} spells.",
                }
            )
            choices.append(
                {
                    "type": "spell_secret_2",
                    "label": "Additional Magical Secrets: Choose 2nd Spell (Any Class)",
                    "options": magical_secrets_spells,
                    "ai_recommendation": f"Lore Bards get Magical Secrets early! Choose up to Level {max_spell_level} spells.",
                }
            )
        else:
            choices.append(
                {
                    "type": "spell",
                    "label": f"Learn/Prepare a {char_class} Spell",
                    "options": spells,
                    "ai_recommendation": ai_spell_rec,
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
    if isinstance(updated_char.get("stats"), dict):
        updated_char["stats"] = dict(updated_char["stats"])
    if isinstance(updated_char.get("base_stats"), dict):
        updated_char["base_stats"] = dict(updated_char["base_stats"])

    # 1. Apply Stat Updates & Level
    if stat_updates:
        for k, v in stat_updates.items():
            if k == "char_level":
                updated_char["char_level"] = v
            elif k in updated_char.get("stats", {}):
                old_val = updated_char["stats"][k]
                updated_char["stats"][k] = v
                if (
                    isinstance(updated_char.get("base_stats"), dict)
                    and k in updated_char["base_stats"]
                ):
                    updated_char["base_stats"][k] += v - old_val

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
        updated_char.get("char_class"), updated_char.get("dnd_edition", "2014 Edition")
    )
    return sync_character_stats(updated_char, class_data, weapon_deltas, homebrew_content)
