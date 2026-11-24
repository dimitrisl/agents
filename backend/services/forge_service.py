import functools
import logging
import random
import re
import uuid
from typing import Any

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
from backend.core.subclass_features_2024 import (
    KNOWN_SUBCLASS_FEATURES_2024,
    SUBCLASS_FEATURES_DETAILS_2024,
)
from backend.repositories.rules_repository import RulesRepository
from backend.services.mechanics_service import sync_character_stats
from backend.services.progression_service import (
    check_progression_features,
    get_level_up_vitals,
)
from backend.services.rules_service import (
    autofix_character_build,
    inject_mandatory_character_grants,
)
from backend.services.stats_service import (
    calculate_max_spell_slots,
    strip_derived_character_fields,
)
from backend.services.validation_service import (
    build_feat_lookup,
    deterministic_validate_build,
    get_owned_non_repeatable_feats,
    is_feat_repeatable,
    resolve_known_feat,
    stat_choice_keys_for,
)

logger = logging.getLogger("DnDAssistant.ForgeService")

_STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
_STAT_KEYS = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
_POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
_CLASS_STAT_PRIORITY: dict[str, tuple[str, ...]] = {
    "barbarian": ("STR", "CON", "DEX", "WIS", "CHA", "INT"),
    "bard": ("CHA", "DEX", "CON", "WIS", "INT", "STR"),
    "cleric": ("WIS", "CON", "STR", "DEX", "CHA", "INT"),
    "druid": ("WIS", "CON", "DEX", "INT", "CHA", "STR"),
    "fighter": ("STR", "CON", "DEX", "WIS", "CHA", "INT"),
    "monk": ("DEX", "WIS", "CON", "STR", "INT", "CHA"),
    "paladin": ("STR", "CHA", "CON", "WIS", "DEX", "INT"),
    "ranger": ("DEX", "WIS", "CON", "INT", "STR", "CHA"),
    "rogue": ("DEX", "CON", "INT", "WIS", "CHA", "STR"),
    "sorcerer": ("CHA", "CON", "DEX", "WIS", "INT", "STR"),
    "warlock": ("CHA", "CON", "DEX", "WIS", "INT", "STR"),
    "wizard": ("INT", "CON", "DEX", "WIS", "CHA", "STR"),
    "artificer": ("INT", "CON", "DEX", "WIS", "CHA", "STR"),
}


@functools.lru_cache(maxsize=1)
def _get_rules_repo():
    return RulesRepository()


def _get_class_stat_priority(char_class: str, repo: RulesRepository, edition: str) -> list[str]:
    """Return ordered 6 ability keys tailored to the class's primary abilities."""
    c_low = (char_class or "").strip().lower()
    if c_low in _CLASS_STAT_PRIORITY:
        return list(_CLASS_STAT_PRIORITY[c_low])

    prog = repo.get_class_progression(char_class, edition)
    order: list[str] = []
    if prog:
        for ab in prog.get("primary_ability") or []:
            key = str(ab).strip().upper()[:3]
            if key in _STAT_KEYS and key not in order:
                order.append(key)
    for fallback_key in ("CON", "DEX", "WIS", "STR", "INT", "CHA"):
        if fallback_key not in order:
            order.append(fallback_key)
    return order


def _coerce_stats_dict(raw_stats: Any) -> dict[str, int] | None:
    """Coerce an arbitrary LLM stats dict into 6 integer ability scores, or None if unusable."""
    if not isinstance(raw_stats, dict):
        return None
    alias_map = {
        "STRENGTH": "STR",
        "DEXTERITY": "DEX",
        "CONSTITUTION": "CON",
        "INTELLIGENCE": "INT",
        "WISDOM": "WIS",
        "CHARISMA": "CHA",
    }
    parsed: dict[str, int] = {}
    for k, v in raw_stats.items():
        key = alias_map.get(str(k).strip().upper(), str(k).strip().upper())
        if key not in _STAT_KEYS:
            continue
        try:
            parsed[key] = int(v)
        except (TypeError, ValueError):
            continue
    return parsed if parsed else None


def _is_valid_point_buy(stats: dict[str, int]) -> bool:
    if len(stats) != 6 or any(k not in stats for k in _STAT_KEYS):
        return False
    total = 0
    for k in _STAT_KEYS:
        val = stats[k]
        if val not in _POINT_BUY_COSTS:
            return False
        total += _POINT_BUY_COSTS[val]
    return total == 27


def _assign_array_by_priority(
    scores: list[int],
    raw_stats: dict[str, int] | None,
    priority_order: list[str],
) -> dict[str, int]:
    """Distribute sorted scores using LLM preference rank where valid, else class priority."""
    sorted_scores = sorted((int(x) for x in scores), reverse=True)
    rank_index = {stat: idx for idx, stat in enumerate(priority_order)}
    if raw_stats and len(raw_stats) == 6:
        ordered_stats = sorted(
            _STAT_KEYS,
            key=lambda s: (-raw_stats.get(s, 0), rank_index.get(s, 99)),
        )
    else:
        ordered_stats = priority_order
    return {stat: sorted_scores[idx] for idx, stat in enumerate(ordered_stats)}


_SAVE_ALIAS_MAP: dict[str, str] = {
    "STRENGTH": "STR",
    "DEXTERITY": "DEX",
    "CONSTITUTION": "CON",
    "INTELLIGENCE": "INT",
    "WISDOM": "WIS",
    "CHARISMA": "CHA",
}


_FULL_HALF_PACT_CASTERS = frozenset(
    {
        "bard",
        "cleric",
        "druid",
        "paladin",
        "ranger",
        "sorcerer",
        "warlock",
        "wizard",
        "artificer",
    }
)
_SPELL_SWAP_CASTERS = frozenset({"bard", "ranger", "sorcerer", "warlock"})


def _norm_spell_key(name: Any) -> str:
    return str(name or "").strip().lower().replace("\u2019", "'").replace("\u2018", "'")


def resolve_spell_list_class(class_name: str, subclass_name: str | None = None) -> str | None:
    """Resolve the spell-list class name (mapping 1/3 casters EK & AT to wizard)."""
    c_low = str(class_name or "").strip().lower()
    sub_low = str(subclass_name or "").strip().lower()
    if (c_low == "fighter" and "eldritch knight" in sub_low) or (
        c_low == "rogue" and "arcane trickster" in sub_low
    ):
        return "wizard"
    return c_low if c_low in _FULL_HALF_PACT_CASTERS else None


def supports_level_up_spell_swap(class_name: str, subclass_name: str | None = None) -> bool:
    """True for known/level-up-swap spellcasters (Bard, Ranger, Sorcerer, Warlock, EK, AT)."""
    c_low = str(class_name or "").strip().lower()
    sub_low = str(subclass_name or "").strip().lower()
    return c_low in _SPELL_SWAP_CASTERS or (
        (c_low == "fighter" and "eldritch knight" in sub_low)
        or (c_low == "rogue" and "arcane trickster" in sub_low)
    )


def _collect_protected_spell_keys(
    char_data: dict,
    target_class: str,
    subclass_to_use: str | None,
    target_level: int,
    edition: str,
    rules_repo,
) -> set[str]:
    """Return normalized names of always-prepared subclass & innate racial spells."""
    protected: set[str] = set()
    classes = list(char_data.get("classes") or [])
    if not classes and char_data.get("char_class"):
        classes = [
            {
                "class_name": char_data.get("char_class"),
                "level": char_data.get("char_level", 1),
                "subclass": char_data.get("subclass"),
            }
        ]

    seen_target = False
    for cls in classes:
        if not isinstance(cls, dict):
            continue
        c_name = str(cls.get("class_name") or "").strip()
        if not c_name:
            continue
        is_target = c_name.lower() == target_class.lower()
        c_sub = (subclass_to_use or cls.get("subclass")) if is_target else cls.get("subclass")
        c_lvl = target_level if is_target else int(cls.get("level") or 1)
        if is_target:
            seen_target = True
        if c_sub:
            sub_entry = rules_repo.get_subclass_entry(c_name, c_sub, edition)
            for lvl_k, sp_names in ((sub_entry or {}).get("bonus_spells") or {}).items():
                try:
                    req_lvl = int(lvl_k)
                except (TypeError, ValueError):
                    continue
                if c_lvl >= req_lvl:
                    for raw_sp in sp_names or []:
                        key = _norm_spell_key(raw_sp)
                        if key:
                            protected.add(key)

    if not seen_target and subclass_to_use:
        sub_entry = rules_repo.get_subclass_entry(target_class, subclass_to_use, edition)
        for lvl_k, sp_names in ((sub_entry or {}).get("bonus_spells") or {}).items():
            try:
                req_lvl = int(lvl_k)
            except (TypeError, ValueError):
                continue
            if target_level >= req_lvl:
                for raw_sp in sp_names or []:
                    key = _norm_spell_key(raw_sp)
                    if key:
                        protected.add(key)

    def _extract_innate_block(block: Any, current_char_level: int) -> None:
        if not isinstance(block, dict):
            return
        by_lvl = block.get("by_level")
        if isinstance(by_lvl, dict):
            for lvl_k, sp_names in by_lvl.items():
                try:
                    req_l = int(lvl_k)
                except (TypeError, ValueError):
                    continue
                if current_char_level >= req_l and isinstance(sp_names, list):
                    for raw_sp in sp_names:
                        key = _norm_spell_key(raw_sp)
                        if key:
                            protected.add(key)
        for k, val in block.items():
            if (k == "always" or str(k).startswith("level_") or str(k).isdigit()) and isinstance(
                val, list
            ):
                for raw_sp in val:
                    key = _norm_spell_key(raw_sp)
                    if key:
                        protected.add(key)

    char_total_level = max(1, int(char_data.get("char_level") or 1))
    race_name = str(char_data.get("race") or "").strip()
    race_data = rules_repo.get_race_data(race_name, edition) if race_name else None
    innate = (race_data or {}).get("innate_spells")
    if isinstance(innate, dict):
        _extract_innate_block(innate, char_total_level)

    lineage_map = (race_data or {}).get("lineage_spells")
    if isinstance(lineage_map, dict) and lineage_map:
        sorted_lineages = [
            (lin_key, blk)
            for lin_key, blk in sorted(lineage_map.items(), key=lambda kv: len(kv[0]), reverse=True)
            if lin_key != "_default" and isinstance(blk, dict)
        ]

        def _match_lineage_text(text: str) -> dict | None:
            lowered = text.lower()
            return next(
                (blk for lin_key, blk in sorted_lineages if lin_key.lower() in lowered),
                None,
            )

        # Match specific subrace/lineage in race name first, then trait names, then
        # unambiguous trait descriptions (skipping multi-option 2024 PHB prompt text).
        matched_lineage = _match_lineage_text(race_name)
        if matched_lineage is None:
            trait_names = " ".join(
                f.get("name", "") if isinstance(f, dict) else str(f or "").split(":", 1)[0]
                for f in (char_data.get("features_traits") or [])
            )
            matched_lineage = _match_lineage_text(trait_names)
        if matched_lineage is None:
            for feat in char_data.get("features_traits") or []:
                desc = (
                    (feat.get("description") or "") if isinstance(feat, dict) else str(feat or "")
                ).lower()
                if not desc or "choose " in desc:
                    continue
                hits = [blk for lin_key, blk in sorted_lineages if lin_key.lower() in desc]
                distinct_signatures = {
                    tuple(sorted((str(k), str(v)) for k, v in blk.items())) for blk in hits
                }
                if len(distinct_signatures) == 1:
                    matched_lineage = hits[0]
                    break
        if matched_lineage is None:
            matched_lineage = lineage_map.get("_default")
        if isinstance(matched_lineage, dict):
            _extract_innate_block(matched_lineage, char_total_level)

    if race_name and not isinstance(innate, dict) and not isinstance(lineage_map, dict):
        fallback_race = rules_repo.get_race_data(race_name, "2014")
        fallback_innate = (fallback_race or {}).get("innate_spells")
        if isinstance(fallback_innate, dict):
            _extract_innate_block(fallback_innate, char_total_level)

    return protected


def get_spell_swap_candidates(
    char_data: dict,
    target_class: str,
    subclass_to_use: str | None,
    target_level: int,
    max_spell_level: int,
    edition: str,
    rules_repo,
    all_spells: list[dict] | None = None,
) -> tuple[list[str], set[str]]:
    """Return (replaceable_leveled_spells, protected_keys) for an eligible Level-Up swap."""
    if (
        not supports_level_up_spell_swap(target_class, subclass_to_use)
        or max_spell_level < 1
        or target_level < 2
    ):
        return [], set()

    spell_list_class = resolve_spell_list_class(target_class, subclass_to_use)
    if not spell_list_class:
        return [], set()

    all_spells = all_spells if all_spells is not None else rules_repo.get_all_spells(edition)
    spells_by_norm = {
        _norm_spell_key(s.get("name")): s
        for s in all_spells
        if isinstance(s, dict) and s.get("name")
    }
    protected = _collect_protected_spell_keys(
        char_data, target_class, subclass_to_use, target_level, edition, rules_repo
    )

    sp_dict = char_data.get("spells") or {}
    if not isinstance(sp_dict, dict):
        return [], protected

    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for lvl_idx in range(1, 10):
        bucket = sp_dict.get(f"level_{lvl_idx}")
        if not isinstance(bucket, list):
            continue
        for entry in bucket:
            raw_name = entry.get("name") if isinstance(entry, dict) else str(entry or "")
            clean_name = str(raw_name).strip()
            norm_key = _norm_spell_key(clean_name)
            if not clean_name or norm_key in seen or norm_key in protected:
                continue
            catalog_sp = spells_by_norm.get(norm_key)
            if catalog_sp is not None:
                sp_lvl = int(catalog_sp.get("level", 0) or 0)
                sp_classes = [str(c).lower() for c in (catalog_sp.get("classes") or [])]
                if sp_lvl < 1 or sp_lvl > max_spell_level:
                    continue
                if sp_classes and spell_list_class not in sp_classes:
                    continue
                candidates.append((sp_lvl, str(catalog_sp.get("name") or clean_name)))
            else:
                if lvl_idx > max_spell_level:
                    continue
                candidates.append((lvl_idx, clean_name))
            seen.add(norm_key)

    candidates.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _, name in candidates], protected


def apply_level_up_spell_swap(
    char_doc: dict,
    pre_level_spells: Any,
    target_class: str,
    chosen_subclass: str | None,
    new_class_level: int,
    swap_out: str,
    swap_in: str,
    selected_spells_in_payload: set[str],
    edition: str,
    rules_repo,
    pre_total_level: int | None = None,
) -> None:
    """Validate and apply an optional 1-for-1 leveled spell replacement on Level Up."""
    clean_out = str(swap_out or "").strip()
    clean_in = str(swap_in or "").strip()
    if not clean_out and not clean_in:
        return
    if bool(clean_out) != bool(clean_in):
        raise ValueError(
            "Both a spell to replace and a replacement spell must be selected to swap spells."
        )

    spell_list_class = resolve_spell_list_class(target_class, chosen_subclass)
    if not spell_list_class or not supports_level_up_spell_swap(target_class, chosen_subclass):
        raise ValueError(f"{target_class} does not support spell swapping on Level Up.")

    from backend.services.stats_service import calculate_max_spell_slots

    max_slots = calculate_max_spell_slots(
        target_class, new_class_level, chosen_subclass, edition=edition
    )
    max_spell_level = max(
        (i for i in range(1, 10) if max_slots.get(f"level_{i}", 0) > 0),
        default=0,
    )
    if max_spell_level < 1 or new_class_level < 2:
        raise ValueError("Character does not have eligible spell slots for spell swapping.")

    all_spells = rules_repo.get_all_spells(edition)
    snapshot = dict(char_doc)
    snapshot["spells"] = pre_level_spells
    if pre_total_level is not None:
        snapshot["char_level"] = pre_total_level
    candidates, protected = get_spell_swap_candidates(
        snapshot,
        target_class,
        chosen_subclass,
        new_class_level,
        max_spell_level,
        edition,
        rules_repo,
        all_spells=all_spells,
    )

    out_norm = _norm_spell_key(clean_out)
    if out_norm in protected:
        raise ValueError(
            f"Subclass or innate trait spell '{clean_out}' cannot be replaced during Level Up."
        )
    if not any(_norm_spell_key(c) == out_norm for c in candidates):
        raise ValueError(
            f"Spell '{clean_out}' is not an eligible known spell to replace on Level Up."
        )

    in_norm = _norm_spell_key(clean_in)
    if in_norm == out_norm:
        raise ValueError("Replacement spell must differ from the spell being replaced.")
    if in_norm in selected_spells_in_payload:
        raise ValueError(
            f"Duplicate spell selection '{clean_in}': already chosen for this Level Up."
        )

    matched_in = next(
        (
            s
            for s in all_spells
            if isinstance(s, dict) and s.get("name") and _norm_spell_key(s["name"]) == in_norm
        ),
        None,
    )
    if matched_in is None:
        raise ValueError(f"Unknown replacement spell '{clean_in}' for {edition}.")

    in_level = int(matched_in.get("level", 0) or 0)
    if in_level < 1 or in_level > max_spell_level:
        raise ValueError(
            f"Replacement spell '{matched_in['name']}' (Level {in_level}) exceeds maximum castable spell level ({max_spell_level})."
        )
    in_classes = [str(c).lower() for c in (matched_in.get("classes") or [])]
    if in_classes and spell_list_class not in in_classes:
        raise ValueError(
            f"Replacement spell '{matched_in['name']}' is not on the {spell_list_class.title()} spell list."
        )

    pre_known: set[str] = set()
    if isinstance(pre_level_spells, dict):
        for lst in pre_level_spells.values():
            if isinstance(lst, list):
                for s in lst:
                    pre_known.add(_norm_spell_key(s.get("name") if isinstance(s, dict) else s))
    if in_norm in pre_known:
        raise ValueError(f"Character already knows replacement spell '{matched_in['name']}'.")

    def _entry_key(entry: Any) -> str:
        return _norm_spell_key(entry.get("name") if isinstance(entry, dict) else entry)

    # Perform replacement across spells buckets and prepared_spells
    spells_dict = char_doc.setdefault("spells", {})
    if isinstance(spells_dict, dict):
        for lvl_idx in range(1, 10):
            key = f"level_{lvl_idx}"
            if isinstance(spells_dict.get(key), list):
                spells_dict[key] = [s for s in spells_dict[key] if _entry_key(s) != out_norm]
        canon_in = str(matched_in.get("name") or clean_in)
        target_bucket = spells_dict.setdefault(f"level_{in_level}", [])
        if not any(_entry_key(x) == _norm_spell_key(canon_in) for x in target_bucket):
            target_bucket.append(canon_in)

    prep_list = char_doc.get("prepared_spells")
    if isinstance(prep_list, list):
        filtered_prep = [p for p in prep_list if _entry_key(p) != out_norm]
    else:
        filtered_prep = []
    canon_in = str(matched_in.get("name") or clean_in)
    if not any(_entry_key(p) == _norm_spell_key(canon_in) for p in filtered_prep):
        filtered_prep.append(canon_in)
    char_doc["prepared_spells"] = filtered_prep


def _extract_resilient_stat(feat_label: str) -> str | None:
    """Parse explicit stat from e.g. 'Resilient (WIS)' or 'Resilient (Wisdom)'."""
    m = re.search(
        r"\(\s*(STR(?:ENGTH)?|DEX(?:TERITY)?|CON(?:STITUTION)?|INT(?:ELLIGENCE)?|WIS(?:DOM)?|CHA(?:RISMA)?)\s*\)",
        str(feat_label or ""),
        re.I,
    )
    if not m:
        return None
    tok = m.group(1).strip().upper()
    return _SAVE_ALIAS_MAP.get(tok, tok[:3])


def _seed_class_saving_throws(
    raw_saves: list | None,
    char_class: str,
    repo: RulesRepository,
    edition: str,
) -> list[str]:
    """Normalize existing saving throws, seeding base class saves from RulesRepository when empty."""
    source = raw_saves
    if not source and char_class:
        c_prog = repo.get_class_progression(char_class, edition) or {}
        source = (c_prog.get("starting_proficiencies") or {}).get("saving_throws") or []
    out: list[str] = []
    for s in source or []:
        up = str(s or "").strip().upper()
        if not up:
            continue
        code = _SAVE_ALIAS_MAP.get(up, up[:3])
        if code in _STAT_KEYS and code not in out:
            out.append(code)
    return out


def _enforce_deterministic_forge_stats(
    char_data: dict,
    char_class: str,
    race: str,
    background: str,
    target_level: int,
    edition: str,
    stats_mode: str,
    rolled_stats: list[int] | None,
    auto_feats: bool,
    repo: RulesRepository,
) -> None:
    """Enforce legal base stats (Standard Array / Point Buy / Rolled), 2014/2024 bonuses, and ASIs."""
    is_2024 = "2024" in str(edition or "")
    priority_order = _get_class_stat_priority(char_class, repo, edition)
    raw_stats = _coerce_stats_dict(char_data.get("stats"))

    if stats_mode == "rolled" and rolled_stats and len(rolled_stats) == 6:
        target_sorted = sorted(rolled_stats, reverse=True)
        if raw_stats and sorted(raw_stats.values(), reverse=True) == target_sorted:
            base = {k: raw_stats[k] for k in _STAT_KEYS}
        else:
            base = _assign_array_by_priority(target_sorted, raw_stats, priority_order)
    elif stats_mode == "point_buy":
        if raw_stats and _is_valid_point_buy(raw_stats):
            base = {k: raw_stats[k] for k in _STAT_KEYS}
        else:
            base = _assign_array_by_priority(_STANDARD_ARRAY, raw_stats, priority_order)
    else:
        if raw_stats and sorted(raw_stats.values(), reverse=True) == _STANDARD_ARRAY:
            base = {k: raw_stats[k] for k in _STAT_KEYS}
        else:
            base = _assign_array_by_priority(_STANDARD_ARRAY, raw_stats, priority_order)

    # Apply edition-specific origin ability bonuses deterministically
    if is_2024:
        bg_data = repo.get_background_data(background, edition) or {}
        ab_cfg = bg_data.get("ability_scores") or {}
        options_groups = ab_cfg.get("options") or []
        allowed_pool = (
            [str(x).strip().upper()[:3] for x in options_groups[0]]
            if options_groups and isinstance(options_groups[0], list)
            else []
        )
        valid_pool = [s for s in priority_order if s in allowed_pool]
        if len(valid_pool) >= 2:
            base[valid_pool[0]] = min(20, base[valid_pool[0]] + 2)
            base[valid_pool[1]] = min(20, base[valid_pool[1]] + 1)
        elif len(valid_pool) == 1:
            base[valid_pool[0]] = min(20, base[valid_pool[0]] + 2)
    else:
        race_data = repo.get_race_data(race, edition) or {}
        stat_bonuses = race_data.get("stat_bonuses") or {}
        if isinstance(stat_bonuses, dict):
            chosen_flex_stats: set[str] = set()
            for k, bonus in stat_bonuses.items():
                key = str(k).strip().upper()[:3]
                if key in base:
                    base[key] = min(20, base[key] + int(bonus or 0))
                    chosen_flex_stats.add(key)
                elif key == "CHO" or str(k).strip().lower() in ("choice", "any", "flex"):
                    for p in priority_order:
                        if p not in stat_bonuses and p not in chosen_flex_stats:
                            base[p] = min(20, base[p] + int(bonus or 0))
                            chosen_flex_stats.add(p)
                            break

    # Apply deterministic Level >= 4 ASI / Epic Boon advancements
    def _safe_adv_level(raw_lvl: Any) -> int:
        if raw_lvl is None or isinstance(raw_lvl, bool):
            return 0
        if isinstance(raw_lvl, (int, float)):
            return int(raw_lvl)
        match = re.match(r"^\s*(\d+)", str(raw_lvl))
        return int(match.group(1)) if match else 0

    def _sync_feat_to_traits(feat_obj: dict) -> None:
        feat_name = str(feat_obj.get("name") or "").strip()
        if not feat_name:
            return
        features_list = char_data.setdefault("features_traits", [])
        if not isinstance(features_list, list):
            features_list = []
            char_data["features_traits"] = features_list
        feat_low = feat_name.lower()
        for existing in features_list:
            if not isinstance(existing, dict):
                continue
            ex_name = str(existing.get("name") or "").strip().lower()
            ex_clean = ex_name.removeprefix("origin feat: ").removeprefix("feat: ").strip()
            if ex_clean == feat_low:
                return
        features_list.append(
            {
                "name": f"Feat: {feat_name}",
                "description": str(feat_obj.get("description") or "").strip(),
                "source": "Feat",
            }
        )

    asi_levels: list[int] = []
    if auto_feats and target_level >= 4:
        for lvl in range(1, target_level + 1):
            prog = check_progression_features(char_class, lvl, edition)
            if prog.get("is_asi_level"):
                asi_levels.append(lvl)

    cleaned_advs: list[dict] = []
    if auto_feats and asi_levels:
        all_feats = {
            f["name"].lower(): f
            for f in repo.get_all_feats(edition)
            if isinstance(f, dict)
            and "name" in f
            and f["name"].strip().lower() != "ability score improvement"
        }
        raw_advs = [
            a
            for a in (char_data.get("advancements") or [])
            if isinstance(a, dict)
            and str(a.get("type") or "").strip().lower() == "feat"
            and _safe_adv_level(a.get("level")) != 1
        ]
        consumed_adv_indices: set[int] = set()
        used_feat_names: set[str] = set()
        for asi_lvl in asi_levels:
            stat_cap = 30 if (is_2024 and asi_lvl >= 19) else 20
            picked_feat = None

            # Prefer explicit level match first, otherwise next unused feat entry <= asi_lvl
            candidate_indices = [
                i
                for i, a in enumerate(raw_advs)
                if i not in consumed_adv_indices and _safe_adv_level(a.get("level")) == asi_lvl
            ] + [
                i
                for i, a in enumerate(raw_advs)
                if i not in consumed_adv_indices
                and _safe_adv_level(a.get("level")) in (0, *range(2, asi_lvl + 1))
            ]

            for idx in candidate_indices:
                cand_name = str(raw_advs[idx].get("name") or "").strip()
                cand_low = cand_name.lower()
                if not cand_low or cand_low == "ability score improvement":
                    consumed_adv_indices.add(idx)
                    break
                cand_base_low = re.sub(r"\s*\([^)]*\)\s*$", "", cand_low).strip()
                f_obj = all_feats.get(cand_low) or all_feats.get(cand_base_low)
                if not f_obj or f_obj["name"].lower() in used_feat_names:
                    continue
                prereqs = f_obj.get("prerequisites") or {}
                min_req_lvl = _safe_adv_level(prereqs.get("min_level"))
                if min_req_lvl > asi_lvl:
                    continue
                picked_feat = f_obj
                consumed_adv_indices.add(idx)
                break

            if picked_feat:
                used_feat_names.add(picked_feat["name"].lower())
                for sk, bv in (picked_feat.get("stat_bonus") or {}).items():
                    if bv and sk in base:
                        base[sk] = min(stat_cap, base[sk] + int(bv))
                if picked_feat.get("has_stat_choice"):
                    allowed_opts = {
                        str(opt).strip().upper()[:3]
                        for opt in (picked_feat.get("stat_choice_options") or [])
                        if str(opt).strip()
                    }
                    is_resilient = picked_feat["name"].strip().lower() == "resilient"
                    explicit_save = _extract_resilient_stat(cand_name) if is_resilient else None
                    search_order = [
                        s for s in priority_order if not allowed_opts or s in allowed_opts
                    ]
                    for s in _STAT_KEYS:
                        if (not allowed_opts or s in allowed_opts) and s not in search_order:
                            search_order.append(s)
                    seeded_saves: list[str] = []
                    if is_resilient:
                        seeded_saves = _seed_class_saving_throws(
                            char_data.get("saving_throws"), char_class, repo, edition
                        )
                        existing_saves = set(seeded_saves)
                        # Prefer CON/WIS/DEX non-proficient saves for Resilient unless explicitly requested
                        non_prof = [
                            s
                            for s in (["CON", "WIS", "DEX"] + search_order)
                            if (not allowed_opts or s in allowed_opts) and s not in existing_saves
                        ]
                        search_order = (
                            ([explicit_save] if explicit_save else []) + non_prof + search_order
                        )
                        search_order = list(dict.fromkeys(search_order))
                    chosen_choice_stat = None
                    for p in search_order:
                        if base[p] < stat_cap:
                            base[p] = min(stat_cap, base[p] + 1)
                            chosen_choice_stat = p
                            break
                    if is_resilient:
                        resilient_stat = explicit_save or chosen_choice_stat
                        if resilient_stat and resilient_stat not in seeded_saves:
                            seeded_saves.append(resilient_stat)
                        if seeded_saves:
                            char_data["saving_throws"] = seeded_saves
                _sync_feat_to_traits(picked_feat)
                cleaned_advs.append(
                    {
                        "level": asi_lvl,
                        "type": "Feat",
                        "name": picked_feat["name"],
                        "description": str(picked_feat.get("description") or "")[:200],
                    }
                )
            else:
                remaining_points = 2
                applied_parts: list[str] = []
                for p in priority_order:
                    if remaining_points <= 0:
                        break
                    room = stat_cap - base[p]
                    if room > 0:
                        delta = min(remaining_points, room)
                        base[p] += delta
                        remaining_points -= delta
                        applied_parts.append(f"+{delta} {p}")
                if applied_parts:
                    title = (
                        f"Epic Boon ({', '.join(applied_parts)})"
                        if (is_2024 and asi_lvl >= 19)
                        else f"Ability Score Improvement ({', '.join(applied_parts)})"
                    )
                    cleaned_advs.append(
                        {
                            "level": asi_lvl,
                            "type": "ASI",
                            "name": title,
                            "description": f"Deterministic level {asi_lvl} increase: {', '.join(applied_parts)}",
                        }
                    )

    if is_2024:
        # Preserve any level 1 Origin Feat entries so inject_mandatory_character_grants doesn't duplicate
        origin_advs = []
        for a in char_data.get("advancements") or []:
            if isinstance(a, dict) and _safe_adv_level(a.get("level")) == 1:
                adv_name = str(a.get("name") or "").strip()
                origin_advs.append(
                    {
                        "level": 1,
                        "type": str(a.get("type") or "Feat").strip() or "Feat",
                        "name": adv_name or "Origin Feat",
                        "description": str(a.get("description") or "").strip() or adv_name,
                    }
                )
        char_data["advancements"] = origin_advs + cleaned_advs
    elif auto_feats:
        char_data["advancements"] = cleaned_advs

    overall_cap = 30 if (is_2024 and target_level >= 19) else 20

    # Level 20 Class Stat Capstones (Primal Champion / Body and Mind)
    c_low = (char_class or "").strip().lower()
    if target_level >= 20:
        if c_low == "barbarian":
            champ_cap = 25 if is_2024 else 24
            base["STR"] = min(champ_cap, base["STR"] + 4)
            base["CON"] = min(champ_cap, base["CON"] + 4)
            overall_cap = max(overall_cap, champ_cap)
        elif c_low == "monk" and is_2024:
            base["DEX"] = min(25, base["DEX"] + 4)
            base["WIS"] = min(25, base["WIS"] + 4)
            overall_cap = max(overall_cap, 25)

    char_data["stats"] = {k: max(1, min(overall_cap, int(base[k]))) for k in _STAT_KEYS}


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

    if stats_mode != "rolled":
        rolled_stats = None

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
    if not isinstance(result, dict) or not result:
        logger.warning("AI JSON generation returned None. Generating default fallback character.")
        result = get_default_character()
        resolved_fb_class = forge_class if forge_class != "AI Choice" else "Fighter"
        fb_priority = _get_class_stat_priority(resolved_fb_class, repo, edition)
        result.update(
            {
                "char_name": name if name != "AI Choice" else "Forged Hero",
                "gender": gender if gender != "AI Choice" else "Male",
                "char_class": resolved_fb_class,
                "subclass": subclass if subclass and subclass != "AI Choice" else None,
                "char_level": target_level,
                "race": forge_race if forge_race != "AI Choice" else "Human",
                "background": forge_background if forge_background != "AI Choice" else "Soldier",
                "alignment": alignment if alignment != "AI Choice" else "True Neutral",
                "stats": _assign_array_by_priority(_STANDARD_ARRAY, None, fb_priority),
                "concept": concept or "",
                "dnd_edition": edition,
            }
        )

    # Enforce explicit user selections and strip any LLM-computed derived numbers
    if name != "AI Choice":
        result["char_name"] = name
    if gender != "AI Choice":
        result["gender"] = gender
    if forge_race != "AI Choice":
        result["race"] = forge_race
    if forge_class != "AI Choice":
        result["char_class"] = forge_class
    elif not str(result.get("char_class") or "").strip():
        result["char_class"] = "Fighter"
    if forge_background != "AI Choice":
        result["background"] = forge_background
    if alignment != "AI Choice":
        result["alignment"] = alignment
    if subclass and subclass != "AI Choice":
        result["subclass"] = subclass
    result["char_level"] = max(1, min(20, int(target_level)))
    result["dnd_edition"] = edition

    strip_derived_character_fields(result, strip_hp=True, strip_weapon_bonuses=True)

    is_2024 = "2024" in str(edition or "")
    resolved_class = str(result.get("char_class") or "Fighter").strip()
    if not result.get("subclass"):
        sub_unlock = 3
        if not is_2024:
            if resolved_class.title() in ("Cleric", "Sorcerer", "Warlock"):
                sub_unlock = 1
            elif resolved_class.title() in ("Wizard", "Druid"):
                sub_unlock = 2
        if result["char_level"] >= sub_unlock:
            avail_subs = repo.get_subclasses(resolved_class, edition)
            if avail_subs:
                result["subclass"] = avail_subs[0]

    _enforce_deterministic_forge_stats(
        result,
        char_class=resolved_class,
        race=str(result.get("race") or "Human"),
        background=str(result.get("background") or "Soldier"),
        target_level=result["char_level"],
        edition=edition,
        stats_mode=stats_mode,
        rolled_stats=rolled_stats,
        auto_feats=auto_feats,
        repo=repo,
    )

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

    # Deterministically inject mandatory Class, Subclass, Species/Race, and Background grants
    result = inject_mandatory_character_grants(
        result,
        edition=edition,
        is_forge=True,
        auto_feats=auto_feats,
        auto_spells=auto_spells,
    )

    # Synchronize derived stats (HP, AC, Proficiency, etc.) deterministically
    class_data = _get_rules_repo().get_class_progression(result.get("char_class"), edition)
    result = sync_character_stats(result, class_data)
    result["hp_current"] = result.get("hp_max", 10)

    # D&D Rules Autofix & Deep Validation
    try:
        autofix_result = autofix_character_build(result)
        result = autofix_result.get("character", result)
        result["hp_current"] = result.get("hp_max", 10)
    except Exception as e:
        logger.error(f"Rule autofix failed during AI forge: {e}")

    # Mandatory Schema & Build Validation
    if not isinstance(result, dict):
        result = {}
    try:
        validated = CharacterSchema.model_validate(result, strict=False)
        return validated.model_dump()
    except Exception as e:
        logger.warning(
            f"Forged character failed initial validation: {e}. Returning sanitized default character."
        )

        fallback = get_default_character()
        for k in (
            "char_name",
            "char_class",
            "race",
            "background",
            "alignment",
            "gender",
            "dnd_edition",
            "subclass",
        ):
            v = result.get(k)
            if isinstance(v, str) and v.strip():
                fallback[k] = v.strip()
        fallback["char_level"] = max(1, min(20, int(target_level)))
        fallback = inject_mandatory_character_grants(
            fallback,
            edition=edition,
            is_forge=True,
            auto_feats=auto_feats,
            auto_spells=auto_spells,
        )
        fb_class_data = _get_rules_repo().get_class_progression(fallback.get("char_class"), edition)
        fallback = sync_character_stats(fallback, fb_class_data)
        fallback["hp_current"] = fallback.get("hp_max", 10)
        return CharacterSchema.model_validate(fallback, strict=False).model_dump()


def validate_manual_class_choices(
    chosen_class_choices: list | None,
    char_class: str,
    target_level: int,
    subclass: str | None = None,
    edition: str = EDITION_2014,
    repo=None,
) -> list[dict[str, str]]:
    """
    Strictly validate and resolve manual-forge `chosen_class_choices` against an
    edition-, class-, subclass-, and level-scoped allow-list from `class_choices_<ed>.json`.
    Raises ValueError on any cross-class, over-level, duplicate, mutually exclusive,
    unmet-prerequisite, or arbitrary non-catalog entry.
    """
    if not chosen_class_choices:
        return []
    if not isinstance(chosen_class_choices, list):
        raise ValueError("chosen_class_choices must be a list of choice names.")

    from backend.repositories.rules_repository import RulesRepository

    rules_repo = repo or RulesRepository()
    choices_catalog = rules_repo.get_class_choices(edition) or {}
    is_2024 = "2024" in str(edition or "")
    c_lower = str(char_class or "").strip().lower()
    sub_lower = str(subclass or "").strip().lower()
    lvl = max(1, int(target_level or 1))

    allowed: dict[str, dict] = {}

    def _register(items, bucket_name: str, check_min_level: bool = False):
        for it in items or []:
            if not isinstance(it, dict) or not it.get("name"):
                continue
            if check_min_level and int(it.get("min_level", 1) or 1) > lvl:
                continue
            name_clean = str(it["name"]).strip()
            allowed[name_clean.lower()] = {
                "name": name_clean,
                "description": str(it.get("description") or "").strip(),
                "bucket": bucket_name,
                "pact": str(it.get("pact") or "").strip().lower() or None,
                "requires_invocation": str(it.get("requires_invocation") or "").strip().lower()
                or None,
            }

    if is_2024 and c_lower == "cleric":
        _register(choices_catalog.get("divine_orders"), "divine_order")
    if is_2024 and c_lower == "druid":
        _register(choices_catalog.get("primal_orders"), "primal_order")
    if (c_lower == "fighter" and lvl >= 1) or (c_lower in ("paladin", "ranger") and lvl >= 2):
        _register(
            (choices_catalog.get("fighting_styles") or {}).get(c_lower),
            "fighting_style",
        )
    if not is_2024 and c_lower == "warlock" and lvl >= 3:
        _register(choices_catalog.get("pact_boons"), "pact_boon")
    if c_lower == "warlock" and lvl >= (1 if is_2024 else 2):
        _register(
            choices_catalog.get("eldritch_invocations"),
            "eldritch_invocation",
            check_min_level=True,
        )
    if c_lower == "sorcerer" and lvl >= (2 if is_2024 else 3):
        _register(choices_catalog.get("metamagic"), "metamagic")
    if c_lower == "fighter" and "battle master" in sub_lower and lvl >= 3:
        _register(choices_catalog.get("maneuvers"), "maneuver")
    if c_lower == "artificer" and lvl >= 2:
        _register(
            choices_catalog.get("artificer_infusions"),
            "artificer_infusion",
            check_min_level=True,
        )
    if c_lower == "ranger" and "hunter" in sub_lower:
        for tier_str, tier_items in (choices_catalog.get("hunter_choices") or {}).items():
            try:
                if int(tier_str) <= lvl:
                    _register(tier_items, f"hunter_choice_{tier_str}")
            except (TypeError, ValueError):
                continue

    resolved: list[dict] = []
    seen_names: set[str] = set()
    bucket_counts: dict[str, int] = {}

    # Compute exact class-, subclass-, level-, and edition-scoped cardinality caps
    inv_schedule = (
        {1: 1, 2: 2, 5: 2, 7: 1, 9: 1, 12: 1, 15: 1, 18: 1}
        if is_2024
        else {2: 2, 5: 1, 7: 1, 9: 1, 12: 1, 15: 1, 18: 1}
    )
    mm_schedule = {2: 2, 10: 2, 17: 2} if is_2024 else {3: 2, 10: 1, 17: 1}
    bm_schedule = {3: 3, 7: 2, 10: 2, 15: 2}
    inf_schedule = {2: 4, 6: 2, 10: 2, 14: 2, 18: 2}
    champ_extra_style_lvl = 7 if is_2024 else 10
    max_fighting_styles = (
        2
        if (c_lower == "fighter" and "champion" in sub_lower and lvl >= champ_extra_style_lvl)
        else 1
    )

    bucket_limits: dict[str, int] = {
        "divine_order": 1,
        "primal_order": 1,
        "pact_boon": 1,
        "fighting_style": max_fighting_styles,
        "eldritch_invocation": sum(cnt for req_l, cnt in inv_schedule.items() if req_l <= lvl),
        "metamagic": sum(cnt for req_l, cnt in mm_schedule.items() if req_l <= lvl),
        "maneuver": sum(cnt for req_l, cnt in bm_schedule.items() if req_l <= lvl),
        "artificer_infusion": sum(cnt for req_l, cnt in inf_schedule.items() if req_l <= lvl),
    }

    for raw in chosen_class_choices:
        if not isinstance(raw, str):
            raise ValueError("Invalid class choice entry: expected string.")
        clean = raw.strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen_names:
            raise ValueError(f"Duplicate class choice '{clean}'.")
        entry = allowed.get(key)
        if not entry:
            raise ValueError(
                f"Class choice '{clean}' is not permitted for a Level {lvl} {char_class} ({edition})."
            )
        bucket = entry["bucket"]
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        max_for_bucket = 1 if bucket.startswith("hunter_choice_") else bucket_limits.get(bucket, 1)
        if bucket_counts[bucket] > max_for_bucket:
            raise ValueError(
                f"Too many selections for '{bucket.replace('_', ' ')}' at Level {lvl} "
                f"(maximum {max_for_bucket} allowed, got '{entry['name']}')."
            )
        seen_names.add(key)
        resolved.append(entry)

    # Validate invocation prerequisites (pact / requires_invocation)
    selected_low = {item["name"].lower() for item in resolved}
    for item in resolved:
        if item["pact"] and item["pact"] not in selected_low:
            raise ValueError(f"Class choice '{item['name']}' requires '{item['pact'].title()}'.")
        if item["requires_invocation"] and item["requires_invocation"] not in selected_low:
            raise ValueError(
                f"Class choice '{item['name']}' requires '{item['requires_invocation'].title()}'."
            )

    return [{"name": it["name"], "description": it["description"]} for it in resolved]


def _build_level_up_order_choices(
    is_2024: bool,
    c_lower: str,
    target_level: int,
    owned_ft_low: set[str],
    choices_catalog: dict,
) -> list[dict[str, Any]]:
    """Build 2024 Level 1 Divine/Primal Order choices (emitted BEFORE spells so index stays stable)."""
    order_choices: list[dict[str, Any]] = []
    # 2024 Cleric Level 1: Divine Order (Protector vs Thaumaturge)
    has_concrete_divine_order = any(
        ("protector" in fn and "thaumaturge" not in fn and ("divine" in fn or fn == "protector"))
        or ("thaumaturge" in fn and "protector" not in fn)
        for fn in owned_ft_low
    )
    if is_2024 and c_lower == "cleric" and target_level == 1 and not has_concrete_divine_order:
        order_opts = [
            opt["name"] for opt in (choices_catalog.get("divine_orders") or []) if opt.get("name")
        ]
        if order_opts:
            order_choices.append(
                {
                    "type": "divine_order",
                    "label": "Choose your Divine Order",
                    "options": order_opts,
                    "ai_recommendation": "Protector grants Heavy Armor & Martial Weapons; Thaumaturge grants +1 Cantrip and +WIS to Arcana & Religion.",
                }
            )

    # 2024 Druid Level 1: Primal Order (Magician vs Warden)
    has_concrete_primal_order = any(
        ("warden" in fn and "magician" not in fn and ("primal" in fn or fn == "warden"))
        or (
            "magician" in fn
            and "warden" not in fn
            and ("primal" in fn or "druid" in fn or fn == "magician")
        )
        for fn in owned_ft_low
    )
    if is_2024 and c_lower == "druid" and target_level == 1 and not has_concrete_primal_order:
        primal_opts = [
            opt["name"] for opt in (choices_catalog.get("primal_orders") or []) if opt.get("name")
        ]
        if primal_opts:
            order_choices.append(
                {
                    "type": "primal_order",
                    "label": "Choose your Primal Order",
                    "options": primal_opts,
                    "ai_recommendation": "Magician grants +1 Cantrip and +WIS to Arcana & Nature; Warden grants Medium Armor & Martial Weapons.",
                }
            )
    return order_choices


def _build_level_up_class_choices(
    is_2024: bool,
    c_lower: str,
    sub_lower: str,
    target_level: int,
    owned_ft_low: set[str],
    choices_catalog: dict,
) -> list[dict[str, Any]]:
    """Build structured non-order class/subclass build choices for a single class level-up."""
    class_choices: list[dict[str, Any]] = []
    owned_pacts = {name for name in owned_ft_low if name.startswith("pact of the ")}

    # Fighting Styles (2014: Fighter L1, Champion L10, Paladin/Ranger L2; 2024: Fighter L1, Champion L7, Paladin/Ranger L2)
    champion_extra_style_lvl = 7 if is_2024 else 10
    if (
        (c_lower == "fighter" and target_level == 1)
        or (
            c_lower == "fighter"
            and "champion" in sub_lower
            and target_level == champion_extra_style_lvl
        )
        or (c_lower in ("paladin", "ranger") and target_level == 2)
    ):
        style_opts = [
            opt["name"]
            for opt in (choices_catalog.get("fighting_styles") or {}).get(c_lower, [])
            if opt.get("name") and opt["name"].lower() not in owned_ft_low
        ]
        if style_opts:
            class_choices.append(
                {
                    "type": "fighting_style",
                    "label": "Choose a Fighting Style",
                    "options": style_opts,
                    "ai_recommendation": f"Pick {style_opts[0]} to sharpen your martial combat role.",
                }
            )

    # Warlock Pact Boon (2014 Level 3 only; in 2024 Pact Boons are Level 1 Eldritch Invocations)
    if not is_2024 and c_lower == "warlock" and target_level == 3 and not owned_pacts:
        boon_opts = [
            opt["name"] for opt in (choices_catalog.get("pact_boons") or []) if opt.get("name")
        ]
        if boon_opts:
            class_choices.append(
                {
                    "type": "pact_boon",
                    "label": "Choose your Pact Boon",
                    "options": boon_opts,
                    "ai_recommendation": "Pact of the Tome (utility rituals/cantrips) or Pact of the Blade (Hexblade/melee).",
                }
            )

    # Warlock Eldritch Invocations
    # 2014: L2 (+2), L5/7/9/12/15/18 (+1)
    # 2024: L1 (+1), L2 (+2), L5 (+2), L7/9/12/15/18 (+1)
    inv_grants = (
        {1: 1, 2: 2, 5: 2, 7: 1, 9: 1, 12: 1, 15: 1, 18: 1}
        if is_2024
        else {2: 2, 5: 1, 7: 1, 9: 1, 12: 1, 15: 1, 18: 1}
    )
    if c_lower == "warlock" and target_level in inv_grants:
        inv_opts = [
            opt["name"]
            for opt in (choices_catalog.get("eldritch_invocations") or [])
            if opt.get("name")
            and opt["name"].lower() not in owned_ft_low
            and int(opt.get("min_level", 1 if is_2024 else 2) or (1 if is_2024 else 2))
            <= target_level
            and (not opt.get("pact") or opt["pact"].lower() in owned_pacts)
            and (
                not opt.get("requires_invocation")
                or opt["requires_invocation"].lower() in owned_ft_low
            )
        ]
        if inv_opts:
            count_inv = inv_grants[target_level]
            for idx_i in range(count_inv):
                class_choices.append(
                    {
                        "type": "eldritch_invocation",
                        "label": "Choose an Eldritch Invocation"
                        if count_inv == 1
                        else f"Choose Eldritch Invocation #{idx_i + 1}",
                        "options": inv_opts,
                        "ai_recommendation": "Pact of the Blade/Tome/Chain at L1 and Agonizing Blast / Eldritch Mind at L2+ are staples."
                        if is_2024
                        else "Agonizing Blast is staple for Eldritch Blast DPR; Devil's Sight and Eldritch Mind offer strong defense.",
                    }
                )

    # Sorcerer Metamagic (2014: L3 +2, L10/17 +1; 2024: L2 +2, L10/17 +2)
    mm_grants = {2: 2, 10: 2, 17: 2} if is_2024 else {3: 2, 10: 1, 17: 1}
    if c_lower == "sorcerer" and target_level in mm_grants:
        mm_opts = [
            opt["name"]
            for opt in (choices_catalog.get("metamagic") or [])
            if opt.get("name") and opt["name"].lower() not in owned_ft_low
        ]
        if mm_opts:
            count_mm = mm_grants[target_level]
            for idx_m in range(count_mm):
                class_choices.append(
                    {
                        "type": "metamagic",
                        "label": "Choose a Metamagic Option"
                        if count_mm == 1
                        else f"Choose Metamagic Option #{idx_m + 1}",
                        "options": mm_opts,
                        "ai_recommendation": "Quickened Spell, Subtle Spell, and Heightened Spell offer top versatility.",
                    }
                )

    # Fighter (Battle Master) Maneuvers (L3 gains 3; L7/10/15 gain 2)
    bm_grants = {3: 3, 7: 2, 10: 2, 15: 2}
    if c_lower == "fighter" and "battle master" in sub_lower and target_level in bm_grants:
        bm_opts = [
            opt["name"]
            for opt in (choices_catalog.get("maneuvers") or [])
            if opt.get("name") and opt["name"].lower() not in owned_ft_low
        ]
        if bm_opts:
            count_bm = bm_grants[target_level]
            for idx_b in range(count_bm):
                class_choices.append(
                    {
                        "type": "maneuver",
                        "label": f"Battle Master: Choose Maneuver #{idx_b + 1}",
                        "options": bm_opts,
                        "ai_recommendation": "Precision Attack, Trip Attack, and Riposte maximize accuracy and DPR.",
                    }
                )

    # Artificer Infusions / 2024 Replicate Magic Item Plans (L2 gains 4; L6/10/14/18 each gain 2)
    inf_grants = {2: 4, 6: 2, 10: 2, 14: 2, 18: 2}
    if c_lower == "artificer" and target_level in inf_grants:
        inf_opts = [
            opt["name"]
            for opt in (choices_catalog.get("artificer_infusions") or [])
            if opt.get("name")
            and opt["name"].lower() not in owned_ft_low
            and int(opt.get("min_level", 2) or 2) <= target_level
        ]
        if inf_opts:
            count_inf = inf_grants[target_level]
            plan_label = "Artificer Magic Item Plan" if is_2024 else "Artificer Infusion"
            for idx_a in range(count_inf):
                class_choices.append(
                    {
                        "type": "infusion",
                        "label": f"Choose an {plan_label}"
                        if count_inf == 1
                        else f"Choose {plan_label} #{idx_a + 1}",
                        "options": inf_opts,
                        "ai_recommendation": "Enhanced Defense / Enhanced Weapon / Mind Sharpener boost party survivability.",
                    }
                )

    # Ranger (Hunter) archetype options (2014: L3/7/11/15; 2024: L3/7)
    if (
        c_lower == "ranger"
        and "hunter" in sub_lower
        and str(target_level) in (choices_catalog.get("hunter_choices") or {})
    ):
        h_opts = [
            opt["name"]
            for opt in (choices_catalog.get("hunter_choices") or {}).get(str(target_level), [])
            if opt.get("name") and opt["name"].lower() not in owned_ft_low
        ]
        if h_opts:
            class_choices.append(
                {
                    "type": "hunter_choice",
                    "label": f"Hunter (Level {target_level}): Choose Archetype Option",
                    "options": h_opts,
                    "ai_recommendation": f"Consider {h_opts[0]} for reliable combat impact.",
                }
            )

    return class_choices


def validate_level_up_structured_choices(
    structured_entries: list[tuple[str, str, str]],
    pre_features_traits: list | None,
    target_class: str,
    new_class_level: int,
    chosen_subclass: str | None = None,
    edition: str = EDITION_2014,
    repo=None,
) -> list[dict[str, str]]:
    """
    Authoritatively validate structured class choices submitted to `/forge/level-up-apply`
    against the exact class-, subclass-, level-, and edition-scoped progression grants.
    Rejects cross-class, over-level, unmet-prerequisite, arbitrary, duplicate, over-cap,
    and mutually exclusive selections with ValueError.
    """
    if not structured_entries:
        return []

    from backend.repositories.rules_repository import RulesRepository

    rules_repo = repo or RulesRepository()
    choices_catalog = rules_repo.get_class_choices(edition) or {}
    is_2024 = "2024" in str(edition or "")
    c_lower = str(target_class or "").strip().lower()
    sub_lower = str(chosen_subclass or "").strip().lower()
    lvl = max(1, int(new_class_level or 1))
    owned_ft_low = {
        str((f.get("name") if isinstance(f, dict) else f) or "").strip().lower()
        for f in (pre_features_traits or [])
        if str((f.get("name") if isinstance(f, dict) else f) or "").strip()
    }

    expected_specs = _build_level_up_order_choices(
        is_2024, c_lower, lvl, owned_ft_low, choices_catalog
    ) + _build_level_up_class_choices(
        is_2024, c_lower, sub_lower, lvl, owned_ft_low, choices_catalog
    )

    allowed_slots: dict[str, int] = {}
    allowed_options_by_type: dict[str, dict[str, str]] = {}
    for spec in expected_specs:
        c_type = str(spec.get("type") or "").strip()
        if not c_type:
            continue
        allowed_slots[c_type] = allowed_slots.get(c_type, 0) + 1
        opt_map = allowed_options_by_type.setdefault(c_type, {})
        for opt_name in spec.get("options") or []:
            clean_opt = str(opt_name).strip()
            if clean_opt:
                opt_map[clean_opt.lower()] = clean_opt

    desc_by_name: dict[str, str] = {}
    for bucket_val in choices_catalog.values():
        items_iter = (
            [item for sub_lst in bucket_val.values() for item in (sub_lst or [])]
            if isinstance(bucket_val, dict)
            else (bucket_val if isinstance(bucket_val, list) else [])
        )
        for it in items_iter:
            if isinstance(it, dict) and it.get("name"):
                desc_by_name[str(it["name"]).strip().lower()] = str(
                    it.get("description") or ""
                ).strip()

    seen_in_payload: set[str] = set()
    counts_by_type: dict[str, int] = {}
    validated: list[dict[str, str]] = []

    for base_type, choice_label, clean_choice in structured_entries:
        clean_low = clean_choice.lower()
        if clean_low in seen_in_payload:
            raise ValueError(
                f"Duplicate selection '{clean_choice}' for '{choice_label}'. Please choose distinct options."
            )
        if base_type not in allowed_slots:
            raise ValueError(
                f"Class choice '{clean_choice}' (type '{base_type}') is not permitted when leveling "
                f"{target_class} to Level {lvl} ({edition})."
            )
        if clean_low in owned_ft_low:
            raise ValueError(
                f"Duplicate selection '{clean_choice}' for '{choice_label}'. Character already has this option."
            )
        canonical_name = allowed_options_by_type.get(base_type, {}).get(clean_low)
        if not canonical_name:
            raise ValueError(
                f"Class choice '{clean_choice}' is not permitted for '{base_type.replace('_', ' ')}' "
                f"at Level {lvl} {target_class} ({edition})."
            )
        counts_by_type[base_type] = counts_by_type.get(base_type, 0) + 1
        if counts_by_type[base_type] > allowed_slots[base_type]:
            raise ValueError(
                f"Too many selections for '{base_type.replace('_', ' ')}' at Level {lvl} "
                f"(maximum {allowed_slots[base_type]} allowed, got '{canonical_name}')."
            )
        seen_in_payload.add(clean_low)
        validated.append(
            {
                "name": canonical_name,
                "description": desc_by_name.get(clean_low) or f"Selected for {choice_label}",
                "source": "Class",
            }
        )

    return validated


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
    chosen_class_choices: list = None,
) -> dict:
    """Enriches and builds a manual character based on user selections and AI helper."""
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    validated_class_choices = validate_manual_class_choices(
        chosen_class_choices=chosen_class_choices,
        char_class=char_class,
        target_level=target_level,
        subclass=subclass,
        edition=edition,
        repo=repo,
    )

    pref_instructions = []
    if custom_preferences and custom_preferences.strip():
        pref_instructions.append(
            f"USER CUSTOM BUILD PREFERENCES (FEATS, SPELLS, ASIs):\n{custom_preferences}"
        )
    if validated_class_choices:
        pref_instructions.append(
            f"USER CHOSEN CLASS OPTIONS (STRICTLY INCLUDE THESE): {', '.join(c['name'] for c in validated_class_choices)}"
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
    if not isinstance(result, dict) or not result:
        logger.warning(
            "AI JSON generation returned None in manual forge. Generating default fallback character."
        )
        result = get_default_character()

    # Strip any LLM-hallucinated derived stats before merging manual choices
    strip_derived_character_fields(result, strip_hp=True, strip_weapon_bonuses=True)

    # Merge manual choices
    result["char_name"] = name
    result["gender"] = gender
    result["char_class"] = char_class
    result["subclass"] = subclass
    result["char_level"] = target_level
    result["race"] = race
    result["background"] = background
    result["alignment"] = alignment
    result["stats"] = dict(base_stats)
    result["saving_throws"] = saving_throws
    result["skill_proficiencies"] = skill_proficiencies
    result["spell_ability"] = spell_ability
    result["dnd_edition"] = edition

    result["char_id"] = str(uuid.uuid4())[:8]

    # Fix Custom Background (Bug 3 & 4)
    # Custom Background is now entirely handled by the AI prompt.
    if "custom" in str(result.get("background", "")).lower():
        pass

    # Add missing static class & subclass features (Bug 7 + L15+ concrete subclass resolution)
    all_static_features = []
    for lvl in range(1, target_level + 1):
        all_static_features.extend(
            resolve_level_up_automatic_features(
                char_class=char_class,
                target_level=lvl,
                subclass_to_use=subclass,
                edition=edition,
            )
        )

    existing_feat_names = {
        str((f.get("name") if isinstance(f, dict) else f) or "").strip().lower()
        for f in (result.get("features_traits") or [])
    }
    for feat in all_static_features:
        if feat.get("name", "").lower() not in existing_feat_names:
            result.setdefault("features_traits", []).append(feat)
            existing_feat_names.add(feat.get("name", "").lower())

    if validated_class_choices:
        chosen_names_low = {c["name"].strip().lower() for c in validated_class_choices}
        chose_divine_order = any(n.startswith("divine order:") for n in chosen_names_low)
        chose_primal_order = any(n.startswith("primal order:") for n in chosen_names_low)
        if chose_divine_order or chose_primal_order:
            pruned_ft = []
            for ft in result.get("features_traits") or []:
                fn = str((ft.get("name") if isinstance(ft, dict) else ft) or "").strip().lower()
                if (
                    chose_divine_order
                    and fn not in chosen_names_low
                    and (
                        (
                            "protector" in fn
                            and "thaumaturge" not in fn
                            and ("divine" in fn or fn == "protector")
                        )
                        or ("thaumaturge" in fn and "protector" not in fn)
                    )
                ):
                    continue
                if (
                    chose_primal_order
                    and fn not in chosen_names_low
                    and (
                        (
                            "warden" in fn
                            and "magician" not in fn
                            and ("primal" in fn or fn == "warden")
                        )
                        or (
                            "magician" in fn
                            and "warden" not in fn
                            and ("primal" in fn or "druid" in fn or fn == "magician")
                        )
                    )
                ):
                    continue
                pruned_ft.append(ft)
            result["features_traits"] = pruned_ft
            existing_feat_names = {
                str((f.get("name") if isinstance(f, dict) else f) or "").strip().lower()
                for f in result["features_traits"]
            }

        for choice_entry in validated_class_choices:
            clean_choice = choice_entry["name"]
            if clean_choice.lower() not in existing_feat_names:
                result.setdefault("features_traits", []).append(
                    {
                        "name": clean_choice,
                        "description": choice_entry["description"]
                        or f"Selected class option: {clean_choice}",
                        "source": "Class",
                    }
                )
                existing_feat_names.add(clean_choice.lower())

    if chosen_spells is not None:
        all_rules_spells = {
            str(s.get("name") or "")
            .strip()
            .lower()
            .replace("\u2019", "'")
            .replace("\u2018", "'"): s
            for s in repo.get_all_spells(edition)
            if isinstance(s, dict) and s.get("name")
        }
        spells_dict: dict[str, list[str]] = {}
        prepared: list[str] = []
        for s_name in chosen_spells:
            s_key = str(s_name or "").strip().lower().replace("\u2019", "'").replace("\u2018", "'")
            s_data = all_rules_spells.get(s_key)
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
            f_clean = str(f_name or "").strip()
            f_base = re.sub(r"\s*\([^)]*\)\s*$", "", f_clean).strip()
            f_data = all_rules_feats.get(f_clean.lower()) or all_rules_feats.get(f_base.lower())
            name = f_data["name"] if f_data else f_clean
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
            # Seed starting class saves when omitted before appending Resilient's save proficiency
            if name.lower() == "resilient":
                cur_saves = _seed_class_saving_throws(
                    result.get("saving_throws"), char_class, repo, edition
                )
                chosen_save = _extract_resilient_stat(f_clean)
                if not chosen_save:
                    priority_order = _get_class_stat_priority(char_class, repo, edition)
                    for cand_s in ["CON", "WIS", "DEX", *priority_order, *_STAT_KEYS]:
                        if cand_s not in cur_saves:
                            chosen_save = cand_s
                            break
                if chosen_save and chosen_save not in cur_saves:
                    cur_saves.append(chosen_save)
                result["saving_throws"] = cur_saves
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

    # Deterministically inject mandatory Class, Subclass, Species/Race, and Background grants
    result = inject_mandatory_character_grants(
        result,
        edition=edition,
        is_forge=True,
        auto_feats=auto_feats,
        auto_spells=auto_spells,
        chosen_feats=chosen_feats,
        chosen_spells=chosen_spells,
        chosen_equipment=chosen_equipment,
    )

    # Synchronize derived stats (HP, AC, Proficiency, etc.)
    class_data = _get_rules_repo().get_class_progression(char_class, edition)
    result = sync_character_stats(result, class_data)
    result["hp_current"] = result.get("hp_max", 10)

    # D&D Rules Autofix & Deep Validation
    try:
        autofix_result = autofix_character_build(result)
        result = autofix_result.get("character", result)
        result["hp_current"] = result.get("hp_max", 10)
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
        strip_derived_character_fields(fallback, strip_hp=True, strip_weapon_bonuses=False)
        fallback = sync_character_stats(fallback, class_data)
        fallback["hp_current"] = fallback.get("hp_max", 10)
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


SUBCLASS_FEATURE_LEVELS = {
    "Barbarian": [3, 6, 10, 14],
    "Bard": [3, 6, 14],
    "Cleric": [1, 2, 6, 8, 17],
    "Druid": [2, 6, 10, 14],
    "Fighter": [3, 7, 10, 15, 18],
    "Monk": [3, 6, 11, 17],
    "Paladin": [3, 7, 15, 20],
    "Ranger": [3, 7, 11, 15],
    "Rogue": [3, 9, 13, 17],
    "Sorcerer": [1, 6, 14, 18],
    "Warlock": [1, 6, 10, 14],
    "Wizard": [2, 6, 10, 14],
    "Artificer": [3, 5, 9, 15],
}

KNOWN_SUBCLASS_FEATURES = {
    ("Ranger", "Horizon Walker", 3): "Planar Warrior (1d8) & Detect Portal",
    ("Ranger", "Horizon Walker", 7): "Ethereal Step",
    ("Ranger", "Horizon Walker", 11): "Planar Warrior (2d8) & Distant Strike",
    ("Ranger", "Horizon Walker", 15): "Spectral Defense (Reaction: damage resistance)",
    ("Ranger", "Hunter", 3): "Hunter's Prey (Colossus Slayer)",
    ("Ranger", "Hunter", 7): "Defensive Tactics",
    ("Ranger", "Hunter", 11): "Multiattack (Volley / Whirlwind)",
    ("Ranger", "Hunter", 15): "Superior Hunter's Defense",
    ("Ranger", "Gloom Stalker", 3): "Dread Ambusher & Umbral Sight",
    ("Ranger", "Gloom Stalker", 7): "Iron Mind",
    ("Ranger", "Gloom Stalker", 11): "Stalker's Flurry",
    ("Ranger", "Gloom Stalker", 15): "Shadowy Dodge",
    ("Fighter", "Champion", 3): "Improved Critical (19-20)",
    ("Fighter", "Champion", 7): "Remarkable Athlete",
    ("Fighter", "Champion", 10): "Additional Fighting Style",
    ("Fighter", "Champion", 15): "Superior Critical (18-20)",
    ("Fighter", "Champion", 18): "Survivor",
    ("Fighter", "Battle Master", 3): "Combat Superiority (Maneuvers)",
    ("Fighter", "Battle Master", 7): "Know Your Enemy",
    ("Fighter", "Battle Master", 10): "Improved Combat Superiority (d10)",
    ("Fighter", "Battle Master", 15): "Relentless",
    ("Fighter", "Battle Master", 18): "Superior Combat Superiority (d12)",
    ("Rogue", "Thief", 3): "Fast Hands & Second-Story Work",
    ("Rogue", "Thief", 9): "Supreme Sneak",
    ("Rogue", "Thief", 13): "Use Magic Device",
    ("Rogue", "Thief", 17): "Thief's Reflexes",
    ("Rogue", "Assassin", 3): "Assassinate",
    ("Rogue", "Assassin", 9): "Infiltration Expertise",
    ("Rogue", "Assassin", 13): "Impostor",
    ("Rogue", "Assassin", 17): "Death Strike",
    ("Wizard", "Evocation", 2): "Sculpt Spells",
    ("Wizard", "Evocation", 6): "Potent Cantrip",
    ("Wizard", "Evocation", 10): "Empowered Evocation",
    ("Wizard", "Evocation", 14): "Overchannel",
}


SUBCLASS_FEATURES_DETAILS = {
    ("Ranger", "Horizon Walker", 3): {
        "name": "Detect Portal & Planar Warrior (Horizon Walker)",
        "description": "Detect Portal: As an action, detect distance/direction to portals within 1 mile. Planar Warrior: Bonus action to convert weapon attack damage to force damage and deal +1d8 extra force damage.",
    },
    ("Ranger", "Horizon Walker", 7): {
        "name": "Ethereal Step (Horizon Walker)",
        "description": "As a bonus action, you can cast Etherealness without expending a spell slot, lasting until the end of the current turn (1/short or long rest).",
    },
    ("Ranger", "Horizon Walker", 11): {
        "name": "Distant Strike (Horizon Walker)",
        "description": "When you take the Attack action, teleport up to 10 feet before each attack. If you attack at least two different creatures, you can make a third attack against a different creature. In addition, Planar Warrior scales to 2d8 force damage.",
    },
    ("Ranger", "Horizon Walker", 15): {
        "name": "Spectral Defense (Horizon Walker)",
        "description": "When you take damage from an attack, you can use your reaction to give yourself resistance to all of that attack's damage on this turn.",
    },
    ("Ranger", "Hunter", 3): {
        "name": "Hunter's Prey (Colossus Slayer)",
        "description": "Once per turn, deal an extra 1d8 damage to a creature below its maximum hit points.",
    },
    ("Ranger", "Hunter", 7): {
        "name": "Defensive Tactics (Hunter)",
        "description": "Bolster your defense with Escape the Horde, Multiattack Defense, or Steel Will.",
    },
    ("Ranger", "Hunter", 11): {
        "name": "Multiattack: Volley / Whirlwind Attack",
        "description": "Ranged volley within 10ft of a point, or melee whirlwind attack against all adjacent creatures.",
    },
    ("Ranger", "Hunter", 15): {
        "name": "Superior Hunter's Defense",
        "description": "Gain Evasion, Stand Against the Tide, or Uncanny Dodge to negate lethal attacks.",
    },
    ("Fighter", "Champion", 3): {
        "name": "Improved Critical (Champion)",
        "description": "Your weapon attacks score a critical hit on a roll of 19 or 20.",
    },
    ("Fighter", "Champion", 7): {
        "name": "Remarkable Athlete (Champion)",
        "description": "Add half your proficiency bonus to any STR, DEX, or CON check that doesn't already use it. Running long jump distance increases by STR modifier in feet.",
    },
    ("Fighter", "Champion", 10): {
        "name": "Additional Fighting Style (Champion)",
        "description": "Choose a second option from the Fighting Style class feature.",
    },
    ("Fighter", "Champion", 15): {
        "name": "Superior Critical (Champion)",
        "description": "Your weapon attacks score a critical hit on a roll of 18-20.",
    },
    ("Fighter", "Champion", 18): {
        "name": "Survivor (Champion)",
        "description": "At the start of each of your turns, you regain 5 + CON modifier HP if you have no more than half your HP left.",
    },
}


def _generate_dynamic_future_milestones(
    target_class: str,
    target_class_level: int,
    subclass: str | None,
    edition: str,
    feat_rec: str,
    archetype: str,
    known_spells: list[str] | None = None,
) -> list[str]:
    repo = _get_rules_repo()
    is_2024 = "2024" in str(edition)
    known_set = {k.strip().lower() for k in (known_spells or [])}
    cls_lower = (target_class or "Fighter").lower()

    if cls_lower == "fighter":
        asi_milestones = [4, 6, 8, 12, 14, 16, 19]
    elif cls_lower == "rogue":
        asi_milestones = [4, 8, 10, 12, 16, 19]
    else:
        asi_milestones = [4, 8, 12, 16, 19]

    subclass_milestones = SUBCLASS_FEATURE_LEVELS.get(target_class, [3, 7, 11, 15])
    start_lvl = target_class_level
    end_lvl = min(20, target_class_level + 5) if target_class_level < 18 else 20

    school_map = {
        "offensive": ["evocation", "necromancy"],
        "defensive": ["abjuration"],
        "utility": ["conjuration", "transmutation", "divination"],
    }
    preferred_schools = school_map.get(archetype, [])

    all_class_spells = [
        s
        for s in repo.get_all_spells(edition)
        if target_class.lower() in [c.lower() for c in s.get("classes", [])]
        and s.get("name", "").strip().lower() not in known_set
    ]

    milestones = []
    for lvl in range(start_lvl, end_lvl + 1):
        details = []
        raw_features = repo.get_features_at_level(target_class, lvl, edition)
        feat_names = []
        for f in raw_features:
            fname = f.get("name", "")
            flwr = fname.lower()
            if "ability score improvement" in flwr:
                continue
            if any(
                ph in flwr
                for ph in [
                    "archetype feature",
                    "tradition feature",
                    "domain feature",
                    "college feature",
                    "path feature",
                    "circle feature",
                    "origin feature",
                    "patron feature",
                    "monastic tradition",
                ]
            ):
                continue
            feat_names.append(fname)

        if feat_names:
            details.append(" & ".join(feat_names))

        # Subclass feature
        if lvl in subclass_milestones:
            known_match = None
            if subclass:
                features_map = KNOWN_SUBCLASS_FEATURES_2024 if is_2024 else KNOWN_SUBCLASS_FEATURES
                for (c, sc, feat_lvl), desc in features_map.items():
                    if (
                        c.lower() == target_class.lower()
                        and sc.lower() in subclass.lower()
                        and feat_lvl == lvl
                    ):
                        known_match = desc
                        break
                if not known_match and is_2024:
                    for (c, sc, feat_lvl), desc in KNOWN_SUBCLASS_FEATURES.items():
                        if (
                            c.lower() == target_class.lower()
                            and sc.lower() in subclass.lower()
                            and feat_lvl == lvl
                        ):
                            known_match = desc
                            break
            if not known_match:
                sub_entry = (
                    repo.get_subclass_entry(target_class, subclass, edition) if subclass else None
                )
                if isinstance(sub_entry, dict):
                    sub_feat = (sub_entry.get("features") or {}).get(str(lvl))
                    if isinstance(sub_feat, dict) and sub_feat.get("name"):
                        known_match = str(sub_feat["name"])
                    elif isinstance(sub_feat, list) and sub_feat:
                        known_match = " & ".join(
                            str(x.get("name"))
                            for x in sub_feat
                            if isinstance(x, dict) and x.get("name")
                        )
            if known_match:
                details.append(known_match)
            else:
                sub_mech = repo.get_subclass_mechanics(target_class, edition)
                sub_info = sub_mech.get("subclasses", {}).get(subclass, {}) if subclass else {}
                scaling_found = []
                for k, val in sub_info.get("scaling", {}).items():
                    for step in val.get("steps", []):
                        if step.get("level") == lvl:
                            scaling_found.append(
                                f"{val.get('name', k)} ({step.get('notation', '')})"
                            )
                if scaling_found:
                    details.append(f"{subclass}: {', '.join(scaling_found)}")
                elif subclass and subclass not in ["None", "N/A", ""]:
                    details.append(f"{subclass} Feature")
                else:
                    details.append("Subclass Feature")

        # ASI milestone
        if lvl in asi_milestones:
            details.append(
                f"Major ASI / Feat Milestone ({feat_rec})"
                if feat_rec
                else "Major ASI / Feat Milestone"
            )

        # Spell tier unlock
        slots_curr = calculate_max_spell_slots(target_class, lvl, subclass, edition=edition)
        slots_prev = (
            calculate_max_spell_slots(target_class, max(1, lvl - 1), subclass, edition=edition)
            if lvl > 1
            else {}
        )
        max_curr = max(
            [int(k.replace("level_", "")) for k, v in slots_curr.items() if v > 0] or [0]
        )
        max_prev = max(
            [int(k.replace("level_", "")) for k, v in slots_prev.items() if v > 0] or [0]
        )

        if max_curr > max_prev or (lvl == start_lvl and max_curr > 0):
            tier_spells = [
                s["name"]
                for s in all_class_spells
                if s.get("level") == max_curr
                and any(kw in (s.get("school") or "").lower() for kw in preferred_schools)
            ]
            if not tier_spells:
                tier_spells = [s["name"] for s in all_class_spells if s.get("level") == max_curr]
            sample = ", ".join(tier_spells[:2])
            spell_tag = (
                f"Tier {max_curr} Spells ({sample})" if sample else f"Tier {max_curr} Spells"
            )
            details.append(spell_tag)

        if lvl == 20:
            details.append("Epic Level 20 Capstone")

        if not details:
            details.append("Hit Points & Tactical Resource Expansion")

        milestones.append(f"Level {lvl}: " + " & ".join(details))
    return milestones


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
    current_subclass: str | None = None,
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

    cls_lower = (target_class or "").lower()
    if cls_lower == "fighter":
        asi_milestones = [4, 6, 8, 12, 14, 16, 19]
    elif cls_lower == "rogue":
        asi_milestones = [4, 8, 10, 12, 16, 19]
    else:
        asi_milestones = [4, 8, 12, 16, 19]

    next_asi_lvl = 19
    for m in asi_milestones:
        if m > target_class_level:
            next_asi_lvl = m
            break

    if not feat_1:
        feat_1 = (
            f"War Caster or +2 to {prim_stat} (at Level {next_asi_lvl} ASI)"
            if is_caster
            else f"Sharpshooter or Great Weapon Master (at Level {next_asi_lvl} ASI)"
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

    sub_for_ms = current_subclass or char_data.get("subclass")

    future_ms_1 = _generate_dynamic_future_milestones(
        target_class=target_class,
        target_class_level=target_class_level,
        subclass=sub_1 or sub_for_ms,
        edition=edition,
        feat_rec=feat_1,
        archetype="offensive",
        known_spells=known_spells,
    )
    future_ms_2 = _generate_dynamic_future_milestones(
        target_class=target_class,
        target_class_level=target_class_level,
        subclass=sub_2 or sub_for_ms,
        edition=edition,
        feat_rec=feat_2,
        archetype="defensive",
        known_spells=known_spells,
    )
    future_ms_3 = _generate_dynamic_future_milestones(
        target_class=target_class,
        target_class_level=target_class_level,
        subclass=sub_3 or sub_for_ms,
        edition=edition,
        feat_rec=feat_3,
        archetype="utility",
        known_spells=known_spells,
    )

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
    repo = _get_rules_repo()
    edition = char_data.get("dnd_edition", EDITION_2014)
    classes = char_data.get("classes", [])
    current_total_level = char_data.get("char_level", 1)
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

    if target_level is not None and target_level > class_current_level:
        target_class_level = min(20, target_level)
    else:
        target_class_level = min(20, class_current_level + 1)

    level_gain = max(1, target_class_level - class_current_level)
    target_total_level = min(20, current_total_level + level_gain)

    needs_sub = _needs_subclass(target_class, target_class_level, current_subclass, edition)
    available_subclasses = repo.get_subclasses(target_class, edition) if needs_sub else []
    has_asi = _has_asi(target_class, target_class_level)

    cls_lower = (target_class or "").lower()
    if cls_lower == "fighter":
        asi_milestones = [4, 6, 8, 12, 14, 16, 19]
    elif cls_lower == "rogue":
        asi_milestones = [4, 8, 10, 12, 16, 19]
    else:
        asi_milestones = [4, 8, 12, 16, 19]

    next_asi_lvl = 19
    for m in asi_milestones:
        if m > target_class_level:
            next_asi_lvl = m
            break

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
            current_subclass=current_subclass,
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
            max_projected_level=min(20, target_class_level + 5),
            next_asi_level=next_asi_lvl,
            primary_stat=prim_stat,
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
        for idx, b in enumerate(raw_builds[:3]):
            if not isinstance(b, dict):
                continue
            ms = [str(m) for m in b.get("future_milestones", []) if m]
            if not ms:
                archetype_type = (
                    "offensive" if idx == 0 else ("defensive" if idx == 1 else "utility")
                )
                ms = _generate_dynamic_future_milestones(
                    target_class=target_class,
                    target_class_level=target_class_level,
                    subclass=str(b.get("recommended_subclass"))
                    if b.get("recommended_subclass")
                    else current_subclass,
                    edition=edition,
                    feat_rec=str(b.get("recommended_feat_or_asi") or ""),
                    archetype=archetype_type,
                    known_spells=all_known_spells,
                )
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
                    "future_milestones": ms,
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


def _lookup_subclass_detail(
    details_map: dict, char_class: str, subclass_to_use: str, target_level: int
) -> dict | None:
    """Resolve subclass detail preferring exact name match before longest substring match."""
    cls_lower = char_class.lower()
    sub_lower = subclass_to_use.lower().strip()
    for (c, sc, lvl), detail in details_map.items():
        if c.lower() == cls_lower and lvl == target_level and sc.lower() == sub_lower:
            return detail
    for (c, sc, lvl), detail in sorted(
        details_map.items(), key=lambda item: len(item[0][1]), reverse=True
    ):
        if c.lower() == cls_lower and lvl == target_level and sc.lower() in sub_lower:
            return detail
    return None


_SUBCLASS_PLACEHOLDERS = (
    "archetype feature",
    "tradition feature",
    "subclass feature",
    "domain feature",
    "path feature",
    "martial archetype",
    "roguish archetype",
    "sorcerous origin",
    "divine domain",
    "arcane tradition",
    "primal path",
    "bard college",
    "druid circle",
    "monastic tradition",
    "sacred oath",
    "ranger archetype",
    "otherworldly patron",
    "artificer specialist",
)


def is_subclass_placeholder_name(feature_name: str) -> bool:
    """Return True when a class table feature name is a generic subclass placeholder."""
    flwr = str(feature_name or "").lower().strip()
    return flwr.endswith(" subclass") or any(ph in flwr for ph in _SUBCLASS_PLACEHOLDERS)


def resolve_level_up_automatic_features(
    char_class: str,
    target_level: int,
    subclass_to_use: str | None = None,
    edition: str = "2014 Edition",
) -> list[dict]:
    """Build deterministic automatic level-up features from RulesRepository."""
    from backend.repositories.rules_repository import RulesRepository

    is_2024 = "2024" in str(edition)
    rules_repo = RulesRepository()
    static_features = rules_repo.get_features_at_level(char_class, target_level, edition)
    if not subclass_to_use:
        return [{"source": f.get("source") or "Class", **f} for f in static_features]

    resolved_features = []
    for feat in static_features:
        if is_subclass_placeholder_name(feat.get("name", "")):
            sub_detail = None
            # Single source of truth: consult data/rules/subclasses/<edition>/<class>.json first
            # across both 2014 and 2024 editions, falling back to Python tables only if absent.
            sub_entry = rules_repo.get_subclass_entry(char_class, subclass_to_use, edition)
            if isinstance(sub_entry, dict):
                raw_lvl_feat = (sub_entry.get("features") or {}).get(str(target_level))
                if isinstance(raw_lvl_feat, dict) and raw_lvl_feat.get("name"):
                    sub_detail = {
                        "name": str(raw_lvl_feat["name"]),
                        "description": str(raw_lvl_feat.get("description") or ""),
                    }
                elif isinstance(raw_lvl_feat, list):
                    for item in raw_lvl_feat:
                        if isinstance(item, dict) and item.get("name"):
                            resolved_features.append({**item, "source": "Subclass"})
                    continue
            if not sub_detail and is_2024:
                sub_detail = _lookup_subclass_detail(
                    SUBCLASS_FEATURES_DETAILS_2024, char_class, subclass_to_use, target_level
                )
            if not sub_detail:
                details_map = SUBCLASS_FEATURES_DETAILS
                sub_detail = _lookup_subclass_detail(
                    details_map, char_class, subclass_to_use, target_level
                )
            if sub_detail:
                resolved_features.append({**sub_detail, "source": "Subclass"})
            else:
                resolved_features.append(
                    {
                        "name": f"{subclass_to_use} Subclass Feature",
                        "description": feat.get(
                            "description",
                            f"Special feature granted by the {subclass_to_use} subclass at Level {target_level}.",
                        ),
                        "source": "Subclass",
                    }
                )
        else:
            resolved_features.append({"source": feat.get("source") or "Class", **feat})
    return resolved_features


def _extract_level_up_hp_deltas(
    char_data: dict,
    user_choices: dict,
    feat_lookup: dict[str, dict[str, Any]],
    owned_non_repeatable: set[str],
    target_total_level: int,
    edition: str,
) -> tuple[int, int, int]:
    """Compute (con_mod_delta, added_feat_hp_per_level, added_flat_hp) from pending level-up ASI/feat choices."""
    from backend.services.stats_service import get_modifier

    is_2024 = "2024" in str(edition)
    stat_cap = 30 if (is_2024 and target_total_level >= 19) else 20
    stats = char_data.get("stats") or {}
    old_con = int(stats.get("CON", 10) or 10)
    con_bump = 0
    added_feat_hp_per_level = 0
    added_flat_hp = 0
    seen_new_feats: set[str] = set()

    for choice_key, choice_val in (user_choices or {}).items():
        if (
            not choice_val
            or "_stat1_" in choice_key
            or "_stat2_" in choice_key
            or choice_key
            in ("level_up_class", "hp_method", "custom_hp_increase", "hp_bonus_included")
        ):
            continue
        base_type = choice_key.rsplit("_", 1)[0] if "_" in choice_key else choice_key
        if base_type in (
            "subclass",
            "spell",
            "spell_secret_1",
            "spell_secret_2",
            "expertise_1",
            "expertise_2",
        ):
            continue
        if (
            base_type != "feat"
            and "feat" not in choice_key.lower()
            and choice_val
            not in (
                "+2 to one Stat",
                "+1 to two Stats",
            )
        ):
            continue

        stat1_key, stat2_key = stat_choice_keys_for(choice_key)
        stat1 = str((user_choices or {}).get(stat1_key) or "").strip().upper()
        stat2 = str((user_choices or {}).get(stat2_key) or "").strip().upper()

        val_str = str(choice_val).strip()
        if val_str == "+2 to one Stat":
            if stat1 == "CON":
                con_bump += 2
        elif val_str == "+1 to two Stats":
            if stat1 == "CON":
                con_bump += 1
            if stat2 == "CON" and stat2 != stat1:
                con_bump += 1
        else:
            resolved = resolve_known_feat(val_str, feat_lookup, source="Feat")
            if not resolved:
                continue
            canon_name, feat_data = resolved
            canon_low = canon_name.lower()
            if not is_feat_repeatable(feat_data, canon_low) and canon_low in owned_non_repeatable:
                continue

            con_bonus = int((feat_data.get("stat_bonus") or {}).get("CON") or 0)
            if con_bonus > 0:
                con_bump += con_bonus

            if feat_data.get("has_stat_choice") and stat1 == "CON":
                allowed_opts = {
                    str(opt).strip().upper()[:3]
                    for opt in (feat_data.get("stat_choice_options") or [])
                    if str(opt).strip()
                }
                if not allowed_opts or "CON" in allowed_opts:
                    con_bump += 1

            per_lvl = int(feat_data.get("hp_bonus_per_level") or 0)
            flat_hp = int(feat_data.get("flat_hp_bonus") or 0)
            if per_lvl > 0 or flat_hp > 0:
                if is_feat_repeatable(feat_data, canon_low) or canon_low not in seen_new_feats:
                    seen_new_feats.add(canon_low)
                    added_feat_hp_per_level += per_lvl
                    added_flat_hp += flat_hp

    new_con = min(stat_cap, old_con + con_bump)
    con_mod_delta = get_modifier(new_con) - get_modifier(old_con)
    return con_mod_delta, added_feat_hp_per_level, added_flat_hp


def analyze_level_up(char_data: dict, user_choices: dict = None) -> dict:
    """Determines level up changes deterministically without an LLM call."""
    import math

    from backend.repositories.rules_repository import RulesRepository
    from backend.services.validation_service import (
        get_multiclass_eligibility,
        get_multiclass_skill_options,
        validate_multiclass_target,
    )

    classes = char_data.get("classes", [])
    user_choices = user_choices or {}

    target_class = user_choices.get("level_up_class") or char_data.get("char_class") or "Fighter"

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

    edition = char_data.get("dnd_edition") or char_data.get("ruleset_version") or "2014 Edition"
    is_2024 = "2024" in str(edition)

    has_existing_class = bool(classes) or bool(str(char_data.get("char_class") or "").strip())
    is_new_multiclass = has_existing_class and class_current_level == 0
    multiclass_options = get_multiclass_eligibility(char_data, edition=edition)
    mc_target_info = (
        validate_multiclass_target(char_data, target_class, edition=edition)
        if is_new_multiclass
        else None
    )

    # Override char_class to target_class for the rest of this function
    char_class = target_class

    rules_repo = RulesRepository()
    static_features = rules_repo.get_features_at_level(char_class, target_level, edition)

    # Resolve subclass early so Draconic Sorcerer HP vitals and feature placeholders match
    current_subclass = None
    for cls in classes:
        if cls.get("class_name", "").lower() == char_class.lower():
            current_subclass = cls.get("subclass")
            break
    if not classes and char_class.lower() == char_data.get("char_class", "").lower():
        current_subclass = char_data.get("subclass")
    chosen_subclass_choice = user_choices.get("subclass") or next(
        (
            str(v)
            for k, v in user_choices.items()
            if v and (k == "subclass" or k.startswith("subclass_"))
        ),
        None,
    )
    subclass_to_use = current_subclass or chosen_subclass_choice

    hp_bonus_per_level = 0
    try:
        vitals = get_level_up_vitals(
            char_class=char_class,
            current_level=class_current_level,
            con_score=char_data.get("stats", {}).get("CON", 10),
            edition=edition,
            features=char_data.get("features_traits", []),
            subclass=subclass_to_use,
        )
        hp_increase = max(1, vitals.get("average_hp_gain", 1))
        max_legal_hp_gain = max(1, vitals.get("max_hp_gain", hp_increase))
        hp_bonus_per_level = int(vitals.get("hp_bonus_per_level") or 0)
    except Exception:
        hp_increase = 1
        max_legal_hp_gain = 1
        hp_bonus_per_level = 0

    hp_method = str(user_choices.get("hp_method") or "").strip().lower()
    custom_hp = user_choices.get("custom_hp_increase")
    rolled_custom_hp = False
    if custom_hp is not None and hp_method != "average":
        try:
            hp_increase = max(1, min(max_legal_hp_gain, int(custom_hp)))
            rolled_custom_hp = True
        except (ValueError, TypeError):
            pass

    retroactive_hp_bonus = 0
    if (
        is_2024
        and char_class.lower() == "sorcerer"
        and not current_subclass
        and "draconic" in str(subclass_to_use or "").lower()
        and target_level >= 3
    ):
        retroactive_hp_bonus = class_current_level

    feat_lookup = build_feat_lookup(edition)
    owned_non_repeatable = get_owned_non_repeatable_feats(
        char_data, edition=edition, feat_lookup=feat_lookup
    )
    con_mod_delta, added_feat_hp_per_level, added_flat_hp = _extract_level_up_hp_deltas(
        char_data=char_data,
        user_choices=user_choices,
        feat_lookup=feat_lookup,
        owned_non_repeatable=owned_non_repeatable,
        target_total_level=target_total_level,
        edition=edition,
    )
    hp_bonus_per_level += added_feat_hp_per_level
    per_level_choice_delta = con_mod_delta + added_feat_hp_per_level
    if rolled_custom_hp:
        preview_new_total_hp = (
            char_data.get("hp_max", 0)
            + hp_increase
            + retroactive_hp_bonus
            + added_flat_hp
            + per_level_choice_delta * target_total_level
        )
    else:
        hp_increase = max(1, hp_increase + per_level_choice_delta)
        preview_new_total_hp = (
            char_data.get("hp_max", 0)
            + hp_increase
            + retroactive_hp_bonus
            + added_flat_hp
            + per_level_choice_delta * current_total_level
        )

    updated_pb = math.ceil(target_total_level / 4) + 1

    choices = []
    static_features = resolve_level_up_automatic_features(
        char_class, target_level, subclass_to_use, edition
    )
    if is_new_multiclass and mc_target_info is not None:
        granted_list = mc_target_info.get("granted_proficiencies") or []
        prof_summary = (
            ", ".join(granted_list)
            if granted_list
            else "No additional armor, weapon, or tool proficiencies"
        )
        static_features = [
            {
                "name": f"Multiclass Proficiencies ({char_class})",
                "description": (
                    f"PHB Multiclassing grants: {prof_summary}. "
                    f"(Does not grant {char_class} saving throw proficiencies.)"
                ),
                "source": "Class",
            },
            *static_features,
        ]

    if not current_subclass:
        subclasses = rules_repo.get_subclasses(char_class, edition)
        if subclasses:
            subclass_level = 3
            if not is_2024:
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

    # 2. ASI/Feat or 2024 Level 19/20 Epic Boon
    from backend.services.progression_service import is_asi_or_epic_boon_feature

    is_asi_level = any(is_asi_or_epic_boon_feature(f.get("name", "")) for f in static_features)

    c_lower = char_class.lower()
    sub_lower = str(subclass_to_use or "").lower()
    spell_list_class = resolve_spell_list_class(char_class, subclass_to_use)
    replaceable_spells: list[str] = []
    spell_swap_options: list[str] = []

    if is_asi_level:
        from backend.services.validation_service import (
            get_character_armor_proficiencies,
            get_character_weapon_proficiencies,
        )

        char_race = char_data.get("race", "").lower()
        char_stats = char_data.get("stats") or {}
        target_class_prog = rules_repo.get_class_progression(char_class, edition)
        char_armor_profs = get_character_armor_proficiencies(char_data, target_class_prog)
        char_weapon_profs = get_character_weapon_proficiencies(char_data, target_class_prog)
        has_spellcasting = bool(
            spell_list_class
            and (spell_list_class not in ("paladin", "ranger") or is_2024 or target_level >= 2)
        ) or any(
            k in str(f.get("name") if isinstance(f, dict) else f).lower()
            for f in (char_data.get("features_traits") or [])
            for k in ("spellcasting", "pact magic", "magic initiate", "ritual caster")
        )

        def _meets_stat_reqs(stat_reqs: dict) -> bool:
            for rk, req_val in (stat_reqs or {}).items():
                rk_up = str(rk).strip().upper()
                try:
                    needed = int(req_val)
                except (TypeError, ValueError):
                    continue
                if "_OR_" in rk_up:
                    options_ab = [p.strip()[:3] for p in rk_up.split("_OR_") if p.strip()]
                    if not any(int(char_stats.get(ab, 10) or 10) >= needed for ab in options_ab):
                        return False
                elif rk_up[:3] in _STAT_KEYS:
                    if int(char_stats.get(rk_up[:3], 10) or 10) < needed:
                        return False
            return True

        def _meets_other_req(req_str: str) -> bool:
            r_low = str(req_str or "").strip().lower()
            if not r_low:
                return True
            if "strength 13+" in r_low and int(char_stats.get("STR", 10) or 10) < 13:
                return False
            if r_low == "spellcasting":
                return has_spellcasting
            if "proficiency with light armor" in r_low or "light armor proficiency" in r_low:
                return "light armor" in char_armor_profs or "all armor" in char_armor_profs
            if "proficiency with medium armor" in r_low or "medium armor proficiency" in r_low:
                return "medium armor" in char_armor_profs or "all armor" in char_armor_profs
            if "proficiency with heavy armor" in r_low or "heavy armor proficiency" in r_low:
                return "heavy armor" in char_armor_profs or "all armor" in char_armor_profs
            if "proficiency with shields" in r_low or "shield proficiency" in r_low:
                return "shields" in char_armor_profs or "all armor" in char_armor_profs
            if "proficiency with martial weapons" in r_low or "martial weapon" in r_low:
                return "martial weapons" in char_weapon_profs
            if r_low == "elf":
                return (
                    bool(re.search(r"\b(?:elf|high elf|wood elf|dark elf|drow)\b", char_race))
                    and "half-elf" not in char_race
                )
            if r_low == "half-elf":
                return "half-elf" in char_race
            if r_low == "human":
                return bool(re.search(r"\bhuman\b", char_race)) and "half" not in char_race
            return bool(re.search(rf"\b{re.escape(r_low)}\b", char_race)) or (r_low in char_race)

        allowed_feats = []
        feat_metadata: dict[str, dict[str, Any]] = {}
        for f in rules_repo.get_all_feats(edition):
            f_name = str(f.get("name") or "").strip()
            f_low = f_name.lower()
            if not f_name or f_low == "ability score improvement":
                continue
            if not is_feat_repeatable(f, f_low) and f_low in owned_non_repeatable:
                continue
            prereqs = f.get("prerequisites") or {}
            try:
                min_req_level = int(prereqs.get("min_level") or 0)
            except (TypeError, ValueError):
                min_req_level = 0
            if min_req_level > target_total_level:
                continue
            if not _meets_stat_reqs(prereqs.get("stat_requirements") or {}):
                continue
            reqs = prereqs.get("other", [])
            if not reqs or any(_meets_other_req(r) for r in reqs):
                allowed_feats.append(f_name)
                stat_opts = [
                    str(opt).strip().upper()[:3]
                    for opt in (f.get("stat_choice_options") or [])
                    if str(opt).strip()
                ]
                stat_bonus = {
                    str(k).upper()[:3]: int(v) for k, v in (f.get("stat_bonus") or {}).items() if v
                }
                feat_metadata[f_name] = {
                    "has_stat_choice": bool(f.get("has_stat_choice")),
                    "stat_choice_options": stat_opts,
                    "stat_bonus": stat_bonus,
                    "hp_bonus_per_level": int(f.get("hp_bonus_per_level") or 0),
                    "flat_hp_bonus": int(f.get("flat_hp_bonus") or 0),
                }

        choices.append(
            {
                "type": "feat",
                "label": "Choose a Feat or Ability Score Improvement",
                "options": ["+2 to one Stat", "+1 to two Stats"] + allowed_feats,
                "ai_recommendation": "A standard ASI/Feat level. Pick what suits your build best.",
                "feat_metadata": feat_metadata,
            }
        )

    # 2b. 2024 Level 1 Divine/Primal Order choices (emitted BEFORE Spells so choice indices stay invariant when Thaumaturge/Magician adds a 4th/3rd cantrip)
    choices_catalog = rules_repo.get_class_choices(edition)
    _owned_ft_names_low = {
        str((f.get("name") if isinstance(f, dict) else f) or "").strip().lower()
        for f in (char_data.get("features_traits") or [])
    }
    choices.extend(
        _build_level_up_order_choices(
            is_2024, c_lower, target_level, _owned_ft_names_low, choices_catalog
        )
    )

    # 3. Spells (Full Casters, Half Casters, Pact Magic + Mystic Arcanum, 1/3 Casters, & Cantrip scaling)
    _pending_choice_vals_low = {
        str(v or "").strip().lower()
        for k, v in (user_choices or {}).items()
        if isinstance(v, str) and not k.startswith(("spell_swap", "hp_"))
    }

    def _has_order_extra_cantrip(cls_low: str, names_low: set[str]) -> bool:
        if not is_2024:
            return False
        if cls_low == "cleric":
            return any("thaumaturge" in fn and "protector" not in fn for fn in names_low)
        if cls_low == "druid":
            return any(
                "warden" not in fn
                and (
                    "primal order: magician" in fn
                    or fn == "magician"
                    or ("magician" in fn and ("primal" in fn or "druid" in fn))
                )
                for fn in names_low
            )
        return False

    def _expected_cantrips(
        cls_low: str, lvl: int, sub_low: str, include_pending: bool = False
    ) -> int:
        if lvl <= 0:
            return 0
        extra = 0
        check_names = (
            _owned_ft_names_low | _pending_choice_vals_low
            if include_pending
            else _owned_ft_names_low
        )
        if _has_order_extra_cantrip(cls_low, check_names):
            extra = 1
        if cls_low in ("wizard", "cleric"):
            return (3 if lvl < 4 else (4 if lvl < 10 else 5)) + extra
        if cls_low == "sorcerer":
            return 4 if lvl < 4 else (5 if lvl < 10 else 6)
        if cls_low in ("bard", "druid", "warlock"):
            return (2 if lvl < 4 else (3 if lvl < 10 else 4)) + extra
        if cls_low == "artificer":
            return 2 if lvl < 10 else (3 if lvl < 14 else 4)
        if cls_low == "fighter" and "eldritch knight" in sub_low:
            return 0 if lvl < 3 else (2 if lvl < 10 else 3)
        if cls_low == "rogue" and "arcane trickster" in sub_low:
            return 0 if lvl < 3 else (3 if lvl < 10 else 4)
        return 0

    if spell_list_class:
        max_slots = calculate_max_spell_slots(
            char_class, target_level, subclass_to_use, edition=edition
        )
        max_spell_level = 0
        for i in range(1, 10):
            if max_slots.get(f"level_{i}", 0) > 0:
                max_spell_level = i

        # Warlock Pact slots cap at level 5; Mystic Arcanum unlocks 1 spell each at L11/13/15/17
        warlock_arcanum_map = {11: 6, 13: 7, 15: 8, 17: 9}
        arcanum_lvl = warlock_arcanum_map.get(target_level) if c_lower == "warlock" else None

        # Collect all spells already known by the character to exclude them
        known_spells_lower = set()
        sp_dict = char_data.get("spells") or {}
        if isinstance(sp_dict, dict):
            for lvl_list in sp_dict.values():
                if isinstance(lvl_list, list):
                    for s in lvl_list:
                        name = s.get("name") if isinstance(s, dict) else str(s)
                        if name:
                            known_spells_lower.add(_norm_spell_key(name))
        elif isinstance(sp_dict, list):
            for s in sp_dict:
                name = s.get("name") if isinstance(s, dict) else str(s)
                if name:
                    known_spells_lower.add(_norm_spell_key(name))

        all_spells = rules_repo.get_all_spells(edition)
        spells_level_map = {s["name"]: s.get("level", 0) for s in all_spells if "name" in s}

        spells = []
        cantrip_options = []
        arcanum_options = []
        magical_secrets_spells = []
        for s in all_spells:
            s_name = s.get("name", "")
            if not s_name or _norm_spell_key(s_name) in known_spells_lower:
                continue
            s_level = s.get("level", 0)
            s_classes = [str(c).lower() for c in s.get("classes", [])]
            matches_class = not s_classes or spell_list_class in s_classes
            if s_level == 0 and matches_class:
                cantrip_options.append(s_name)
            elif 0 < s_level <= max_spell_level:
                magical_secrets_spells.append(s_name)
                if matches_class:
                    spells.append(s_name)
            elif arcanum_lvl and s_level == arcanum_lvl and matches_class:
                arcanum_options.append(s_name)

        # Sort spells: highest level (newest tier) first, then alphabetical
        spells.sort(key=lambda n: (-spells_level_map.get(n, 0), n))
        magical_secrets_spells.sort(key=lambda n: (-spells_level_map.get(n, 0), n))
        cantrip_options.sort()
        arcanum_options.sort()

        # Grant newly unlocked Cantrip choice(s) when expected cantrip count increases
        prev_cantrips = _expected_cantrips(
            c_lower, class_current_level, str(current_subclass or "").lower(), include_pending=False
        )
        new_cantrips = _expected_cantrips(c_lower, target_level, sub_lower, include_pending=True)
        gained_cantrips = max(0, new_cantrips - prev_cantrips)
        if gained_cantrips > 0 and cantrip_options:
            for idx_c in range(min(gained_cantrips, 4)):
                choices.append(
                    {
                        "type": "spell",
                        "label": f"Learn a {spell_list_class.title()} Cantrip"
                        if gained_cantrips == 1
                        else f"Learn {spell_list_class.title()} Cantrip #{idx_c + 1}",
                        "options": cantrip_options,
                        "ai_recommendation": f"Choose a signature cantrip like {cantrip_options[0]}.",
                    }
                )

        # Grant Mystic Arcanum choice specifically at Warlock L11/13/15/17
        if arcanum_lvl and arcanum_options:
            choices.append(
                {
                    "type": "spell",
                    "label": f"Mystic Arcanum: Choose a Level {arcanum_lvl} Warlock Spell",
                    "options": arcanum_options,
                    "ai_recommendation": f"Choose one Level {arcanum_lvl} spell you can cast once per Long Rest without a Pact slot.",
                }
            )

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
        elif max_spell_level >= 1 and spells:
            choices.append(
                {
                    "type": "spell",
                    "label": f"Learn/Prepare a {spell_list_class.title()} Spell",
                    "options": spells,
                    "ai_recommendation": ai_spell_rec,
                }
            )

        if max_spell_level >= 1 and spells:
            replaceable_spells, _ = get_spell_swap_candidates(
                char_data,
                char_class,
                subclass_to_use,
                target_level,
                max_spell_level,
                edition,
                rules_repo,
                all_spells=all_spells,
            )
            if replaceable_spells:
                spell_swap_options = list(spells)

    if is_new_multiclass and char_class.strip().lower() in ("bard", "ranger", "rogue"):
        mc_skills = get_multiclass_skill_options(
            char_class, char_data.get("skill_proficiencies") or []
        )
        if mc_skills:
            choices.append(
                {
                    "type": "skill",
                    "label": f"Multiclass {char_class}: Choose 1 Bonus Skill Proficiency",
                    "options": mc_skills,
                    "ai_recommendation": f"Choose {mc_skills[0]} to complement your multiclass build.",
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
    if char_class == "Bard" and (
        (is_2024 and target_level in [2, 9]) or (not is_2024 and target_level in [3, 10])
    ):
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
    elif is_2024 and char_class == "Ranger" and target_level == 2:
        choices.append(
            {
                "type": "expertise_1",
                "label": "Deft Explorer: Choose a skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick Stealth, Perception, or Survival for your Ranger Expertise.",
            }
        )
    elif is_2024 and char_class == "Ranger" and target_level == 9:
        choices.append(
            {
                "type": "expertise_1",
                "label": "Expertise (Level 9): Choose 1st skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick a skill you are already proficient in.",
            }
        )
        choices.append(
            {
                "type": "expertise_2",
                "label": "Expertise (Level 9): Choose 2nd skill for Expertise",
                "options": skills,
                "ai_recommendation": "Pick another skill for Expertise.",
            }
        )
    elif is_2024 and char_class == "Wizard" and target_level == 2:
        choices.append(
            {
                "type": "expertise_1",
                "label": "Scholar: Choose an Academic Skill for Expertise",
                "options": ["Arcana", "History", "Investigation", "Medicine", "Nature", "Religion"],
                "ai_recommendation": "Arcana or Investigation synergizes best with Wizard INT.",
            }
        )

    # 5. Structured Class / Subclass Build Choices (2014 & 2024: Fighting Style, Pact Boon, Invocations, Metamagic, Maneuvers, Infusions/Plans, Hunter)
    choices.extend(
        _build_level_up_class_choices(
            is_2024, c_lower, sub_lower, target_level, _owned_ft_names_low, choices_catalog
        )
    )

    # Deterministically compute updated spell slots for the target level
    updated_classes = [dict(c) for c in classes] if classes else []
    if not updated_classes and char_data.get("char_class"):
        updated_classes = [
            {
                "class_name": str(char_data.get("char_class")).strip(),
                "level": max(1, int(char_data.get("char_level") or 1)),
                "subclass": char_data.get("subclass"),
            }
        ]
    if updated_classes:
        matched_cls = False
        for c in updated_classes:
            if (c.get("class_name") or "").lower() == char_class.lower():
                c["level"] = target_level
                if subclass_to_use and not c.get("subclass"):
                    c["subclass"] = subclass_to_use
                matched_cls = True
                break
        if not matched_cls:
            updated_classes.append(
                {
                    "class_name": char_class,
                    "level": target_level,
                    "subclass": subclass_to_use,
                }
            )
        for c in updated_classes:
            c_prog = rules_repo.get_class_progression(c.get("class_name", ""), edition)
            if c_prog and "caster_type" in c_prog:
                c["caster_type"] = c_prog.get("caster_type")

    updated_spell_slots = calculate_max_spell_slots(
        char_class,
        target_total_level,
        subclass=subclass_to_use,
        classes=updated_classes,
        edition=edition,
    )

    return {
        "automatic_changes": static_features,
        "hp_increase": hp_increase,
        "hp_bonus_per_level": hp_bonus_per_level,
        "new_total_hp": preview_new_total_hp,
        "choices_required": choices,
        "replaceable_spells": replaceable_spells,
        "spell_swap_options": spell_swap_options,
        "multiclass_options": multiclass_options,
        "updated_proficiency_bonus": updated_pb,
        "updated_spell_slots": updated_spell_slots,
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
