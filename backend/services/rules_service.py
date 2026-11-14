import functools
import json
import logging
import re

from backend.core.ai_client import generate_ai_json, generate_ai_response
from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.prompts import (
    PDF_PARSING_STEP1_PROMPT,
    PDF_PARSING_STEP2_PROMPT,
    RULE_COMPARISON_PROMPT,
    RULES_ORACLE_PROMPT,
)
from backend.core.schemas import CharacterSchema
from backend.core.state_manager import get_default_character
from backend.repositories.rules_repository import RulesRepository
from backend.utils.api_client import fetch_feat_from_api

logger = logging.getLogger("DnDAssistant.RulesService")


@functools.lru_cache(maxsize=1)
def _get_rules_repo():
    return RulesRepository()


@functools.lru_cache(maxsize=128)
def query_rules(query: str, edition: str = EDITION_2014) -> str:
    """Uses AI to answer questions about D&D rules."""
    prompt = RULES_ORACLE_PROMPT.format(
        edition=edition,
        query=query,
    )
    return generate_ai_response(prompt)


@functools.lru_cache(maxsize=128)
def compare_rules(query: str) -> str:
    """Uses AI to compare 2014 and 2024 rules."""
    prompt = RULE_COMPARISON_PROMPT.format(query=query)
    return generate_ai_response(prompt)


_DEFAULT_STARTING_EQUIPMENT_BY_CLASS: dict[str, list[dict]] = {
    "paladin": [
        {"name": "Chain Mail", "equipped": True},
        {"name": "Shield", "equipped": True},
        {"name": "Holy Symbol", "equipped": False},
        {"name": "Priest's Pack", "equipped": False},
    ],
    "fighter": [
        {"name": "Chain Mail", "equipped": True},
        {"name": "Shield", "equipped": True},
        {"name": "Dungeoneer's Pack", "equipped": False},
    ],
    "barbarian": [
        {"name": "Explorer's Pack", "equipped": False},
    ],
    "monk": [
        {"name": "Explorer's Pack", "equipped": False},
    ],
    "rogue": [
        {"name": "Leather Armor", "equipped": True},
        {"name": "Thieves' Tools", "equipped": False},
        {"name": "Burglar's Pack", "equipped": False},
    ],
    "ranger": [
        {"name": "Studded Leather Armor", "equipped": True},
        {"name": "Explorer's Pack", "equipped": False},
    ],
    "cleric": [
        {"name": "Chain Shirt", "equipped": True},
        {"name": "Shield", "equipped": True},
        {"name": "Holy Symbol", "equipped": False},
        {"name": "Priest's Pack", "equipped": False},
    ],
    "druid": [
        {"name": "Leather Armor", "equipped": True},
        {"name": "Wooden Shield", "equipped": True},
        {"name": "Druidic Focus", "equipped": False},
        {"name": "Explorer's Pack", "equipped": False},
    ],
    "bard": [
        {"name": "Leather Armor", "equipped": True},
        {"name": "Lute", "equipped": False},
        {"name": "Entertainer's Pack", "equipped": False},
    ],
    "wizard": [
        {"name": "Spellbook", "equipped": False},
        {"name": "Arcane Focus", "equipped": False},
        {"name": "Scholar's Pack", "equipped": False},
    ],
    "sorcerer": [
        {"name": "Arcane Focus", "equipped": False},
        {"name": "Dungeoneer's Pack", "equipped": False},
    ],
    "warlock": [
        {"name": "Leather Armor", "equipped": True},
        {"name": "Arcane Focus", "equipped": False},
        {"name": "Scholar's Pack", "equipped": False},
    ],
    "artificer": [
        {"name": "Studded Leather Armor", "equipped": True},
        {"name": "Thieves' Tools", "equipped": False},
        {"name": "Dungeoneer's Pack", "equipped": False},
    ],
}

_DEFAULT_STARTING_WEAPONS_BY_CLASS: dict[str, list[dict]] = {
    "paladin": [
        {"name": "Longsword", "damage_dice": "1d8"},
        {"name": "Javelin", "damage_dice": "1d6"},
    ],
    "fighter": [
        {"name": "Longsword", "damage_dice": "1d8"},
        {"name": "Light Crossbow", "damage_dice": "1d8"},
    ],
    "barbarian": [
        {"name": "Greataxe", "damage_dice": "1d12"},
        {"name": "Handaxe", "damage_dice": "1d6"},
    ],
    "monk": [
        {"name": "Quarterstaff", "damage_dice": "1d6"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
    "rogue": [
        {"name": "Shortsword", "damage_dice": "1d6"},
        {"name": "Shortbow", "damage_dice": "1d6"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
    "ranger": [
        {"name": "Longbow", "damage_dice": "1d8"},
        {"name": "Shortsword", "damage_dice": "1d6"},
    ],
    "cleric": [
        {"name": "Mace", "damage_dice": "1d6"},
        {"name": "Light Crossbow", "damage_dice": "1d8"},
    ],
    "druid": [
        {"name": "Quarterstaff", "damage_dice": "1d6"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
    "bard": [
        {"name": "Rapier", "damage_dice": "1d8"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
    "wizard": [
        {"name": "Quarterstaff", "damage_dice": "1d6"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
    "sorcerer": [
        {"name": "Quarterstaff", "damage_dice": "1d6"},
        {"name": "Light Crossbow", "damage_dice": "1d8"},
    ],
    "warlock": [
        {"name": "Quarterstaff", "damage_dice": "1d6"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
    "artificer": [
        {"name": "Light Crossbow", "damage_dice": "1d8"},
        {"name": "Dagger", "damage_dice": "1d4"},
    ],
}

_DEFAULT_STARTING_SPELLS_BY_CLASS: dict[str, dict[str, list[str]]] = {
    "wizard": {
        "cantrips": ["Fire Bolt", "Mage Hand", "Prestidigitation"],
        "level_1": ["Shield", "Magic Missile", "Detect Magic", "Mage Armor"],
    },
    "cleric": {
        "cantrips": ["Sacred Flame", "Guidance", "Thaumaturgy"],
        "level_1": ["Bless", "Cure Wounds", "Guiding Bolt", "Healing Word"],
    },
    "druid": {
        "cantrips": ["Produce Flame", "Guidance"],
        "level_1": ["Entangle", "Healing Word", "Faerie Fire", "Goodberry"],
    },
    "bard": {
        "cantrips": ["Vicious Mockery", "Minor Illusion"],
        "level_1": ["Healing Word", "Faerie Fire", "Dissonant Whispers", "Charm Person"],
    },
    "sorcerer": {
        "cantrips": ["Fire Bolt", "Ray of Frost", "Mage Hand", "Prestidigitation"],
        "level_1": ["Shield", "Magic Missile"],
    },
    "warlock": {
        "cantrips": ["Eldritch Blast", "Minor Illusion"],
        "level_1": ["Hex", "Armor of Agathys"],
    },
    "paladin": {
        "cantrips": [],
        "level_1": ["Bless", "Cure Wounds"],
    },
    "ranger": {
        "cantrips": [],
        "level_1": ["Hunter's Mark", "Cure Wounds"],
    },
    "artificer": {
        "cantrips": ["Fire Bolt", "Mending"],
        "level_1": ["Cure Wounds", "Faerie Fire"],
    },
}

_RACIAL_LANGUAGE_MAP: dict[str, str] = {
    "elf": "Elvish",
    "half-elf": "Elvish",
    "dwarf": "Dwarvish",
    "halfling": "Halfling",
    "gnome": "Gnomish",
    "dragonborn": "Draconic",
    "tiefling": "Infernal",
    "orc": "Orc",
    "half-orc": "Orc",
    "goliath": "Giant",
    "aasimar": "Celestial",
}


def inject_mandatory_character_grants(
    char_data: dict,
    edition: str | None = None,
    is_forge: bool = False,
    auto_feats: bool = True,
    auto_spells: bool = True,
    chosen_feats: list | None = None,
    chosen_spells: list | None = None,
    chosen_equipment: list | None = None,
) -> dict:
    """
    Deterministically injects all mandatory D&D 5e (2014) and 5.5e (2024 Revision)
    features, traits, skill proficiencies, tool proficiencies, origin feats, racial speed,
    and fallback starting gear/spells from static JSON rulesets in RulesRepository.
    """
    repo = _get_rules_repo()
    edition_str = str(edition or char_data.get("dnd_edition") or EDITION_2014)
    is_2024 = "2024" in edition_str

    char_class = str(char_data.get("char_class") or "").strip()
    class_lower = char_class.lower()
    subclass = str(char_data.get("subclass") or "").strip()
    level = int(char_data.get("char_level") or 1)
    race = str(char_data.get("race") or "").strip()
    background = str(char_data.get("background") or "").strip()

    class_data = repo.get_class_progression(char_class, edition_str) if char_class else None
    race_data = repo.get_race_data(race, edition_str) if race else None
    bg_data = repo.get_background_data(background, edition_str) if background else None

    # Normalize features_traits list
    raw_features = char_data.get("features_traits") or []
    features_list: list[dict] = []
    for f in raw_features:
        if isinstance(f, dict):
            features_list.append(f)
        elif hasattr(f, "model_dump"):
            features_list.append(f.model_dump())
        elif isinstance(f, str) and f.strip():
            features_list.append({"name": f.strip(), "description": "", "source": "Imported"})
    char_data["features_traits"] = features_list

    existing_names = {
        str(f.get("name") or "").strip().lower() for f in features_list if isinstance(f, dict)
    }

    def _add_feature(name: str, description: str, source: str) -> None:
        clean_name = name.strip()
        if not clean_name:
            return
        low = clean_name.lower()
        if low in existing_names:
            return
        # Avoid duplicate feat prefixes (e.g. "Feat: Alert" vs "Origin Feat: Alert" vs "Alert")
        bare = low.replace("origin feat: ", "").replace("feat: ", "").strip()
        if source.lower() == "feat":
            for ex in existing_names:
                ex_bare = ex.replace("origin feat: ", "").replace("feat: ", "").strip()
                if ex_bare == bare:
                    return
        features_list.append(
            {"name": clean_name, "description": description.strip(), "source": source}
        )
        existing_names.add(low)

    # 1. Mandatory Species / Racial Traits & Base Speed
    racial_mandatory_skills: list[str] = []
    has_skill_versatility_one = False
    has_skill_versatility_two = False

    if race_data:
        race_speed = race_data.get("speed")
        if isinstance(race_speed, int) and char_data.get("base_speed") is None:
            if char_data.get("speed") in (None, 30):
                char_data["speed"] = race_speed
                char_data["base_speed"] = race_speed

        for trait in race_data.get("traits", []):
            if not isinstance(trait, dict):
                continue
            t_name = str(trait.get("name") or "").strip()
            t_desc = str(trait.get("description") or "").strip()
            t_low = t_name.lower()
            desc_low = t_desc.lower()

            if t_low == "ability score increase":
                continue

            _add_feature(t_name, t_desc, "Race")

            if t_low == "keen senses" or "proficiency in the perception skill" in desc_low:
                racial_mandatory_skills.append("Perception")
            elif t_low == "naturally stealthy" or "proficiency in the stealth skill" in desc_low:
                racial_mandatory_skills.append("Stealth")
            elif t_low == "menacing" or "proficiency in the intimidation skill" in desc_low:
                racial_mandatory_skills.append("Intimidation")
            elif "proficiency in two skills of your choice" in desc_low:
                has_skill_versatility_two = True
            elif "proficiency in one skill of your choice" in desc_low:
                has_skill_versatility_one = True

    # 2. Mandatory Static Class & Subclass Features
    if char_class and level >= 1:
        for lvl in range(1, level + 1):
            for feat in repo.get_features_at_level(char_class, lvl, edition_str):
                if isinstance(feat, dict):
                    _add_feature(
                        str(feat.get("name") or ""),
                        str(feat.get("description") or ""),
                        str(feat.get("source") or "Class"),
                    )

    if subclass and subclass.lower() != "none" and not (is_2024 and level < 3):
        sub_mech = repo.get_subclass_mechanics(char_class, edition_str).get("subclasses", {})
        matched_sub = next(
            (v for k, v in sub_mech.items() if k.strip().lower() == subclass.strip().lower()),
            None,
        )
        if isinstance(matched_sub, dict):
            for entry in (matched_sub.get("scaling") or {}).values():
                if not isinstance(entry, dict):
                    continue
                valid_steps = [
                    st
                    for st in (entry.get("steps") or [])
                    if isinstance(st, dict) and int(st.get("level", 99)) <= level
                ]
                if valid_steps:
                    best_step = max(valid_steps, key=lambda s: int(s.get("level", 0)))
                    s_name = str(entry.get("name") or "").strip()
                    hint = str(entry.get("hint") or "").strip()
                    notation = str(best_step.get("notation") or "").strip()
                    s_desc = f"{hint} ({notation})".strip(" ()") if notation else hint
                    _add_feature(s_name, s_desc, "Subclass")

    # 3. Mandatory Background Features, Tools & Skills
    bg_mandatory_skills: list[str] = []
    bg_valid_tools: list[str] = []
    if bg_data:
        for s in bg_data.get("skills", []) or []:
            s_str = str(s).strip()
            if s_str and "any " not in s_str.lower():
                bg_mandatory_skills.append(s_str)

        for t in bg_data.get("tools", []) or []:
            t_str = str(t).strip()
            if t_str and "any " not in t_str.lower():
                bg_valid_tools.append(t_str)

        if not is_2024 and isinstance(bg_data.get("feature"), dict):
            bf_name = str(bg_data["feature"].get("name") or "").strip()
            bf_desc = str(bg_data["feature"].get("description") or "").strip()
            if bf_name:
                _add_feature(bf_name, bf_desc, "Background")

        if bg_valid_tools:
            bg_label = bg_data.get("name", background)
            _add_feature(
                f"Background Tool Proficiency ({bg_label})",
                f"Tool Proficiency granted by {bg_label} background: {', '.join(bg_valid_tools)}.",
                "Background",
            )

    # Merge mandatory Background & Racial skill proficiencies on character forge (or initial sync with explicit background)
    if is_forge:
        skill_profs = [
            str(s).strip() for s in (char_data.get("skill_proficiencies") or []) if str(s).strip()
        ]
        had_no_user_skills = len(skill_profs) == 0
        seen_skills = {s.lower() for s in skill_profs}

        def _add_skill(sk: str) -> bool:
            sk_clean = sk.strip()
            if sk_clean and sk_clean.lower() not in seen_skills:
                skill_profs.append(sk_clean)
                seen_skills.add(sk_clean.lower())
                return True
            return False

        # Always merge mandatory Background skills
        for b_sk in bg_mandatory_skills:
            _add_skill(b_sk)

        # Always merge mandatory Racial skills (e.g., Elf Perception, Halfling Stealth)
        for r_sk in racial_mandatory_skills:
            _add_skill(r_sk)

        # If user omitted class skills completely, deterministically fill class skill slots from class options
        class_skills_cfg = (
            (class_data or {}).get("starting_proficiencies", {}).get("skills", {})
            if isinstance(class_data, dict)
            else {}
        )
        class_skill_count = int(class_skills_cfg.get("count", 2) or 2)
        class_skill_options = list(class_skills_cfg.get("options") or [])

        if had_no_user_skills and class_skill_options:
            added_class_skills = 0
            for opt in class_skill_options:
                if added_class_skills >= class_skill_count:
                    break
                if _add_skill(str(opt)):
                    added_class_skills += 1

        # Bonus skill choices from Species (Human 2024 Skill Versatility / Warforged Specialized Design / Half-Elf)
        bonus_racial_choices = (
            2 if has_skill_versatility_two else (1 if has_skill_versatility_one else 0)
        )
        if bonus_racial_choices > 0 and had_no_user_skills and class_skill_options:
            added_bonus = 0
            for opt in class_skill_options + [
                "Perception",
                "Insight",
                "Athletics",
                "Stealth",
                "Investigation",
            ]:
                if added_bonus >= bonus_racial_choices:
                    break
                if _add_skill(str(opt)):
                    added_bonus += 1

        char_data["skill_proficiencies"] = skill_profs

    # 4. Mandatory 2024 Background Origin Feat & Human Versatile Origin Feat
    if is_2024 and auto_feats and is_forge:
        all_feats_2024 = repo.get_all_feats("2024")
        feats_by_name = {
            str(f.get("name") or "").lower(): f for f in all_feats_2024 if isinstance(f, dict)
        }

        def _find_feat_meta(feat_label: str) -> tuple[str, str]:
            clean_lbl = feat_label.strip()
            low_lbl = clean_lbl.lower()
            base_lbl = low_lbl.split("(")[0].strip()
            f_obj = feats_by_name.get(low_lbl) or feats_by_name.get(base_lbl)
            desc = (
                str(f_obj.get("description") or "")
                if f_obj
                else f"2024 Origin Feat granted by {background or 'Background'}."
            )
            return clean_lbl, desc

        bg_feat_raw = str((bg_data or {}).get("feat") or "").strip()
        if not bg_feat_raw or "any origin feat" in bg_feat_raw.lower():
            bg_feat_raw = "Skilled"

        is_2024_human = "human" in race.lower() and "half" not in race.lower()
        entitled_origin_count = 2 if is_2024_human else 1
        user_chosen_count = len(chosen_feats) if chosen_feats else 0

        advancements = list(char_data.get("advancements") or [])
        existing_adv_names = {
            str(a.get("name") or "").strip().lower().split("(")[0].strip()
            for a in advancements
            if isinstance(a, dict)
        }

        def _inject_origin_feat(feat_title: str) -> None:
            name_val, desc_val = _find_feat_meta(feat_title)
            base_key = name_val.lower().split("(")[0].strip()
            _add_feature(f"Origin Feat: {name_val}", desc_val, "Feat")
            if base_key not in existing_adv_names:
                advancements.append(
                    {
                        "level": 1,
                        "type": "Feat",
                        "name": name_val,
                        "description": desc_val[:200],
                    }
                )
                existing_adv_names.add(base_key)

        if user_chosen_count < entitled_origin_count:
            # Ensure Background's mandatory Origin Feat is present
            _inject_origin_feat(bg_feat_raw)

            # If 2024 Human (Versatile) still needs their 2nd Origin Feat, inject Skilled (or Tough if Skilled is taken)
            if is_2024_human and len(existing_adv_names) < 2:
                versatile_pick = "Skilled" if "skilled" not in existing_adv_names else "Tough"
                _inject_origin_feat(versatile_pick)

        char_data["advancements"] = advancements

    # 5. Deterministic Starting Languages, Equipment, Weapons & Spells Fallback (on Forge)
    if is_forge:
        # Languages
        if not char_data.get("languages"):
            langs = ["Common"]
            r_low = race.lower()
            for r_key, lang_name in _RACIAL_LANGUAGE_MAP.items():
                if r_key in r_low and lang_name not in langs:
                    langs.append(lang_name)
                    break
            if len(langs) == 1:
                langs.append("Dwarvish" if "soldier" in background.lower() else "Elvish")
            char_data["languages"] = langs

        # Starting Equipment
        if chosen_equipment is None and not char_data.get("equipment"):
            default_eq = [
                dict(item)
                for item in _DEFAULT_STARTING_EQUIPMENT_BY_CLASS.get(
                    class_lower, [{"name": "Explorer's Pack", "equipped": False}]
                )
            ]
            eq_names_lower = {it["name"].lower() for it in default_eq}
            for tool_name in bg_valid_tools:
                if tool_name.lower() not in eq_names_lower:
                    default_eq.append({"name": tool_name, "equipped": False})
                    eq_names_lower.add(tool_name.lower())
            char_data["equipment"] = default_eq

        # Starting Weapons
        if not char_data.get("weapons"):
            default_weapons = [
                dict(w)
                for w in _DEFAULT_STARTING_WEAPONS_BY_CLASS.get(
                    class_lower, [{"name": "Longsword", "damage_dice": "1d8"}]
                )
            ]
            char_data["weapons"] = default_weapons

        # Starting Spells (for spellcasters when auto_spells=True and chosen_spells is None)
        if auto_spells and chosen_spells is None:
            current_spells = char_data.get("spells") or {}
            has_any_spells = isinstance(current_spells, dict) and any(
                isinstance(v, list) and len(v) > 0 for v in current_spells.values()
            )
            if not has_any_spells:
                can_cast_at_lvl = class_lower in (
                    "wizard",
                    "cleric",
                    "druid",
                    "bard",
                    "sorcerer",
                    "warlock",
                    "artificer",
                ) or (class_lower in ("paladin", "ranger") and (is_2024 or level >= 2))
                if can_cast_at_lvl and class_lower in _DEFAULT_STARTING_SPELLS_BY_CLASS:
                    starter_spells = {
                        k: list(v)
                        for k, v in _DEFAULT_STARTING_SPELLS_BY_CLASS[class_lower].items()
                        if v
                    }
                    char_data["spells"] = starter_spells
                    prepared = []
                    for s_list in starter_spells.values():
                        for s_name in s_list:
                            if s_name not in prepared:
                                prepared.append(s_name)
                    char_data["prepared_spells"] = prepared

    return char_data


def autofix_character_build(char_data: dict, homebrew_content: list[dict] | None = None) -> dict:
    """Validates character build against edition rules deterministically, applies corrections, and resynchronizes mechanics."""
    from backend.services.stats_service import sync_character_stats
    from backend.services.validation_service import deterministic_validate_build

    # 1. Deterministic Validation & Corrections
    corrected_char, issues = deterministic_validate_build(char_data)

    # We create a dummy validation result to keep compatibility with any frontend code expecting it
    validation = {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "suggestions": [],
        "corrections": {},
    }

    edition = corrected_char.get("dnd_edition", EDITION_2014)
    # Check if character contains 2024 indicators (masteries, origin feats, etc.)
    if (
        "2024" in str(edition)
        or corrected_char.get("weapon_masteries")
        or any("origin feat" in str(f).lower() for f in corrected_char.get("features_traits", []))
    ):
        edition = "2024 Edition"
        corrected_char["dnd_edition"] = edition

    char_class = corrected_char.get("char_class", "")
    level = corrected_char.get("char_level", 1)

    # Edition 2024 Rule: Subclasses are gained exclusively at Level 3
    if "2024" in edition and level < 3:
        corrected_char["subclass"] = ""

    # Deterministically inject mandatory Class, Subclass, Species/Race, and Background traits
    corrected_char = inject_mandatory_character_grants(
        corrected_char, edition=edition, is_forge=False
    )

    # Re-sync derived stats using mechanics engine for the specific edition
    class_data = _get_rules_repo().get_class_progression(char_class, edition)
    synced_char = sync_character_stats(
        corrected_char, class_data, homebrew_content=homebrew_content
    )

    try:
        validated = CharacterSchema.model_validate(synced_char, strict=False)
        return {"validation_result": validation, "character": validated.model_dump()}
    except Exception as e:
        logger.warning(f"Autofix validation failed: {e}")
        return {"validation_result": validation, "character": synced_char}


def parse_character_from_text(
    sheet_text: str, edition: str = EDITION_2014, homebrew_content: list[dict] | None = None
) -> dict:
    """
    Parses raw text extracted from a D&D Character Sheet PDF into the app's JSON structure.
    Uses a 2-step chained process for maximum precision.
    """
    bounded_text = (sheet_text or "")[:30000]
    fenced_text = f"<document>\n{bounded_text}\n</document>"

    if edition == EDITION_2014 and (
        "2024 player's handbook" in bounded_text.lower()
        or "weapon mastery" in bounded_text.lower()
        or "origin feat" in bounded_text.lower()
    ):
        edition = EDITION_2024

    logger.info(f"Starting Chained Character Parsing (Edition: {edition}, Step 1: Core Stats)...")

    # STEP 1: Core Statistics & Identity
    step1_prompt = PDF_PARSING_STEP1_PROMPT.format(
        edition=edition,
        sheet_text=fenced_text,
    )
    core_data = generate_ai_json(step1_prompt)
    if not isinstance(core_data, dict):
        logger.error("Step 1 of chained parsing failed.")
        return None

    logger.info(f"Step 1 Complete (Name: {core_data.get('char_name')}). Starting Step 2...")

    # STEP 2: Combat, Equipment, Spells & Lore
    step2_prompt = PDF_PARSING_STEP2_PROMPT.format(
        edition=edition,
        core_json=json.dumps(core_data),
        sheet_text=fenced_text,
    )
    combat_data = generate_ai_json(step2_prompt)
    if not isinstance(combat_data, dict):
        logger.warning(
            "Step 2 of chained parsing failed; weapons, equipment and spells will be empty."
        )
        combat_data = {}

    # Allowlist safe merge keys instead of raw dict spread
    allowed_fields = set(CharacterSchema.model_fields.keys()) - {
        "owner_id",
        "active_campaign",
        "char_id",
    }
    merged = {k: v for k, v in core_data.items() if k in allowed_fields}
    for k, v in combat_data.items():
        if k in allowed_fields:
            merged[k] = v
    final_raw = merged
    final_raw["dnd_edition"] = edition

    # Synchronize derived stats according to edition rules
    from backend.services.stats_service import sync_character_stats

    class_data = _get_rules_repo().get_class_progression(final_raw.get("char_class", ""), edition)
    final_raw = sync_character_stats(final_raw, class_data, homebrew_content=homebrew_content)

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
