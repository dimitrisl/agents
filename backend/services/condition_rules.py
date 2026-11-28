"""Pure deterministic D&D 2014 & 2024 Condition Effects, Countermeasures ("Antidotes"),
and Damage Defense Derivation helpers (#275).

Kept dependency-free from FastAPI/MongoDB so `stats_service.py`, routers, and
unit tests stay cohesive and strictly mirrored with `client/src/app/core/rules/conditions.ts`.
"""

from typing import Any, Dict, List, Optional, Tuple

SPEED_ZERO_CONDITIONS = frozenset(
    {
        "grappled",
        "restrained",
        "paralyzed",
        "stunned",
        "unconscious",
        "petrified",
    }
)

AUTO_FAIL_STR_DEX_CONDITIONS = frozenset(
    {
        "paralyzed",
        "stunned",
        "unconscious",
        "petrified",
    }
)

INCAPACITATING_CONDITIONS = frozenset(
    {
        "incapacitated",
        "unconscious",
        "paralyzed",
        "petrified",
        "stunned",
    }
)


def _is_2024(char_data: Dict[str, Any], edition: Optional[str] = None) -> bool:
    if edition is not None and str(edition).strip():
        return "2024" in str(edition)
    ed_text = " ".join(
        str(x or "")
        for x in (
            char_data.get("dnd_edition"),
            char_data.get("ruleset_version"),
        )
    )
    return "2024" in ed_text


def _normalize_conditions(conditions: Any) -> List[str]:
    if not isinstance(conditions, (list, tuple, set)):
        return []
    out: List[str] = []
    seen = set()
    for raw in conditions:
        clean = str(raw or "").strip().lower()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def has_speed_zero_condition(conditions: Any, is_2024: bool = False) -> bool:
    """
    True if any active condition sets effective walking speed to 0 ft.

    2014 Stunned says "can't move"; 2024 Stunned only applies Incapacitated (no Speed 0),
    so `stunned` is excluded when `is_2024` is True.
    """
    conds = _normalize_conditions(conditions)
    locked = SPEED_ZERO_CONDITIONS - {"stunned"} if is_2024 else SPEED_ZERO_CONDITIONS
    return any(c in locked for c in conds)


def get_class_level(char_data: Dict[str, Any], class_name: str) -> int:
    target = class_name.strip().lower()
    best = 0
    for cls in char_data.get("classes") or []:
        if isinstance(cls, dict) and str(cls.get("class_name") or "").strip().lower() == target:
            try:
                best = max(best, int(cls.get("level") or 0))
            except (TypeError, ValueError):
                pass
    if best == 0 and str(char_data.get("char_class") or "").strip().lower() == target:
        try:
            best = max(best, int(char_data.get("char_level") or 1))
        except (TypeError, ValueError):
            best = 1
    return best


def _has_subclass(
    char_data: Dict[str, Any], class_name: str, subclass_frag: str, min_lvl: int = 1
) -> bool:
    target_cls = class_name.strip().lower()
    frag = subclass_frag.strip().lower()
    for cls in char_data.get("classes") or []:
        if not isinstance(cls, dict):
            continue
        if (
            str(cls.get("class_name") or "").strip().lower() == target_cls
            and frag in str(cls.get("subclass") or "").strip().lower()
        ):
            try:
                if int(cls.get("level") or 0) >= min_lvl:
                    return True
            except (TypeError, ValueError):
                pass
    if (
        str(char_data.get("char_class") or "").strip().lower() == target_cls
        and frag in str(char_data.get("subclass") or "").strip().lower()
    ):
        try:
            if int(char_data.get("char_level") or 1) >= min_lvl:
                return True
        except (TypeError, ValueError):
            pass
    return False


def _feature_names_lower(char_data: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for f in char_data.get("features_traits") or []:
        name = f.get("name") if isinstance(f, dict) else f
        clean = str(name or "").strip().lower()
        if clean:
            names.append(clean)
    return names


def _has_sense(char_data: Dict[str, Any], sense_keyword: str) -> Optional[str]:
    kw = sense_keyword.strip().lower()
    for s in char_data.get("senses") or []:
        raw = str(s or "").strip()
        if kw in raw.lower():
            return raw
    return None


def detect_condition_countermeasures(
    char_data: Dict[str, Any], edition: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Identify class, subclass, species, feat, and sense countermeasures ("antidotes")
    that neutralize or grant advantage against D&D conditions (2014 & 2024 parity).
    """
    is_2024 = _is_2024(char_data, edition)
    ft_names = _feature_names_lower(char_data)
    race = str(char_data.get("race") or "").strip().lower()
    senses = [str(s or "").strip() for s in (char_data.get("senses") or []) if str(s or "").strip()]
    countermeasures: List[Dict[str, str]] = []

    def add(condition: str, source: str, kind: str, detail: str) -> None:
        countermeasures.append(
            {
                "condition": condition,
                "source": source,
                "kind": kind,
                "detail": detail,
            }
        )

    # 1. Barbarian (Berserker L6+) Mindless Rage
    if any("mindless rage" in fn for fn in ft_names) or _has_subclass(
        char_data, "barbarian", "berserker", 6
    ):
        add("Charmed", "Mindless Rage", "immune", "Immune to Charmed while Raging")
        add("Frightened", "Mindless Rage", "immune", "Immune to Frightened while Raging")

    # 2. Paladin L10+ Aura of Courage
    if (
        any("aura of courage" in fn for fn in ft_names)
        or get_class_level(char_data, "paladin") >= 10
    ):
        add("Frightened", "Aura of Courage", "immune", "Immune to Frightened")

    # 3. Paladin (Devotion L7+) Aura of Devotion
    if any("aura of devotion" in fn for fn in ft_names) or _has_subclass(
        char_data, "paladin", "devotion", 7
    ):
        add("Charmed", "Aura of Devotion", "immune", "Immune to Charmed")

    # 4. Monk: 2014 Stillness of Mind (L7) & Purity of Body (L10) vs 2024 Self-Restoration (L10)
    monk_lvl = get_class_level(char_data, "monk")
    if is_2024:
        if any("self-restoration" in fn for fn in ft_names) or monk_lvl >= 10:
            for cond in ("Charmed", "Frightened", "Poisoned"):
                add(
                    cond,
                    "Self-Restoration",
                    "action_end",
                    f"Bonus Action (no Focus cost) to end {cond}",
                )
    else:
        if any("stillness of mind" in fn for fn in ft_names) or monk_lvl >= 7:
            for cond in ("Charmed", "Frightened"):
                add(
                    cond,
                    "Stillness of Mind",
                    "action_end",
                    f"Use your Action to end {cond}",
                )
        if any("purity of body" in fn for fn in ft_names) or monk_lvl >= 10:
            add(
                "Poisoned",
                "Purity of Body",
                "immune",
                "Immune to disease and poison (2014 Monk L10)",
            )

    # 5. Druid Circle of the Land L10+ Nature's Ward (2014 poison/disease & Poisoned; 2024 Poisoned condition immunity)
    if any("nature's ward" in fn for fn in ft_names) or _has_subclass(
        char_data, "druid", "land", 10
    ):
        nw_detail = (
            "Immune to the Poisoned condition (2024 Nature's Ward)"
            if is_2024
            else "Immune to poison & disease (2014 Land Druid)"
        )
        add("Poisoned", "Nature's Ward", "immune", nw_detail)

    # 6. Species / Ancestral Antidotes
    has_fey_ancestry = any("fey ancestry" in fn for fn in ft_names) or any(
        k in race for k in ("elf", "eladrin", "drow", "shadar-kai", "astral")
    )
    if has_fey_ancestry:
        adv_detail = (
            "Advantage on saving throws to avoid or end Charmed"
            if is_2024
            else "Advantage on saving throws against being Charmed"
        )
        add("Charmed", "Fey Ancestry", "advantage", adv_detail)

    if any(fn == "brave" or "brave (" in fn for fn in ft_names) or "halfling" in race:
        add(
            "Frightened",
            "Brave",
            "advantage",
            "Advantage on saving throws against being Frightened",
        )

    if any("stout resilience" in fn for fn in ft_names) or ("stout" in race and "halfling" in race):
        add(
            "Poisoned",
            "Stout Resilience",
            "advantage",
            "Advantage on saving throws against poison (+ Poison Resistance)",
        )

    if any("dwarven resilience" in fn for fn in ft_names) or "dwarf" in race:
        adv_detail = (
            "Advantage on saves to avoid or end Poisoned (+ Poison Resistance)"
            if is_2024
            else "Advantage on saving throws against poison (+ Poison Resistance)"
        )
        add("Poisoned", "Dwarven Resilience", "advantage", adv_detail)

    if any("constructed resilience" in fn for fn in ft_names) or "warforged" in race:
        add(
            "Poisoned",
            "Constructed Resilience",
            "advantage",
            "Advantage on saving throws vs poisoned/poison (+ Poison Resistance)",
        )

    # 7. Special Senses: Blindsight / Truesight mitigate Blinded & Hidden/Invisible targets
    blind_sense = _has_sense(char_data, "blindsight") or (
        "Blindsight 10 ft."
        if any("blind fighting" in fn for fn in ft_names)
        else (
            "Blindsight 30 ft."
            if (is_2024 and any("blindsight" in fn for fn in ft_names))
            else None
        )
    )
    if blind_sense:
        add(
            "Blinded",
            blind_sense,
            "sense_mitigation",
            f"{blind_sense}: perceives surroundings & targets within range without sight",
        )
    true_sense = next((s for s in senses if "truesight" in s.lower()), None)
    if true_sense:
        add(
            "Blinded",
            true_sense,
            "sense_mitigation",
            f"{true_sense}: sees normally within range and penetrates magical darkness/invisibility",
        )

    # Deduplicate preserving order
    seen_keys = set()
    unique: List[Dict[str, str]] = []
    for entry in countermeasures:
        key = (entry["condition"].lower(), entry["source"].lower())
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(entry)
    return unique


def _normalize_defense_list(items: Any) -> List[str]:
    if not isinstance(items, (list, tuple, set)):
        return []
    out: List[str] = []
    seen = set()
    for item in items:
        label = str(item or "").strip()
        low = label.lower()
        if not label:
            continue
        if "draconic ancestry element" in low or "fiendish legacy element" in low:
            continue
        if low not in seen:
            seen.add(low)
            out.append(label)
    return out


def compute_damage_defense_state(
    char_data: Dict[str, Any],
    race_meta: Optional[Dict[str, Any]] = None,
    edition: Optional[str] = None,
) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    """
    Compute deterministic `(merged_resist, merged_immune, merged_vuln, derived_resist, derived_immune)`.
    Subtracts `char_data['derived_damage_resistances' / 'derived_damage_immunities']` before
    merging remaining custom user entries so derived defenses never stay sticky after edition,
    race, or feature changes.
    """
    is_2024 = _is_2024(char_data, edition)
    ft_entries = char_data.get("features_traits") or []
    ft_names = _feature_names_lower(char_data)

    resistances_list = [
        str(r).strip()
        for r in ((race_meta or {}).get("damage_resistances") or [])
        if str(r).strip()
    ]
    immunities_list = [
        str(r).strip() for r in ((race_meta or {}).get("damage_immunities") or []) if str(r).strip()
    ]
    vulnerabilities_list: List[str] = []

    race_low = str(char_data.get("race") or "").strip().lower()
    if "warforged" in race_low and "Poison" not in resistances_list:
        resistances_list.append("Poison")

    for f in ft_entries:
        fn = str((f.get("name") if isinstance(f, dict) else f) or "").strip().lower()
        fd = str((f.get("description") if isinstance(f, dict) else "") or "").strip().lower()
        if "soul of the forge" in fn or "infernal constitution" in fn:
            if "Fire" not in resistances_list:
                resistances_list.append("Fire")
        if "infernal constitution" in fn:
            for elem in ("Cold", "Poison"):
                if elem not in resistances_list:
                    resistances_list.append(elem)
        if "radiant soul" in fn and "Radiant" not in resistances_list:
            resistances_list.append("Radiant")
        if (
            "necrotic husk" in fn or "inured to undeath" in fn
        ) and "Necrotic" not in resistances_list:
            resistances_list.append("Necrotic")
        if "spell resistance" in fn and "Spell Damage (Abjurer)" not in resistances_list:
            resistances_list.append("Spell Damage (Abjurer)")
        if "constructed resilience" in fn and "Poison" not in resistances_list:
            resistances_list.append("Poison")
        if "draconic ancestry" in fn:
            for elem_word, res_label in (
                ("fire", "Fire"),
                ("cold", "Cold"),
                ("lightning", "Lightning"),
                ("acid", "Acid"),
                ("poison", "Poison"),
            ):
                if elem_word in fd:
                    resistances_list = [
                        res_label if "draconic ancestry element" in r.lower() else r
                        for r in resistances_list
                    ]
                    if res_label not in resistances_list:
                        resistances_list.append(res_label)
                    break

    # Deterministic immunities: 2014 Monk L10 Purity of Body / 2014 Land Druid L10 Nature's Ward
    if not is_2024:
        monk_lvl = get_class_level(char_data, "monk")
        if monk_lvl >= 10 or any("purity of body" in fn for fn in ft_names):
            if "Poison" not in immunities_list:
                immunities_list.append("Poison")
        if _has_subclass(char_data, "druid", "land", 10) or any(
            "nature's ward" in fn for fn in ft_names
        ):
            if "Poison" not in immunities_list:
                immunities_list.append("Poison")

    derived_res = _normalize_defense_list(resistances_list)
    derived_imm = _normalize_defense_list(immunities_list)

    prev_derived_res = {
        str(x or "").strip().lower()
        for x in (char_data.get("derived_damage_resistances") or [])
        if str(x or "").strip()
    }
    prev_derived_imm = {
        str(x or "").strip().lower()
        for x in (char_data.get("derived_damage_immunities") or [])
        if str(x or "").strip()
    }

    def _merge_manual(base: List[str], existing: Any, prev_derived: set[str]) -> List[str]:
        manual_filtered = [
            item
            for item in (list(existing) if isinstance(existing, (list, tuple, set)) else [])
            if str(item or "").strip().lower() not in prev_derived
        ]
        return _normalize_defense_list(list(base) + manual_filtered)

    merged_resist = _merge_manual(
        derived_res, char_data.get("damage_resistances"), prev_derived_res
    )
    merged_immune = _merge_manual(derived_imm, char_data.get("damage_immunities"), prev_derived_imm)
    merged_vuln = _merge_manual(
        vulnerabilities_list, char_data.get("damage_vulnerabilities"), set()
    )
    return merged_resist, merged_immune, merged_vuln, derived_res, derived_imm


def derive_damage_defenses(
    char_data: Dict[str, Any],
    race_meta: Optional[Dict[str, Any]] = None,
    edition: Optional[str] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Compute deterministic `(damage_resistances, damage_immunities, damage_vulnerabilities)`
    while subtracting previously derived entries before merging custom overrides.
    """
    merged_res, merged_imm, merged_vuln, _, _ = compute_damage_defense_state(
        char_data, race_meta=race_meta, edition=edition
    )
    return merged_res, merged_imm, merged_vuln


def evaluate_condition_roll_mode(
    char_data: Dict[str, Any],
    roll_type: str,
    stat: str = "",
    edition: Optional[str] = None,
) -> Tuple[bool, bool, bool]:
    """
    Evaluate Advantage / Disadvantage / Auto-Fail flags contributed by active conditions
    (2014 & 2024 rules), ready to combine with exhaustion and feature advantages.

    Returns `(has_adv, has_dis, auto_fail)`.
    """
    conds = set(_normalize_conditions(char_data.get("conditions")))
    if not conds:
        return False, False, False

    is_2024 = _is_2024(char_data, edition)
    norm = (roll_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    stat_up = (stat or "").strip().upper()
    stat_low = (stat or "").strip().lower()

    is_init = norm == "initiative" or stat_low == "initiative"
    is_death = norm in {"death", "death_save"} or stat_low == "death"
    is_save = (
        norm in {"save", "saving_throw", "savingthrow", "concentration"}
        or stat_low == "concentration"
    )
    is_attack = norm in {"attack", "attack_roll", "weapon_attack", "spell_attack"}
    is_skill_or_ability = not is_init and not is_save and not is_death and not is_attack

    has_adv = False
    has_dis = False
    auto_fail = False

    if is_attack:
        if "invisible" in conds:
            has_adv = True
        if conds & {"poisoned", "frightened", "blinded", "restrained", "prone"}:
            has_dis = True
    elif is_init:
        if is_2024 and "invisible" in conds:
            has_adv = True
        if (is_2024 and (conds & INCAPACITATING_CONDITIONS)) or (
            conds & {"poisoned", "frightened"}
        ):
            has_dis = True
    elif is_save:
        if stat_up in {"STR", "STRENGTH", "DEX", "DEXTERITY"} and (
            conds & AUTO_FAIL_STR_DEX_CONDITIONS
        ):
            auto_fail = True
        if stat_up in {"DEX", "DEXTERITY"} and "restrained" in conds:
            has_dis = True
    elif is_skill_or_ability:
        if conds & {"poisoned", "frightened"}:
            has_dis = True

    return has_adv, has_dis, auto_fail
