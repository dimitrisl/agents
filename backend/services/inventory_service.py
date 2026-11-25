"""Deterministic inventory weight, catalog hydration, and carrying capacity service (#262).

Kept isolated from the large ``stats_service.py`` module per Epic #283's
modularity guardrail while reading catalog weights strictly from ``RulesRepository``
and campaign homebrew without hardcoding D&D item weights in Python.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

_SIZE_CAPACITY_MULTIPLIERS: Dict[str, float] = {
    "tiny": 0.5,
    "small": 1.0,
    "medium": 1.0,
    "large": 2.0,
    "huge": 4.0,
    "gargantuan": 8.0,
}

_ONE_SIZE_LARGER_MARKERS = (
    "powerful build",
    "equine build",
    "hippo build",
    "little giant",
    "brawny",
)

_ONE_SIZE_LARGER_SPECIES = (
    "goliath",
    "firbolg",
    "bugbear",
)

_ITEM_WEIGHT_ALIASES: Dict[str, str] = {
    "arrows": "arrow",
    "bolts": "crossbow bolt",
    "crossbow bolts": "crossbow bolt",
    "sling bullets": "sling bullet",
    "bullets": "sling bullet",
    "blowgun needles": "blowgun needle",
    "needles": "blowgun needle",
    "rations": "rations (1 day)",
    "torches": "torch",
    "hempen rope": "rope, hempen (50 ft.)",
    "50 ft hempen rope": "rope, hempen (50 ft.)",
    "50 ft. hempen rope": "rope, hempen (50 ft.)",
    "silk rope": "rope, silk (50 ft.)",
    "50 ft silk rope": "rope, silk (50 ft.)",
    "50 ft. silk rope": "rope, silk (50 ft.)",
    "hooded lantern": "lantern, hooded",
    "bolt case": "crossbow bolt case",
    "healing potion": "potion of healing",
    "greater healing potion": "potion of greater healing",
    "superior healing potion": "potion of superior healing",
    "supreme healing potion": "potion of supreme healing",
}


def parse_weight_lb(raw_weight: Any) -> Optional[float]:
    """Parse numeric or string D&D weights (e.g. ``'2 lb.'``, ``'1/2 lb'``) into pounds."""
    if raw_weight is None or isinstance(raw_weight, bool):
        return None
    if isinstance(raw_weight, (int, float)):
        val = float(raw_weight)
        return max(0.0, round(val, 4)) if math.isfinite(val) else None

    text = str(raw_weight).strip().lower()
    if not text:
        return None
    if re.match(r"^\s*-", text):
        return 0.0

    mixed = re.search(r"(\d+)\s+(\d+)\s*/\s*(\d+)", text)
    if mixed and int(mixed.group(3)) != 0:
        return max(0.0, round(int(mixed.group(1)) + int(mixed.group(2)) / int(mixed.group(3)), 4))

    frac = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if frac and int(frac.group(2)) != 0:
        return max(0.0, round(int(frac.group(1)) / int(frac.group(2)), 4))

    num = re.search(r"(\d+(?:\.\d+)?|\.\d+)", text)
    if not num:
        return None
    return max(0.0, round(float(num.group(1)), 4))


def _resolve_catalog_weight(
    raw_name: str,
    all_items: List[Dict[str, Any]],
    all_weapons: List[Dict[str, Any]],
) -> float:
    """Resolve per-unit weight from items.json / weapons.json / homebrew catalogs."""
    from backend.services.stats_service import _find_catalog_item, get_base_weapon

    lowered = re.sub(r"\s+", " ", str(raw_name or "").strip().lower())
    if not lowered:
        return 0.0

    # Check exact or alias match in items catalog before fuzzy weapon/armor lookup
    for candidate_name in (lowered, _ITEM_WEIGHT_ALIASES.get(lowered, "")):
        if not candidate_name:
            continue
        exact_item = next(
            (i for i in all_items if str(i.get("name") or "").strip().lower() == candidate_name),
            None,
        )
        if exact_item is not None:
            parsed = parse_weight_lb(exact_item.get("weight"))
            if parsed is not None:
                return parsed
            # Generic catalog placeholders ("Armor +1", "Ring of Protection") explicitly omit weight
            return 0.0

    matched_item = _find_catalog_item(raw_name, all_items)
    if matched_item is not None:
        parsed = parse_weight_lb(matched_item.get("weight"))
        if parsed is not None:
            return parsed

    matched_weapon = get_base_weapon(lowered, all_weapons)
    if matched_weapon is not None:
        parsed = parse_weight_lb(matched_weapon.get("weight"))
        if parsed is not None:
            return parsed

    return 0.0


def resolve_item_unit_weight_lb(
    item: Dict[str, Any],
    all_items: List[Dict[str, Any]],
    all_weapons: List[Dict[str, Any]],
) -> float:
    """Return effective single-unit weight in pounds (explicit ``weight`` > catalog lookup)."""
    explicit = parse_weight_lb(item.get("weight"))
    if explicit is not None:
        return explicit
    return _resolve_catalog_weight(str(item.get("name") or ""), all_items, all_weapons)


def resolve_weapon_unit_weight_lb(
    weapon: Dict[str, Any],
    all_weapons: List[Dict[str, Any]],
) -> float:
    """Return effective weapon weight in pounds (explicit ``weight`` > ``weapons.json`` / homebrew)."""
    from backend.services.stats_service import get_base_weapon

    explicit = parse_weight_lb(weapon.get("weight"))
    if explicit is not None:
        return explicit

    lowered = str(weapon.get("name") or "").strip().lower()
    if not lowered:
        return 0.0
    matched_weapon = get_base_weapon(lowered, all_weapons)
    if matched_weapon is not None:
        parsed = parse_weight_lb(matched_weapon.get("weight"))
        if parsed is not None:
            return parsed
    return 0.0


def compute_coin_weight_lb(currency: Any) -> float:
    """Compute D&D RAW coin weight at 50 coins per pound."""
    if not isinstance(currency, dict):
        return 0.0
    total_coins = 0
    for denom in ("cp", "sp", "ep", "gp", "pp"):
        try:
            total_coins += max(0, int(currency.get(denom) or 0))
        except (ValueError, TypeError):
            continue
    return round(total_coins / 50.0, 2)


def _has_one_size_larger_trait(
    char_data: Dict[str, Any],
    race_meta: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Detect non-stacking 'count as one size larger for carrying capacity' traits."""
    for trait in (race_meta or {}).get("traits") or []:
        tname = str((trait.get("name") if isinstance(trait, dict) else trait) or "").strip()
        tdesc = str((trait.get("description") if isinstance(trait, dict) else "") or "").lower()
        tlow = tname.lower()
        if any(m in tlow for m in _ONE_SIZE_LARGER_MARKERS):
            return tname or "Powerful Build"
        if "one size larger" in tdesc and "carrying capacity" in tdesc:
            return tname or "Powerful Build"

    for feat in char_data.get("features_traits") or []:
        fname = str((feat.get("name") if isinstance(feat, dict) else feat) or "").strip()
        fdesc = str((feat.get("description") if isinstance(feat, dict) else "") or "").lower()
        flow = fname.lower()
        if any(m in flow for m in _ONE_SIZE_LARGER_MARKERS):
            return fname
        if ("one size larger" in fdesc or "as if you were one size larger" in fdesc) and (
            "carrying capacity" in fdesc
        ):
            return fname
    race_low = str(char_data.get("race") or "").lower()
    if any(s in race_low for s in _ONE_SIZE_LARGER_SPECIES):
        return "Powerful Build"
    return None


def _has_bear_aspect_doubling(char_data: Dict[str, Any]) -> bool:
    """Detect Barbarian L6 Aspect of the Beast (Bear) without false-matching Eagle/Wolf."""
    for feat in char_data.get("features_traits") or []:
        fname = str((feat.get("name") if isinstance(feat, dict) else feat) or "").lower()
        fdesc = str((feat.get("description") if isinstance(feat, dict) else "") or "").lower()
        if "aspect of the beast" in fname:
            # Explicit selection or unambiguous Bear text (skip generic 3-way template prompt)
            has_all_options = "eagle" in fdesc and "wolf" in fdesc
            if "bear" in fname or ("bear" in fdesc and not has_all_options):
                return True
            if re.search(r"\bchosen\s*:\s*bear\b|\btotem\s*:\s*bear\b", fdesc):
                return True
        if "carrying capacity" in fdesc and "doubled" in fdesc and "bear" in (fname + " " + fdesc):
            if not ("eagle" in fdesc and "wolf" in fdesc):
                return True
    return False


def compute_carrying_capacity(
    char_data: Dict[str, Any],
    race_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[float, float, List[str]]:
    """Compute D&D 2014/2024 carrying capacity ``15 * STR * multiplier`` and multipliers."""
    stats = char_data.get("stats") or {}
    try:
        str_score = max(1, int(stats.get("STR", 10) if isinstance(stats, dict) else 10))
    except (ValueError, TypeError):
        str_score = 10

    raw_size = str((race_meta or {}).get("size") or char_data.get("size") or "Medium").strip()
    size_mult = _SIZE_CAPACITY_MULTIPLIERS.get(raw_size.lower(), 1.0)
    multiplier = size_mult
    sources: List[str] = [f"15 × STR {str_score}"]
    if size_mult != 1.0:
        sources.append(f"{raw_size} size (×{size_mult:g})")

    one_size_source = _has_one_size_larger_trait(char_data, race_meta)
    if one_size_source:
        multiplier *= 2.0
        sources.append(f"{one_size_source} (×2)")

    if _has_bear_aspect_doubling(char_data):
        multiplier *= 2.0
        sources.append("Aspect of the Beast: Bear (×2)")

    capacity = round(15.0 * str_score * multiplier, 1)
    return capacity, multiplier, sources


def evaluate_encumbrance_status(
    total_weight_lb: float,
    capacity_lb: float,
) -> Tuple[str, float, float, float]:
    """Return status band plus Variant (5x/10x STR*mult) and Push/Drag/Lift (2x capacity) limits."""
    encumbered_lb = round(capacity_lb / 3.0, 1)
    heavily_lb = round((2.0 * capacity_lb) / 3.0, 1)
    push_drag_lift_lb = round(2.0 * capacity_lb, 1)

    if total_weight_lb > capacity_lb:
        status = "over_capacity"
    elif total_weight_lb > heavily_lb:
        status = "heavily_encumbered"
    elif total_weight_lb > encumbered_lb:
        status = "encumbered"
    else:
        status = "unencumbered"

    return status, encumbered_lb, heavily_lb, push_drag_lift_lb


def sync_character_inventory(
    char_data: Dict[str, Any],
    *,
    repo: Any = None,
    all_items: Optional[List[Dict[str, Any]]] = None,
    all_weapons: Optional[List[Dict[str, Any]]] = None,
    homebrew_content: Optional[List[Dict[str, Any]]] = None,
    race_meta: Optional[Dict[str, Any]] = None,
    preserve_existing_on_miss: bool = False,
) -> Dict[str, Any]:
    """Hydrate resolved item/weapon weights and compute inventory totals & capacity in-place."""
    if not isinstance(char_data, dict):
        return char_data

    if repo is None:
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()

    from backend.services.stats_service import _merge_homebrew_items, _merge_homebrew_weapons

    if all_items is None:
        all_items = _merge_homebrew_items(repo.get_all_items(), homebrew_content)
    if all_weapons is None:
        all_weapons = _merge_homebrew_weapons(repo.get_all_weapons(), homebrew_content)

    if race_meta is None:
        race_name = str(char_data.get("race") or "").strip()
        edition = str(
            char_data.get("dnd_edition") or char_data.get("ruleset_version") or "2014 Edition"
        )
        race_meta = repo.get_race_data(race_name, edition) if race_name else None

    equipment_lb = 0.0
    for eq in char_data.get("equipment") or []:
        if not isinstance(eq, dict):
            continue
        unit_w = resolve_item_unit_weight_lb(eq, all_items, all_weapons)
        if unit_w == 0.0 and preserve_existing_on_miss and eq.get("weight") is None:
            prev_w = parse_weight_lb(eq.get("resolved_weight_lb"))
            if prev_w is not None and prev_w > 0.0:
                unit_w = prev_w
        eq["resolved_weight_lb"] = round(unit_w, 2)
        if not eq.get("weight_ignored"):
            qty = eq.get("quantity")
            qty_num = max(0, int(qty)) if qty is not None else 1
            equipment_lb += unit_w * qty_num

    weapons_lb = 0.0
    for w in char_data.get("weapons") or []:
        if not isinstance(w, dict):
            continue
        unit_w = resolve_weapon_unit_weight_lb(w, all_weapons)
        if unit_w == 0.0 and preserve_existing_on_miss and w.get("weight") is None:
            prev_w = parse_weight_lb(w.get("resolved_weight_lb"))
            if prev_w is not None and prev_w > 0.0:
                unit_w = prev_w
        w["resolved_weight_lb"] = round(unit_w, 2)
        if not w.get("weight_ignored"):
            weapons_lb += unit_w

    coins_lb = compute_coin_weight_lb(char_data.get("currency"))
    equipment_lb = round(equipment_lb, 2)
    weapons_lb = round(weapons_lb, 2)
    total_weight_lb = round(equipment_lb + weapons_lb + coins_lb, 1)

    capacity_lb, multiplier, capacity_sources = compute_carrying_capacity(char_data, race_meta)
    status, enc_lb, heavy_lb, push_lb = evaluate_encumbrance_status(total_weight_lb, capacity_lb)

    char_data["total_weight_lb"] = total_weight_lb
    char_data["carrying_capacity_lb"] = capacity_lb
    char_data["encumbrance_status"] = status
    char_data["weight_breakdown"] = {
        "equipment_lb": equipment_lb,
        "weapons_lb": weapons_lb,
        "coins_lb": coins_lb,
        "multiplier": round(multiplier, 2),
        "capacity_sources": capacity_sources,
        "encumbered_threshold_lb": enc_lb,
        "heavily_encumbered_threshold_lb": heavy_lb,
        "push_drag_lift_lb": push_lb,
    }
    return char_data
