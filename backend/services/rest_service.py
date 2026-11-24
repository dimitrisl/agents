"""Deterministic Short Rest, Long Rest, and campaign DM control reset helpers."""

from __future__ import annotations

import copy
import math
import re
from typing import Any, Dict, List, Optional

from backend.core.schemas import DmModifiersSchema
from backend.repositories.rules_repository import RulesRepository
from backend.services.stats_service import sync_character_stats

_SHORT_REST_2024_SINGLE_RECHARGE_RE = re.compile(
    r"^(rage|second wind|channel divinity|wild shape)$", re.IGNORECASE
)

_DM_CONTROL_DEFAULTS = {
    "exhaustion_bypass": False,
    "magic_items_suppressed": False,
    "dm_short_rest_unlocked": False,
    "dm_long_rest_unlocked": False,
    "dm_level_up_unlocked": False,
}


def dm_control_reset_fields() -> Dict[str, Any]:
    """Fresh default values for all DM-managed campaign control fields."""
    return {
        **_DM_CONTROL_DEFAULTS,
        "dm_modifiers": DmModifiersSchema().model_dump(),
    }


def is_2024_edition(char_doc: Dict[str, Any]) -> bool:
    return "2024" in str(char_doc.get("dnd_edition") or char_doc.get("ruleset_version") or "")


def is_deceased_by_exhaustion(char_doc: Dict[str, Any]) -> bool:
    exh = max(0, min(6, int(char_doc.get("exhaustion_level") or 0)))
    return exh >= 6 and not bool(char_doc.get("exhaustion_bypass", False))


def available_hit_dice(char_doc: Dict[str, Any]) -> int:
    level = max(1, int(char_doc.get("char_level") or 1))
    used = max(0, int(char_doc.get("hit_dice_used") or 0))
    return max(0, level - used)


def _restore_all_spell_slots(spell_slots: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    restored: Dict[str, Any] = {}
    for k, v in (spell_slots or {}).items():
        if isinstance(v, dict):
            entry = {**v, "used": 0}
            if "pact_used" in entry:
                entry["pact_used"] = 0
            restored[k] = entry
        else:
            restored[k] = v
    return restored


def _restore_pact_magic_slots(
    char_doc: Dict[str, Any], spell_slots: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not isinstance(spell_slots, dict):
        return spell_slots or {}

    updated = {k: (dict(v) if isinstance(v, dict) else v) for k, v in spell_slots.items()}
    classes = char_doc.get("classes") or []
    warlock_levels = sum(
        int(c.get("level", 0) or 0)
        for c in classes
        if isinstance(c, dict) and "warlock" in str(c.get("class_name") or "").lower()
    )
    if warlock_levels <= 0 and "warlock" in str(char_doc.get("char_class") or "").lower():
        warlock_levels = int(char_doc.get("char_level") or 1)

    if warlock_levels <= 0 and "pact" not in updated:
        return updated

    if "pact" in updated and isinstance(updated["pact"], dict):
        pact_entry = updated["pact"]
        pact_lvl = pact_entry.get("level")
        pact_entry["used"] = 0
        if pact_lvl is not None:
            lvl_key = f"level_{pact_lvl}"
            lvl_slot = updated.get(lvl_key)
            if isinstance(lvl_slot, dict):
                prev_pact_used = int(lvl_slot.get("pact_used", 0) or 0)
                lvl_slot["pact_used"] = 0
                lvl_slot["used"] = max(0, int(lvl_slot.get("used", 0) or 0) - prev_pact_used)
        return updated

    # Pure Warlock or non-multiclass caster: Pact Magic uses standard leveled slots.
    has_other_caster = any(
        isinstance(c, dict)
        and "warlock" not in str(c.get("class_name") or "").lower()
        and str(c.get("caster_type") or "").lower() in ("full", "half", "third")
        for c in classes
    )
    if not has_other_caster:
        for slot in updated.values():
            if isinstance(slot, dict) and "used" in slot:
                slot["used"] = 0

    return updated


def _recharge_short_rest_resources(
    resources: Optional[List[Any]],
    is_2024: bool,
    sorcerer_level: int = 0,
    has_sorcerous_restoration: bool = False,
) -> List[Any]:
    recharged: List[Any] = []
    for res in resources or []:
        if not isinstance(res, dict):
            recharged.append(res)
            continue
        r_copy = dict(res)
        r_max = int(r_copy.get("max", 0) or 0)
        cur = int(r_copy.get("current", 0) or 0)
        name_clean = str(r_copy.get("name") or "").strip()
        if is_2024 and _SHORT_REST_2024_SINGLE_RECHARGE_RE.match(name_clean):
            r_copy["current"] = min(r_max, cur + 1)
        elif (
            not is_2024
            and (sorcerer_level >= 20 or has_sorcerous_restoration)
            and name_clean.lower() in ("sorcery points", "sorcery point", "font of magic")
        ):
            # 2014 PHB L20 Capstone: Sorcerous Restoration regains 4 SP on a Short Rest.
            r_copy["current"] = min(r_max, cur + 4)
        elif str(r_copy.get("recharge") or "").lower() == "short":
            r_copy["current"] = r_max
        recharged.append(r_copy)
    return recharged


def _recharge_long_rest_resources(resources: Optional[List[Any]]) -> List[Any]:
    recharged: List[Any] = []
    for res in resources or []:
        if not isinstance(res, dict):
            recharged.append(res)
            continue
        r_copy = dict(res)
        r_copy["current"] = int(r_copy.get("max", 0) or 0)
        recharged.append(r_copy)
    return recharged


def _sync_character(
    char_doc: Dict[str, Any], homebrew_content: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    if not char_doc.get("stats"):
        return copy.deepcopy(char_doc)
    preserved_slots = copy.deepcopy(char_doc.get("spell_slots"))
    preserved_resources = copy.deepcopy(char_doc.get("class_resources"))
    repo = RulesRepository()
    edition = char_doc.get("dnd_edition", "2014 Edition")
    class_data = repo.get_class_progression(char_doc.get("char_class"), edition)
    synced = sync_character_stats(char_doc, class_data, homebrew_content=homebrew_content)
    if preserved_slots is not None:
        synced["spell_slots"] = preserved_slots
    if preserved_resources is not None:
        synced["class_resources"] = preserved_resources
    return synced


def _class_level_for(char_doc: Dict[str, Any], target: str) -> int:
    lvl = 0
    for c in char_doc.get("classes") or []:
        if isinstance(c, dict) and str(c.get("class_name") or "").strip().lower() == target:
            try:
                lvl += max(0, int(c.get("level") or 0))
            except (TypeError, ValueError):
                pass
    if lvl == 0 and str(char_doc.get("char_class") or "").strip().lower() == target:
        try:
            lvl = max(1, int(char_doc.get("char_level") or 1))
        except (TypeError, ValueError):
            lvl = 1
    return lvl


def _find_resource(resources: Optional[List[Any]], *aliases: str) -> Optional[Dict[str, Any]]:
    wanted = {a.strip().lower() for a in aliases}
    for res in resources or []:
        if isinstance(res, dict) and str(res.get("name") or "").strip().lower() in wanted:
            return res
    return None


def _normalize_recovery_map(raw_slots: Optional[Dict[str, int]], label: str) -> Dict[int, int]:
    cleaned: Dict[int, int] = {}
    for raw_k, raw_v in (raw_slots or {}).items():
        key_str = str(raw_k).strip().lower().removeprefix("level_")
        try:
            lvl = int(key_str)
            cnt = int(raw_v or 0)
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid {label} slot specification: {raw_k}: {raw_v}") from err
        if cnt < 0:
            raise ValueError(f"{label} slot count cannot be negative.")
        if cnt == 0:
            continue
        cleaned[lvl] = cleaned.get(lvl, 0) + cnt
    return cleaned


def _recover_spell_slots_map(
    spell_slots: Dict[str, Any],
    resources: List[Any],
    counts_by_level: Dict[int, int],
    *,
    class_level: int,
    feature_name: str,
) -> None:
    if not counts_by_level:
        return
    if class_level <= 0:
        raise ValueError(f"{feature_name} requires levels in the corresponding class.")
    budget = math.ceil(class_level / 2)
    total_cost = 0
    for lvl, cnt in counts_by_level.items():
        if lvl < 1 or lvl >= 6:
            raise ValueError(f"{feature_name} cannot recover spell slots of 6th level or higher.")
        total_cost += lvl * cnt
    if total_cost > budget:
        raise ValueError(
            f"{feature_name} budget exceeded ({total_cost} requested, max {budget} combined slot levels)."
        )

    res = _find_resource(resources, feature_name.lower())
    if not res or int(res.get("current") or 0) < 1:
        raise ValueError(f"No {feature_name} uses remaining until you finish a Long Rest.")

    for lvl, cnt in counts_by_level.items():
        slot_entry = spell_slots.get(f"level_{lvl}")
        if not isinstance(slot_entry, dict) or int(slot_entry.get("used") or 0) < cnt:
            raise ValueError(f"Not enough expended Level {lvl} spell slots to recover.")

    res["current"] = int(res["current"]) - 1
    for lvl, cnt in counts_by_level.items():
        slot_entry = spell_slots[f"level_{lvl}"]
        slot_entry["used"] = max(0, int(slot_entry.get("used") or 0) - cnt)


def apply_short_rest(
    char_doc: Dict[str, Any],
    dice_to_spend: int = 0,
    hp_healed: int = 0,
    homebrew_content: Optional[List[Dict[str, Any]]] = None,
    arcane_recovery_slots: Optional[Dict[str, int]] = None,
    natural_recovery_slots: Optional[Dict[str, int]] = None,
    harness_divine_power_slot: Optional[int] = None,
) -> Dict[str, Any]:
    """Applies a deterministic Short Rest, clearing the 1-shot DM unlock."""
    if is_deceased_by_exhaustion(char_doc):
        raise ValueError("Dead characters (Exhaustion Level 6) cannot benefit from a Short Rest.")

    avail = available_hit_dice(char_doc)
    spent = int(dice_to_spend or 0)
    if spent < 0:
        raise ValueError("Cannot spend negative Hit Dice.")
    if spent > avail:
        raise ValueError(f"Only {avail} Hit Dice remaining.")

    updated = copy.deepcopy(char_doc)
    is_2024 = is_2024_edition(updated)

    arcane_map = _normalize_recovery_map(arcane_recovery_slots, "Arcane Recovery")
    natural_map = _normalize_recovery_map(natural_recovery_slots, "Natural Recovery")

    # Pre-check Harness Divine Power Channel Divinity availability BEFORE short-rest recharge
    if harness_divine_power_slot is not None:
        cleric_lvl = _class_level_for(updated, "cleric")
        paladin_lvl = _class_level_for(updated, "paladin")
        if cleric_lvl < 2 and paladin_lvl < 3:
            raise ValueError("Harness Divine Power requires Cleric level 2+ or Paladin level 3+.")
        total_lvl = max(1, int(updated.get("char_level") or 1))
        pb = math.ceil(total_lvl / 4) + 1
        max_hdp = math.ceil(pb / 2)
        if harness_divine_power_slot < 1 or harness_divine_power_slot > max_hdp:
            raise ValueError(f"Harness Divine Power can only recover slots up to level {max_hdp}.")
        cd_before = _find_resource(updated.get("class_resources"), "channel divinity")
        if not cd_before or int(cd_before.get("current") or 0) < 1:
            raise ValueError("No Channel Divinity uses remaining for Harness Divine Power.")

    updated["hit_dice_used"] = max(0, int(updated.get("hit_dice_used") or 0)) + spent
    updated["spell_slots"] = _restore_pact_magic_slots(updated, updated.get("spell_slots"))
    sorc_lvl = _class_level_for(updated, "sorcerer")
    has_sorc_restoration = any(
        isinstance(f, dict) and "sorcerous restoration" in str(f.get("name") or "").lower()
        for f in (updated.get("features_traits") or [])
    )
    updated["class_resources"] = _recharge_short_rest_resources(
        updated.get("class_resources"),
        is_2024,
        sorcerer_level=sorc_lvl,
        has_sorcerous_restoration=has_sorc_restoration,
    )

    # Apply Arcane Recovery, Natural Recovery, and Harness Divine Power on spell slots & pools
    if arcane_map or natural_map or harness_divine_power_slot is not None:
        if not isinstance(updated.get("spell_slots"), dict):
            updated["spell_slots"] = {}
        resources_list = updated.get("class_resources") or []
        if not isinstance(resources_list, list):
            resources_list = []
            updated["class_resources"] = resources_list

        if (arcane_map and _find_resource(resources_list, "arcane recovery") is None) or (
            natural_map and _find_resource(resources_list, "natural recovery") is None
        ):
            from backend.services.class_resources_service import sync_class_resources

            hydrated_classes = updated.get("classes") or []
            if not hydrated_classes and updated.get("char_class"):
                hydrated_classes = [
                    {
                        "class_name": updated.get("char_class"),
                        "level": int(updated.get("char_level") or 1),
                        "subclass": updated.get("subclass"),
                    }
                ]
            resources_list = sync_class_resources(
                resources_list,
                hydrated_classes,
                updated.get("stats") or {},
                updated.get("dnd_edition") or updated.get("ruleset_version"),
                race=updated.get("race"),
                total_level=int(updated.get("char_level") or 1),
                subclass=updated.get("subclass"),
                features_traits=updated.get("features_traits"),
                char_class=updated.get("char_class"),
            )
            updated["class_resources"] = resources_list

        if arcane_map:
            _recover_spell_slots_map(
                updated["spell_slots"],
                resources_list,
                arcane_map,
                class_level=_class_level_for(updated, "wizard"),
                feature_name="Arcane Recovery",
            )
        if natural_map:
            druid_lvl = _class_level_for(updated, "druid")
            classes_list = updated.get("classes") or []
            primary_class_low = str(updated.get("char_class") or "").strip().lower()
            has_land = any(
                isinstance(c, dict)
                and str(c.get("class_name") or "").strip().lower() == "druid"
                and "land" in str(c.get("subclass") or "").lower()
                for c in classes_list
            ) or (
                (not classes_list or primary_class_low == "druid")
                and "land" in str(updated.get("subclass") or "").lower()
            )
            has_nr_feat = any(
                isinstance(f, dict) and "natural recovery" in str(f.get("name") or "").lower()
                for f in (updated.get("features_traits") or [])
            )
            min_druid_lvl = 2 if (not is_2024 or has_nr_feat) else 6
            if not (has_land or has_nr_feat) or druid_lvl < min_druid_lvl:
                raise ValueError(
                    "Natural Recovery requires Circle of the Land Druid (Level 2+ in 2014 / Level 6+ in 2024)."
                )
            _recover_spell_slots_map(
                updated["spell_slots"],
                resources_list,
                natural_map,
                class_level=druid_lvl,
                feature_name="Natural Recovery",
            )
        if harness_divine_power_slot is not None:
            cd_after = _find_resource(resources_list, "channel divinity")
            hdp_entry = updated["spell_slots"].get(f"level_{harness_divine_power_slot}")
            if not isinstance(hdp_entry, dict) or int(hdp_entry.get("used") or 0) < 1:
                raise ValueError(
                    f"No expended Level {harness_divine_power_slot} spell slots to recover via Harness Divine Power."
                )
            if not cd_after or int(cd_after.get("current") or 0) < 1:
                raise ValueError("No Channel Divinity uses remaining for Harness Divine Power.")
            cd_after["current"] = int(cd_after["current"]) - 1
            hdp_entry["used"] = max(0, int(hdp_entry.get("used") or 0) - 1)

    updated["dm_short_rest_unlocked"] = False

    synced = _sync_character(updated, homebrew_content)
    hp_max = max(1, int(synced.get("hp_max") or 1))
    hp_before = max(0, int(synced.get("hp_current") or 0))
    healed = 0 if spent == 0 else max(0, int(hp_healed or 0))
    synced["hp_current"] = min(hp_max, hp_before + healed)
    if hp_before == 0 and synced["hp_current"] > 0:
        synced["death_saves"] = {"successes": 0, "failures": 0}
    return synced


def apply_long_rest(
    char_doc: Dict[str, Any],
    homebrew_content: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Applies an edition-aware Long Rest and clears any pending DM Long Rest unlock."""
    if is_deceased_by_exhaustion(char_doc):
        raise ValueError("Dead characters (Exhaustion Level 6) cannot benefit from a Long Rest.")

    updated = copy.deepcopy(char_doc)
    is_2024 = is_2024_edition(updated)
    total_level = max(1, int(updated.get("char_level") or 1))
    current_hd_used = max(0, int(updated.get("hit_dice_used") or 0))

    if is_2024:
        updated["hit_dice_used"] = 0
    else:
        recovered = max(1, total_level // 2)
        updated["hit_dice_used"] = max(0, current_hd_used - recovered)

    updated["exhaustion_level"] = max(0, int(updated.get("exhaustion_level") or 0) - 1)
    updated["hp_temp"] = 0
    updated["concentrating_on"] = None
    updated["death_saves"] = {"successes": 0, "failures": 0}
    updated["spell_slots"] = _restore_all_spell_slots(updated.get("spell_slots"))
    updated["class_resources"] = _recharge_long_rest_resources(updated.get("class_resources"))
    updated["dm_long_rest_unlocked"] = False

    if not updated.get("stats"):
        if (not is_2024) and updated["exhaustion_level"] < 4 and updated.get("base_hp_max"):
            updated["hp_max"] = updated["base_hp_max"]

    synced = _sync_character(updated, homebrew_content)
    synced["hp_current"] = max(1, int(synced.get("hp_max") or 1))
    return synced


def reset_campaign_dm_controls(
    char_doc: Dict[str, Any],
    homebrew_content: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resets DM campaign flags/modifiers on a detached hero and re-syncs solo math."""
    updated = copy.deepcopy(char_doc)
    updated.update(dm_control_reset_fields())
    return _sync_character(updated, homebrew_content)
