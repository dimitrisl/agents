import copy
import logging
import re
from typing import Any, Dict

from backend.repositories.rules_repository import RulesRepository

logger = logging.getLogger("DnDAssistant.ValidationService")

SUBCLASS_MIN_LEVEL = 3

_FEAT_PREFIX_RE = re.compile(r"^(?:origin\s+)?feat:\s*", flags=re.IGNORECASE)
_NON_FEAT_SOURCES = {"race", "species", "class", "subclass", "background"}


def stat_choice_keys_for(choice_key: str) -> tuple[str, str]:
    """Return the companion stat1/stat2 choice keys for an indexed choice key."""
    parts = choice_key.rsplit("_", 1)
    has_idx = len(parts) > 1 and parts[1].isdigit()
    idx_suffix = f"_{parts[1]}" if has_idx else ""
    base = parts[0] if has_idx else choice_key
    return f"{base}_stat1{idx_suffix}", f"{base}_stat2{idx_suffix}"


def normalize_feat_name(raw_name: str | None) -> str:
    """Strip common UI/audit prefixes ('Feat:', 'Origin Feat:') and normalize casing."""
    if not raw_name:
        return ""
    return _FEAT_PREFIX_RE.sub("", str(raw_name).strip()).strip().lower()


def is_feat_repeatable(feat_data: Dict[str, Any] | None, canonical_name: str = "") -> bool:
    """Return True only when a feat may legally be selected multiple times."""
    name_low = normalize_feat_name(canonical_name or (feat_data or {}).get("name"))
    if name_low == "ability score improvement":
        return True
    return bool(feat_data and feat_data.get("repeatable") is True)


def resolve_known_feat(
    raw_name: str | None,
    feat_lookup: Dict[str, Dict[str, Any]],
    source: str | None = None,
) -> tuple[str, Dict[str, Any]] | None:
    """Resolve a trait/advancement name against known feats while ignoring non-feat grants."""
    clean = str(raw_name or "").strip()
    if not clean or not feat_lookup:
        return None

    low = clean.lower()
    has_feat_prefix = bool(_FEAT_PREFIX_RE.match(low))
    src_low = str(source or "").strip().lower()

    # Protect racial/class/background traits (e.g. Halfling 'Lucky', Half-Orc 'Menacing')
    if src_low in _NON_FEAT_SOURCES and not has_feat_prefix:
        return None

    norm = normalize_feat_name(clean)
    if not norm:
        return None

    if norm in feat_lookup:
        fdata = feat_lookup[norm]
        return str(fdata.get("name") or clean), fdata

    is_explicit_feat = has_feat_prefix or src_low in ("feat", "origin feat")
    for k in sorted(feat_lookup.keys(), key=len, reverse=True):
        if not k:
            continue
        if norm.startswith(f"{k} ("):
            fdata = feat_lookup[k]
            return str(fdata.get("name") or clean), fdata
        if is_explicit_feat and re.search(rf"\b{re.escape(k)}\b", norm):
            fdata = feat_lookup[k]
            return str(fdata.get("name") or clean), fdata

    return None


def build_feat_lookup(
    edition: str = "2014 Edition", homebrew_content: list[dict] | None = None
) -> Dict[str, Dict[str, Any]]:
    """Build a lowercase-name feat lookup merged with optional campaign homebrew feats."""
    repo = RulesRepository()
    feats = list(repo.get_all_feats(edition))
    if homebrew_content:
        feats.extend(
            f
            for f in homebrew_content
            if isinstance(f, dict) and f.get("homebrew_type") in ("feat", "feature")
        )
    return {
        str(f.get("name") or "").strip().lower(): f
        for f in feats
        if isinstance(f, dict) and f.get("name")
    }


def _is_racial_homonym_entry(entry: Dict[str, Any], canon_low: str) -> bool:
    """Protect legacy Halfling 'Lucky' and Half-Orc 'Menacing' traits lacking source metadata."""
    src_low = str(entry.get("source") or "").strip().lower()
    name_low = str(entry.get("name") or "").strip().lower()
    if src_low in ("feat", "origin feat") or bool(_FEAT_PREFIX_RE.match(name_low)):
        return False
    desc_low = str(entry.get("description") or "").lower()
    if canon_low == "lucky" and "roll a 1 on the d20" in desc_low:
        return True
    if canon_low == "menacing" and "intimidation skill" in desc_low:
        return True
    return False


def get_owned_non_repeatable_feats(
    char_data: Dict[str, Any],
    edition: str | None = None,
    feat_lookup: Dict[str, Dict[str, Any]] | None = None,
) -> set[str]:
    """Collect canonical lowercase names of non-repeatable feats already owned by the character."""
    if feat_lookup is None:
        ed = edition or char_data.get("dnd_edition", "2014 Edition")
        feat_lookup = build_feat_lookup(ed)

    owned: set[str] = set()
    for entry in char_data.get("features_traits") or []:
        if not isinstance(entry, dict):
            continue
        resolved = resolve_known_feat(entry.get("name"), feat_lookup, source=entry.get("source"))
        if resolved:
            canon_name, feat_data = resolved
            canon_low = canon_name.lower()
            if _is_racial_homonym_entry(entry, canon_low):
                continue
            if not is_feat_repeatable(feat_data, canon_low):
                owned.add(canon_low)

    for adv in char_data.get("advancements") or []:
        if not isinstance(adv, dict):
            continue
        if str(adv.get("type") or "").strip().lower() != "feat":
            continue
        resolved = resolve_known_feat(adv.get("name"), feat_lookup, source="Feat")
        if resolved:
            canon_name, feat_data = resolved
            canon_low = canon_name.lower()
            if not is_feat_repeatable(feat_data, canon_low):
                owned.add(canon_low)

    return owned


def calculate_feature_hp_bonus_per_level(
    features: list[Dict[str, Any]] | None,
    edition: str = "2014 Edition",
    homebrew_content: list[dict] | None = None,
    *,
    is_sorcerer_level: bool = False,
    count_draconic: bool = False,
) -> tuple[int, bool]:
    """Sum per-level HP bonuses from traits and feats without double-counting non-repeatable feats."""
    if not features:
        return 0, False

    feat_lookup = build_feat_lookup(edition, homebrew_content=homebrew_content)
    hp_bonus_per_level = 0
    has_draconic_hp = False
    has_dwarven_toughness = False
    seen_hp_feats: set[str] = set()

    for f in features:
        if not isinstance(f, dict):
            continue
        f_name = str(f.get("name") or "")
        f_desc = str(f.get("description") or "")
        full_text = f"{f_name} {f_desc}".lower()

        if "dwarven toughness" in full_text:
            if not has_dwarven_toughness:
                hp_bonus_per_level += 1
                has_dwarven_toughness = True
            continue
        if "draconic resilience" in full_text:
            if count_draconic and is_sorcerer_level and not has_draconic_hp:
                hp_bonus_per_level += 1
                has_draconic_hp = True
            continue

        resolved = resolve_known_feat(f_name, feat_lookup, source=f.get("source"))
        if not resolved:
            continue
        canon_name, feat_data = resolved
        per_lvl = int((feat_data or {}).get("hp_bonus_per_level") or 0)
        if per_lvl <= 0:
            continue
        canon_low = canon_name.lower()
        if not is_feat_repeatable(feat_data, canon_low):
            if canon_low in seen_hp_feats:
                continue
            seen_hp_feats.add(canon_low)
        hp_bonus_per_level += per_lvl

    return hp_bonus_per_level, has_draconic_hp


def _sum_unique_feat_numeric(
    features: list[Dict[str, Any]] | None,
    field_name: str,
    edition: str = "2014 Edition",
    homebrew_content: list[dict] | None = None,
) -> int:
    """Sum a numeric feat bonus field (e.g. flat_hp_bonus, speed_bonus), deduping non-repeatable feats."""
    if not features:
        return 0
    feat_lookup = build_feat_lookup(edition, homebrew_content=homebrew_content)
    total = 0
    seen_feats: set[str] = set()
    for f in features:
        if not isinstance(f, dict):
            continue
        resolved = resolve_known_feat(f.get("name"), feat_lookup, source=f.get("source"))
        if not resolved:
            continue
        canon_name, feat_data = resolved
        val = int((feat_data or {}).get(field_name) or 0)
        if val <= 0:
            continue
        canon_low = canon_name.lower()
        if not is_feat_repeatable(feat_data, canon_low):
            if canon_low in seen_feats:
                continue
            seen_feats.add(canon_low)
        total += val
    return total


def calculate_feature_flat_hp_bonus(
    features: list[Dict[str, Any]] | None,
    edition: str = "2014 Edition",
    homebrew_content: list[dict] | None = None,
) -> int:
    """Sum flat HP bonuses granted by feats such as Boon of Fortitude (+40 HP)."""
    return _sum_unique_feat_numeric(
        features, "flat_hp_bonus", edition=edition, homebrew_content=homebrew_content
    )


def calculate_feature_speed_bonus(
    features: list[Dict[str, Any]] | None,
    edition: str = "2014 Edition",
    homebrew_content: list[dict] | None = None,
) -> int:
    """Sum Walking Speed bonuses granted by feats such as Boon of Speed (+30 ft)."""
    return _sum_unique_feat_numeric(
        features, "speed_bonus", edition=edition, homebrew_content=homebrew_content
    )


_NON_HEAVY_EQUIP_TYPES = (
    "medium armor",
    "light armor",
    "shield",
    "wondrous item",
    "weapon",
    "ring",
    "potion",
    "scroll",
    "adventuring gear",
)


def _strip_armor_modifiers(raw_name: str) -> str:
    """Normalize '+1/+2/+3' enhancements and punctuation for catalog and keyword matching."""
    cleaned = re.sub(r"(?:\s*,\s*|\s+)\+[1-3]\b", "", str(raw_name or "").lower())
    cleaned = re.sub(r"[(),]", " ", cleaned)
    return " ".join(cleaned.split())


def build_armor_items_lookup(
    homebrew_content: list[dict[str, Any]] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Build a lowercase armor/item catalog lookup merged with optional homebrew definitions."""
    lookup: Dict[str, Dict[str, Any]] = {
        str(i.get("name") or "").strip().lower(): i
        for i in RulesRepository().get_all_items()
        if isinstance(i, dict) and i.get("name")
    }
    for hb in homebrew_content or []:
        if isinstance(hb, dict) and hb.get("name"):
            lookup[str(hb["name"]).strip().lower()] = hb
    return lookup


def get_heavy_armor_strength_penalty(
    char_data: Dict[str, Any],
    items_lookup: Dict[str, Dict[str, Any]] | None = None,
) -> tuple[int, str | None]:
    """Return (speed_penalty_ft, audit_notice) when wearing Heavy Armor below its STR requirement."""
    if not isinstance(char_data, dict):
        return 0, None

    edition = str(char_data.get("dnd_edition") or char_data.get("ruleset_version") or "")
    is_2024 = "2024" in edition
    race = str(char_data.get("race") or "").strip().lower()
    if "dwarf" in race and not is_2024:
        return 0, None

    features = char_data.get("features_traits") or []
    classes = char_data.get("classes") or []
    has_arcane_armor = (
        any(
            isinstance(f, dict)
            and any(
                kw in str(f.get("name") or "").lower() for kw in ("arcane armor", "power armor")
            )
            for f in features
        )
        or "armorer" in str(char_data.get("subclass") or "").lower()
        or any(
            isinstance(c, dict) and "armorer" in str(c.get("subclass") or "").lower()
            for c in classes
        )
    )
    if has_arcane_armor:
        return 0, None

    magic_suppressed = bool(char_data.get("magic_items_suppressed", False))
    equipment = char_data.get("equipment") or []
    # Boots of Striding and Springing are a Wondrous magic item; suppressed under Athas/Antimagic.
    has_striding_boots = (not magic_suppressed) and any(
        isinstance(eq, dict)
        and eq.get("equipped")
        and "boots of striding" in str(eq.get("name") or "").lower()
        for eq in equipment
    )
    if has_striding_boots:
        return 0, None

    if items_lookup is None:
        all_items = RulesRepository().get_all_items()
        items_lookup = {
            str(i.get("name") or "").strip().lower(): i
            for i in all_items
            if isinstance(i, dict) and i.get("name")
        }

    stats = char_data.get("stats") or {}
    if hasattr(stats, "model_dump"):
        stats = stats.model_dump()
    try:
        str_score = int(
            (stats.get("STR") if isinstance(stats, dict) else getattr(stats, "STR", 10)) or 10
        )
    except (TypeError, ValueError):
        str_score = 10

    max_penalty = 0
    trigger_notice: str | None = None
    for equip in equipment:
        if not isinstance(equip, dict) or not equip.get("equipped"):
            continue
        raw_name = str(equip.get("name") or "").strip()
        low = raw_name.lower()
        # Mithral is a non-magical lightweight metal alloy per 5e Sage Advice.
        if not low or "mithral" in low:
            continue

        base_low = _strip_armor_modifiers(low)
        item_db = items_lookup.get(low) or items_lookup.get(base_low)
        equip_type = str(equip.get("type") or "").strip().lower()
        if item_db is not None:
            item_type = str(item_db.get("type") or "").lower()
            if "heavy armor" not in item_type:
                continue
            min_str = int(item_db.get("min_str") or 0)
        elif equip_type and any(t in equip_type for t in _NON_HEAVY_EQUIP_TYPES):
            continue
        elif "heavy armor" in equip_type and equip.get("min_str") is not None:
            try:
                min_str = int(equip.get("min_str") or 0)
            except (TypeError, ValueError):
                min_str = 0
        else:
            min_str = 0
            if "breast" not in base_low and "half" not in base_low:
                if re.search(
                    r"\b(?:full\s+)?plate(?:\s+armor)?\b|\bsplint(?:\s+armor)?\b",
                    base_low,
                ):
                    min_str = 15
                elif re.search(r"\bchain\s*mail\b", base_low):
                    min_str = 13

        if min_str > 0 and str_score < min_str:
            max_penalty = 10
            trigger_notice = (
                f"Wearing {raw_name} with STR {str_score} (requires STR {min_str}) "
                "reduces Walking Speed by 10 ft."
            )
            break

    return max_penalty, trigger_notice


def collect_build_suggestions(
    char_data: Dict[str, Any],
    items_lookup: Dict[str, Dict[str, Any]] | None = None,
) -> list[str]:
    """Collect informational rules notices/recommendations (non-blocking)."""
    suggestions: list[str] = []
    _, armor_str_notice = get_heavy_armor_strength_penalty(char_data, items_lookup=items_lookup)
    if armor_str_notice and armor_str_notice not in suggestions:
        suggestions.append(armor_str_notice)
    return suggestions


_MULTICLASS_ARMOR_PROFS_2014: dict[str, tuple[str, ...]] = {
    "artificer": ("light armor", "medium armor", "shields"),
    "barbarian": ("shields",),
    "bard": ("light armor",),
    "cleric": ("light armor", "medium armor", "shields"),
    "druid": ("light armor", "medium armor", "shields"),
    "fighter": ("light armor", "medium armor", "shields"),
    "monk": (),
    "paladin": ("light armor", "medium armor", "shields"),
    "ranger": ("light armor", "medium armor", "shields"),
    "rogue": ("light armor",),
    "sorcerer": (),
    "warlock": ("light armor",),
    "wizard": (),
}

_MULTICLASS_ARMOR_PROFS_2024: dict[str, tuple[str, ...]] = {
    **_MULTICLASS_ARMOR_PROFS_2014,
    "druid": ("light armor", "shields"),
}

_MULTICLASS_WEAPON_PROFS_2014: dict[str, tuple[str, ...]] = {
    "artificer": (),
    "barbarian": ("simple weapons", "martial weapons"),
    "bard": (),
    "cleric": (),
    "druid": (),
    "fighter": ("simple weapons", "martial weapons"),
    "monk": ("simple weapons", "shortswords"),
    "paladin": ("simple weapons", "martial weapons"),
    "ranger": ("simple weapons", "martial weapons"),
    "rogue": (),
    "sorcerer": (),
    "warlock": ("simple weapons",),
    "wizard": (),
}

_MULTICLASS_WEAPON_PROFS_2024: dict[str, tuple[str, ...]] = {
    **_MULTICLASS_WEAPON_PROFS_2014,
    "monk": (),
    "warlock": (),
}


def get_character_armor_proficiencies(char_data: Dict[str, Any], class_data: Dict[str, Any]) -> set:
    """Extracts all armor proficiencies granted by primary class, multiclass table, subclass, and features."""
    proficiencies = set()
    edition = char_data.get("dnd_edition", "2014 Edition")
    is_2024 = "2024" in str(edition or "")
    repo = RulesRepository()
    mc_armor_table = _MULTICLASS_ARMOR_PROFS_2024 if is_2024 else _MULTICLASS_ARMOR_PROFS_2014

    class_entries = _extract_class_subclass_tuples(char_data)
    if class_entries:
        for idx, (cname, _, _) in enumerate(class_entries):
            c_low = cname.strip().lower()
            if idx == 0:
                cd = (
                    class_data
                    if (
                        isinstance(class_data, dict)
                        and str(class_data.get("class_name") or "").strip().lower() in ("", c_low)
                    )
                    else repo.get_class_progression(cname, edition)
                )
                if cd and "starting_proficiencies" in cd:
                    for p in cd["starting_proficiencies"].get("armor", []):
                        p_lower = p.lower()
                        if p_lower != "none":
                            if p_lower in ["light", "medium", "heavy"]:
                                proficiencies.add(f"{p_lower} armor")
                            else:
                                proficiencies.add(p_lower)
            else:
                proficiencies.update(mc_armor_table.get(c_low, ()))
    elif class_data and "starting_proficiencies" in class_data:
        for p in class_data["starting_proficiencies"].get("armor", []):
            p_lower = p.lower()
            if p_lower != "none":
                if p_lower in ["light", "medium", "heavy"]:
                    proficiencies.add(f"{p_lower} armor")
                else:
                    proficiencies.add(p_lower)

    # 1b. Subclass armor proficiencies (e.g. Life/Tempest/War/Forge Cleric Heavy Armor, Hexblade/Valor Medium+Shields)
    for cname, csub, clvl in class_entries:
        if not csub or csub.lower() in ("none", "n/a"):
            continue
        c_prog = repo.get_class_progression(cname, edition)
        min_lvl = _get_subclass_min_level(c_prog) if c_prog else SUBCLASS_MIN_LEVEL
        if clvl >= (min_lvl if min_lvl is not None else SUBCLASS_MIN_LEVEL):
            sub_entry = repo.get_subclass_entry(cname, csub, edition) or {}
            for p in sub_entry.get("armor_proficiencies") or []:
                p_low = str(p).strip().lower()
                if p_low in ("light", "medium", "heavy"):
                    proficiencies.add(f"{p_low} armor")
                elif p_low:
                    proficiencies.add(p_low)

    # 2. Features and Traits
    # e.g., "Bonus Proficiency: Heavy Armor" or "Training in War and Song" (Light armor)
    for feat in char_data.get("features_traits", []) or []:
        if isinstance(feat, dict):
            f_name = str(feat.get("name") or "").strip().lower()
            f_desc = str(feat.get("description") or "").lower()
        elif isinstance(feat, str):
            f_name = feat.strip().lower()
            f_desc = ""
        else:
            continue
        # Generic multi-option 2024 choice placeholders mention Protector/Warden in prose;
        # only grant armor proficiency in 2024 when the specific order option was actually chosen.
        is_protector_order = (
            "protector" in f_name
            and "thaumaturge" not in f_name
            and ("divine" in f_name or f_name == "protector")
        )
        is_warden_order = (
            "warden" in f_name
            and "magician" not in f_name
            and ("primal" in f_name or f_name == "warden")
        )
        if is_protector_order:
            if is_2024:
                proficiencies.add("heavy armor")
            continue
        if is_warden_order:
            if is_2024:
                proficiencies.add("medium armor")
            continue
        if (
            f_name.startswith(("divine order", "primal order"))
            or ("protector" in f_name and "thaumaturge" in f_name)
            or ("warden" in f_name and "magician" in f_name)
        ):
            continue
        desc = f"{f_desc} {f_name}".strip()
        if "proficien" not in desc and "training" not in desc:
            continue
        if re.search(r"\blight(?:\s*(?:,|and)\s*(?:medium|heavy))*\s+armor\b", desc):
            proficiencies.add("light armor")
        if re.search(r"\bmedium(?:\s*(?:,|and)\s*heavy)*\s+armor\b", desc):
            proficiencies.add("medium armor")
        if "heavy armor" in desc:
            proficiencies.add("heavy armor")
        if "shields" in desc:
            proficiencies.add("shields")

    # "All armor" covers everything
    if "all armor" in proficiencies:
        proficiencies.update(["light armor", "medium armor", "heavy armor", "shields"])

    return proficiencies


def _extract_class_subclass_tuples(char_data: Dict[str, Any]) -> list[tuple[str, str, int]]:
    """Return normalized [(class_name, subclass_name, class_level)] entries."""
    out: list[tuple[str, str, int]] = []
    primary_class = str(char_data.get("char_class") or "").strip()
    primary_sub = str(char_data.get("subclass") or "").strip()
    classes = char_data.get("classes") or []
    for cls in classes:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        cname = str(c_dict.get("class_name") or "").strip()
        if not cname:
            continue
        try:
            clvl = max(1, int(c_dict.get("level") or 1))
        except (TypeError, ValueError):
            clvl = 1
        csub = str(
            c_dict.get("subclass")
            or (primary_sub if cname.lower() == primary_class.lower() else "")
        ).strip()
        out.append((cname, csub, clvl))
    if not out and primary_class:
        try:
            clvl = max(1, int(char_data.get("char_level") or 1))
        except (TypeError, ValueError):
            clvl = 1
        out.append((primary_class, primary_sub, clvl))
    return out


def _normalize_weapon_prof_token(raw: str) -> str:
    clean = str(raw or "").strip().lower()
    if clean in ("simple", "simple weapons"):
        return "simple weapons"
    if clean in ("martial", "martial weapons"):
        return "martial weapons"
    return clean


def get_character_weapon_proficiencies(
    char_data: Dict[str, Any], class_data: Dict[str, Any] | None = None
) -> set[str]:
    """Extract weapon proficiencies from primary class, multiclass table, subclass, race, and features."""
    profs: set[str] = set()
    edition = char_data.get("dnd_edition", "2014 Edition")
    is_2024 = "2024" in str(edition or "")
    mc_weapon_table = _MULTICLASS_WEAPON_PROFS_2024 if is_2024 else _MULTICLASS_WEAPON_PROFS_2014
    repo = RulesRepository()

    class_entries = _extract_class_subclass_tuples(char_data)
    if class_entries:
        for idx, (cname, csub, clvl) in enumerate(class_entries):
            c_low = cname.strip().lower()
            c_prog = (
                class_data
                if (
                    idx == 0
                    and isinstance(class_data, dict)
                    and str(class_data.get("class_name") or "").strip().lower() in ("", c_low)
                )
                else repo.get_class_progression(cname, edition)
            )
            if idx == 0:
                if isinstance(c_prog, dict):
                    for wp in (c_prog.get("starting_proficiencies") or {}).get("weapons") or []:
                        norm = _normalize_weapon_prof_token(wp)
                        if norm and norm != "none":
                            profs.add(norm)
            else:
                profs.update(mc_weapon_table.get(c_low, ()))

            if csub and csub.lower() not in ("none", "n/a"):
                sub_prog = repo.get_class_progression(cname, edition) or c_prog
                min_lvl = _get_subclass_min_level(sub_prog) if sub_prog else SUBCLASS_MIN_LEVEL
                if clvl >= (min_lvl if min_lvl is not None else SUBCLASS_MIN_LEVEL):
                    sub_entry = repo.get_subclass_entry(cname, csub, edition) or {}
                    for wp in sub_entry.get("weapon_proficiencies") or []:
                        norm = _normalize_weapon_prof_token(wp)
                        if norm:
                            profs.add(norm)
    elif isinstance(class_data, dict):
        for wp in (class_data.get("starting_proficiencies") or {}).get("weapons") or []:
            norm = _normalize_weapon_prof_token(wp)
            if norm and norm != "none":
                profs.add(norm)

    race_name = str(char_data.get("race") or "").strip()
    if race_name:
        race_data = repo.get_race_data(race_name, edition) or {}
        for wp in race_data.get("weapon_proficiencies") or []:
            norm = _normalize_weapon_prof_token(wp)
            if norm:
                profs.add(norm)

    known_weapon_tokens = (
        "simple weapons",
        "martial weapons",
        "hand crossbows",
        "heavy crossbows",
        "light crossbows",
        "longswords",
        "shortswords",
        "rapiers",
        "scimitars",
        "shortbows",
        "longbows",
        "daggers",
        "darts",
        "slings",
        "quarterstaffs",
        "battleaxes",
        "handaxes",
        "light hammers",
        "warhammers",
        "clubs",
        "javelins",
        "maces",
        "sickles",
        "spears",
        "firearms",
    )
    for feat in char_data.get("features_traits", []) or []:
        if isinstance(feat, dict):
            f_name = str(feat.get("name") or "").strip().lower()
            f_desc = str(feat.get("description") or "").lower()
        elif isinstance(feat, str):
            f_name = feat.strip().lower()
            f_desc = ""
        else:
            continue
        is_protector_order = (
            "protector" in f_name
            and "thaumaturge" not in f_name
            and ("divine" in f_name or f_name == "protector")
        )
        is_warden_order = (
            "warden" in f_name
            and "magician" not in f_name
            and ("primal" in f_name or f_name == "warden")
        )
        if is_protector_order or is_warden_order:
            if is_2024:
                profs.add("martial weapons")
            continue
        if (
            f_name.startswith(("divine order", "primal order"))
            or ("protector" in f_name and "thaumaturge" in f_name)
            or ("warden" in f_name and "magician" in f_name)
        ):
            continue
        combined = f"{f_name} {f_desc}"
        if "gunner" in f_name:
            profs.add("firearms")
        if "tavern brawler" in f_name:
            profs.add("improvised weapons")
        if "proficien" in combined or "training" in combined or "hex warrior" in f_name:
            for tok in known_weapon_tokens:
                if tok in combined or tok.rstrip("s") in combined:
                    profs.add(tok)

    return profs


def is_weapon_proficient(
    weapon: Dict[str, Any],
    weapon_proficiencies: set[str] | list[str] | None,
    weapon_data: Dict[str, Any] | None = None,
    is_monk: bool = False,
) -> bool:
    """Return True if the character is proficient with the equipped weapon."""
    if weapon.get("is_custom"):
        return bool(weapon.get("proficient", True))
    if not weapon_proficiencies:
        return bool(weapon.get("proficient", True))

    w_name = str(weapon.get("name") or "").strip().lower()
    if not w_name or "unarmed" in w_name or "spell" in w_name or "eldritch blast" in w_name:
        return bool(weapon.get("proficient", True))

    prof_set = {_normalize_weapon_prof_token(p) for p in weapon_proficiencies if str(p).strip()}
    clean_base = re.sub(r"\s*\+\d+\s*", " ", w_name).strip()

    if is_monk and (
        "shortsword" in clean_base
        or (
            weapon_data
            and "simple" in str(weapon_data.get("category") or "").lower()
            and "melee" in str(weapon_data.get("category") or "").lower()
        )
    ):
        return True

    simple_known = (
        "club",
        "dagger",
        "greatclub",
        "handaxe",
        "javelin",
        "light hammer",
        "mace",
        "quarterstaff",
        "sickle",
        "spear",
        "light crossbow",
        "dart",
        "shortbow",
        "sling",
    )
    martial_known = (
        "battleaxe",
        "flail",
        "glaive",
        "greataxe",
        "greatsword",
        "halberd",
        "lance",
        "longsword",
        "maul",
        "morningstar",
        "pike",
        "rapier",
        "scimitar",
        "shortsword",
        "trident",
        "war pick",
        "warhammer",
        "whip",
        "blowgun",
        "hand crossbow",
        "heavy crossbow",
        "longbow",
        "net",
    )

    w_props = (
        [str(p).lower() for p in (weapon_data.get("properties") or [])]
        if weapon_data
        else [
            p.strip().lower()
            for p in (
                weapon.get("properties")
                if isinstance(weapon.get("properties"), list)
                else str(weapon.get("properties") or "").split(",")
            )
            if str(p).strip()
        ]
    )
    finesse_martial_names = ("rapier", "scimitar", "shortsword", "whip")
    light_martial_names = ("scimitar", "shortsword", "hand crossbow")
    is_finesse_prop = any("finesse" in p for p in w_props) or any(
        re.search(rf"\b{re.escape(k)}\b", clean_base) for k in finesse_martial_names
    )
    is_light_prop = any("light" in p for p in w_props) or any(
        re.search(rf"\b{re.escape(k)}\b", clean_base) for k in light_martial_names
    )
    is_ranged_light = "hand crossbow" in clean_base or (
        weapon_data and "ranged" in str(weapon_data.get("category") or "").lower()
    )
    has_finesse_martial_prof = any("martial" in tok and "finesse" in tok for tok in prof_set)
    has_light_martial_prof = any(
        "martial" in tok and "light" in tok and ("finesse" in tok or not is_ranged_light)
        for tok in prof_set
    )

    if weapon_data:
        cat = str(weapon_data.get("category") or "").lower()
        if "simple" in cat and "simple weapons" in prof_set:
            return True
        if "martial" in cat:
            if "martial weapons" in prof_set:
                return True
            if has_finesse_martial_prof and is_finesse_prop:
                return True
            if has_light_martial_prof and is_light_prop:
                return True
    else:
        if (
            any(re.search(rf"\b{re.escape(k)}\b", clean_base) for k in simple_known)
            and "simple weapons" in prof_set
        ):
            return True
        if any(re.search(rf"\b{re.escape(k)}\b", clean_base) for k in martial_known):
            if "martial weapons" in prof_set:
                return True
            if has_finesse_martial_prof and is_finesse_prop:
                return True
            if has_light_martial_prof and is_light_prop:
                return True

    # Direct single-weapon or plural proficiency token match (e.g. "longsword" vs "longswords")
    for tok in prof_set:
        tok_sing = tok[:-1] if tok.endswith("s") else tok
        if (
            tok == clean_base
            or tok_sing == clean_base
            or (len(tok_sing) >= 4 and re.search(rf"\b{re.escape(tok_sing)}\b", clean_base))
        ):
            return True

    # Only fall back to explicit/default weapon flag for custom/unknown weapon names
    if weapon_data is None and not any(
        re.search(rf"\b{re.escape(k)}\b", clean_base) for k in simple_known + martial_known
    ):
        return bool(weapon.get("proficient", True))

    return False


def get_max_attunement_slots(char_data: Dict[str, Any]) -> int:
    """Determines maximum attunement slots for a character according to 5e rules.
    Base limit is 3. Artificers expand this via Magic Item Adept/Savant/Master:
      - Level 10+: 4 slots
      - Level 14+: 5 slots
      - Level 18+: 6 slots
    """
    if not char_data or not isinstance(char_data, dict):
        return 3

    artificer_level = 0
    classes = char_data.get("classes", []) or []
    for cls in classes:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        if (c_dict.get("class_name") or "").lower() == "artificer":
            try:
                lvl = int(c_dict.get("level", 0) or 0)
                artificer_level = max(artificer_level, lvl)
            except (ValueError, TypeError):
                pass

    if artificer_level == 0 and (char_data.get("char_class") or "").lower() == "artificer":
        try:
            artificer_level = int(char_data.get("char_level", 1) or 1)
        except (ValueError, TypeError):
            artificer_level = 1

    for f in char_data.get("features_traits", []) or []:
        fname = (f.get("name") if isinstance(f, dict) else str(f)).lower()
        if "magic item master" in fname:
            artificer_level = max(artificer_level, 18)
        elif "magic item savant" in fname:
            artificer_level = max(artificer_level, 14)
        elif "magic item adept" in fname:
            artificer_level = max(artificer_level, 10)

    if artificer_level >= 18:
        return 6
    if artificer_level >= 14:
        return 5
    if artificer_level >= 10:
        return 4
    return 3


def deterministic_validate_build(char_data: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """
    Applies deterministic rules validation to the character.
    Returns the corrected character data and a list of identified issues.
    """
    corrected_char = copy.deepcopy(char_data)
    repo = RulesRepository()
    issues = []

    char_class = corrected_char.get("char_class", "")
    edition = corrected_char.get("dnd_edition", "2014 Edition")

    class_data = repo.get_class_progression(char_class, edition)

    # 1. Ability Score Caps
    # We removed the hard cap of 20 because magic items (like Belt of Giant Strength)
    # or homebrew rules allow stats > 20, and the validation service does not differentiate
    # between base stats and final item-boosted stats.
    # The stat calculation engine will handle bounds naturally.
    # 1b. Multiclass Prerequisites
    stats = corrected_char.get("base_stats") or corrected_char.get("stats", {})
    if hasattr(stats, "model_dump"):
        stats = stats.model_dump()
    elif not isinstance(stats, dict):
        stats = {
            "STR": getattr(stats, "STR", 10),
            "DEX": getattr(stats, "DEX", 10),
            "CON": getattr(stats, "CON", 10),
            "INT": getattr(stats, "INT", 10),
            "WIS": getattr(stats, "WIS", 10),
            "CHA": getattr(stats, "CHA", 10),
        }

    classes = corrected_char.get("classes", [])
    if len(classes) > 1:
        prereqs = {
            "barbarian": lambda s: s.get("STR", 0) >= 13,
            "bard": lambda s: s.get("CHA", 0) >= 13,
            "cleric": lambda s: s.get("WIS", 0) >= 13,
            "druid": lambda s: s.get("WIS", 0) >= 13,
            "fighter": lambda s: s.get("STR", 0) >= 13 or s.get("DEX", 0) >= 13,
            "monk": lambda s: s.get("DEX", 0) >= 13 and s.get("WIS", 0) >= 13,
            "paladin": lambda s: s.get("STR", 0) >= 13 and s.get("CHA", 0) >= 13,
            "ranger": lambda s: s.get("DEX", 0) >= 13 and s.get("WIS", 0) >= 13,
            "rogue": lambda s: s.get("DEX", 0) >= 13,
            "sorcerer": lambda s: s.get("CHA", 0) >= 13,
            "warlock": lambda s: s.get("CHA", 0) >= 13,
            "wizard": lambda s: s.get("INT", 0) >= 13,
            "artificer": lambda s: s.get("INT", 0) >= 13,
        }
        for cls in classes:
            cname = cls.get("class_name", "").lower()
            if cname in prereqs and not prereqs[cname](stats):
                issue_msg = f"Character does not meet the multiclassing stat prerequisites for {cname.capitalize()}."
                logger.warning(issue_msg)
                issues.append(issue_msg)

    # 2. Armor Proficiency Validation
    # Check if the character has equipped armor they are not proficient in and issue a warning
    armor_profs = get_character_armor_proficiencies(corrected_char, class_data)
    all_items = repo.get_all_items()
    items_lookup = {i.get("name", "").lower(): i for i in all_items}

    equipment = corrected_char.get("equipment", [])
    attuned_items_count = 0
    for equip in equipment:
        if isinstance(equip, dict) and equip.get("attuned", False):
            attuned_items_count += 1
        if isinstance(equip, dict) and equip.get("equipped", False):
            item_name = equip.get("name", "").lower()
            item_db = items_lookup.get(item_name)
            if item_db:
                item_type = item_db.get("type", "").lower()

                # Check if it's armor
                req_prof = None
                if "light armor" in item_type:
                    req_prof = "light armor"
                elif "medium armor" in item_type:
                    req_prof = "medium armor"
                elif "heavy armor" in item_type:
                    req_prof = "heavy armor"
                elif "shield" in item_type:
                    req_prof = "shields"

                if req_prof:
                    if req_prof not in armor_profs and "all armor" not in armor_profs:
                        issue_msg = f"Character lacks proficiency for {item_name} ({req_prof}). Wearing it imposes disadvantage on STR/DEX checks, saves, and attacks, and prevents spellcasting."
                        logger.warning(issue_msg)
                        issues.append(issue_msg)

    max_attuned = get_max_attunement_slots(corrected_char)
    if attuned_items_count > max_attuned:
        issue_msg = f"Character is attuned to {attuned_items_count} magic items, exceeding the maximum attunement limit of {max_attuned}."
        logger.warning(issue_msg)
        issues.append(issue_msg)

    # 3. Weapon Proficiency Validation (Basic)
    # Weapons can be used without proficiency, but it shouldn't have proficiency bonus applied.
    # Our sync_character_stats adds proficiency bonus automatically, so we'll just flag it for now
    # or remove custom non-proficient items if AI hallucinated them.
    # We will leave weapons equipped, as using weapons without proficiency is legal (unlike spellcasting in unproficient armor).

    # 4. Subclass Level Validation
    # Clear the subclass if the character has not yet reached the level where the class
    # grants a subclass choice. The threshold is read from the static JSON progression,
    # so no domain data is ever hardcoded here.
    subclass = corrected_char.get("subclass")
    level = corrected_char.get("char_level", 1)
    classes_list = corrected_char.get("classes", [])

    # In multiclass characters, verify the specific class level rather than total character level
    char_class_level = level
    for cls in classes_list:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        if c_dict.get("class_name", "").lower() == char_class.lower():
            char_class_level = c_dict.get("level", level)
            break

    if subclass and class_data:
        subclass_min_level = _get_subclass_min_level(class_data)
        if subclass_min_level is None:
            # Fallback for parsing errors or older JSON
            subclass_min_level = SUBCLASS_MIN_LEVEL

        if char_class_level < subclass_min_level:
            issue_msg = f"Character is level {char_class_level} in '{char_class}' but subclass '{subclass}' requires level {subclass_min_level}. Clearing subclass."
            logger.warning(issue_msg)
            issues.append(issue_msg)
            corrected_char["subclass"] = None

    # Check any other classes in the multiclass list
    for cls in classes_list:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        c_sub = c_dict.get("subclass")
        c_name = c_dict.get("class_name", "")
        c_lvl = c_dict.get("level", 1)
        if c_sub and c_name:
            c_data = (
                class_data
                if c_name.lower() == char_class.lower()
                else repo.get_class_progression(c_name, edition)
            )
            if c_data:
                c_min = _get_subclass_min_level(c_data)
                if c_min is None:
                    c_min = SUBCLASS_MIN_LEVEL
                if c_lvl < c_min:
                    issue_msg = f"Character has {c_lvl} level(s) in '{c_name}' but subclass '{c_sub}' requires level {c_min}. Clearing subclass."
                    logger.warning(issue_msg)
                    if issue_msg not in issues:
                        issues.append(issue_msg)
                    if isinstance(cls, dict):
                        cls["subclass"] = None
                    elif hasattr(cls, "subclass"):
                        cls.subclass = None
                    if c_name.lower() == char_class.lower():
                        corrected_char["subclass"] = None

    # 5. Duplicate Non-Repeatable Feat Validation
    feat_lookup = build_feat_lookup(edition)
    raw_features = list(corrected_char.get("features_traits") or [])
    feat_occurrences: Dict[str, list[tuple[int, int, str]]] = {}
    for idx, entry in enumerate(raw_features):
        if not isinstance(entry, dict):
            continue
        resolved = resolve_known_feat(entry.get("name"), feat_lookup, source=entry.get("source"))
        if not resolved:
            continue
        canon_name, feat_data = resolved
        canon_low = canon_name.lower()
        if _is_racial_homonym_entry(entry, canon_low) or is_feat_repeatable(feat_data, canon_low):
            continue
        src_low = str(entry.get("source") or "").strip().lower()
        name_low = str(entry.get("name") or "").strip().lower()
        priority = (
            1
            if (src_low in ("feat", "origin feat") or bool(_FEAT_PREFIX_RE.match(name_low)))
            else 0
        )
        feat_occurrences.setdefault(canon_low, []).append((priority, idx, canon_name))

    duplicate_indices: set[int] = set()
    flagged_dupes: set[str] = set()
    for canon_low, occs in feat_occurrences.items():
        if len(occs) > 1:
            # Keep the highest-priority (earliest) entry, drop the duplicates
            keep_priority, keep_idx, display_name = max(occs, key=lambda item: (item[0], -item[1]))
            for _, idx, _ in occs:
                if idx != keep_idx:
                    duplicate_indices.add(idx)
            flagged_dupes.add(canon_low)
            issue_msg = f"Duplicate non-repeatable feat '{display_name}' is not allowed. Removing duplicate entry."
            logger.warning(issue_msg)
            if issue_msg not in issues:
                issues.append(issue_msg)

    if duplicate_indices:
        corrected_char["features_traits"] = [
            f for idx, f in enumerate(raw_features) if idx not in duplicate_indices
        ]

    raw_advs = list(corrected_char.get("advancements") or [])
    seen_adv_feats: set[str] = set()
    cleaned_advs = []
    for adv in raw_advs:
        if isinstance(adv, dict) and str(adv.get("type") or "").strip().lower() == "feat":
            resolved = resolve_known_feat(adv.get("name"), feat_lookup, source="Feat")
            if resolved:
                canon_name, feat_data = resolved
                canon_low = canon_name.lower()
                if not is_feat_repeatable(feat_data, canon_low):
                    if canon_low in seen_adv_feats:
                        if canon_low not in flagged_dupes:
                            flagged_dupes.add(canon_low)
                            issue_msg = f"Duplicate non-repeatable feat '{canon_name}' is not allowed. Removing duplicate entry."
                            logger.warning(issue_msg)
                            if issue_msg not in issues:
                                issues.append(issue_msg)
                        continue
                    seen_adv_feats.add(canon_low)
        cleaned_advs.append(adv)
    if len(cleaned_advs) != len(raw_advs):
        corrected_char["advancements"] = cleaned_advs

    return corrected_char, issues


# Keywords that identify the "choose your subclass" feature in progression JSON.
_SUBCLASS_KEYWORDS = (
    "archetype",
    "subclass",
    "domain",
    "circle",
    "sacred oath",
    "patron",
    "monastic tradition",
    "primal path",
    "college",
    "roguish archetype",
    "ranger archetype",
    "arcane tradition",
    "sorcerous origin",
    "otherworldly patron",
    "artificer specialist",
)


def _get_subclass_min_level(class_data: Dict[str, Any]) -> int | None:
    """Returns the earliest level at which the class grants a subclass choice.

    Reads the static JSON progression and looks for feature names matching
    known subclass-granting keywords. Returns None if no such entry is found,
    which is treated as 'no restriction' by the caller.
    """
    progression = class_data.get("progression", {})
    for level_str, level_data in sorted(progression.items(), key=lambda x: int(x[0])):
        for feature in level_data.get("features", []):
            name = feature.get("name", "").lower()
            if any(kw in name for kw in _SUBCLASS_KEYWORDS):
                return int(level_str)
    return None
