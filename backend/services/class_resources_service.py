"""Limited-use class pools (Sorcery Points, Ki/Focus, Rage, Channel Divinity, ...).

The pools are data, not code: ``data/rules/class_resources.json`` says which
class gets what, from which level, how big the pool is and when it recharges.
``sync_class_resources`` turns that into the character's ``class_resources`` on
every save, so the numbers follow level-ups and multiclassing on their own.

Pools the player added by hand are never touched. A hand-made pool whose name
matches a rules pool (e.g. "Sorcery Points" typed in before this existed) is
adopted instead of duplicated.
"""

import functools
import json
import logging
import math
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DnDAssistant.ClassResources")

RESOURCES_FILE = os.path.join("data", "rules", "class_resources.json")


@functools.lru_cache(maxsize=1)
def _load_rules() -> Dict[str, Any]:
    try:
        with open(RESOURCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        logger.error(f"Could not load class resources from {RESOURCES_FILE}: {e}")
        return {}


def _edition_key(edition: Optional[str]) -> str:
    return "2024" if "2024" in str(edition or "") else "2014"


def _norm(name: Any) -> str:
    return " ".join(str(name or "").lower().split())


def _modifier(score: Any) -> int:
    try:
        return math.floor((int(score) - 10) / 2)
    except (TypeError, ValueError):
        return 0


def _pool_max(rule: Dict[str, Any], class_level: int, stats: Dict[str, Any]) -> int:
    """0 means the class doesn't have this pool yet at that level."""
    spec = rule.get("max", {})
    if "per_level" in spec:
        if class_level < spec.get("from", 1):
            return 0
        return int(spec["per_level"]) * class_level
    if "steps" in spec:
        reached = [uses for lvl, uses in spec["steps"] if class_level >= lvl]
        return int(reached[-1]) if reached else 0
    if "ability" in spec:
        if class_level < spec.get("from", 1):
            return 0
        value = _modifier(stats.get(spec["ability"], 10)) + int(spec.get("plus", 0))
        return max(int(spec.get("min", 0)), value)
    return 0


def rules_pools(
    classes: List[Dict[str, Any]],
    stats: Dict[str, Any],
    edition: Optional[str],
    race: Optional[str] = None,
    total_level: Optional[int] = None,
    subclass: Optional[str] = None,
    features_traits: Optional[List[Any]] = None,
    char_class: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Every pool the character's classes and race/species grant right now."""
    edition_key = _edition_key(edition)
    by_class = _load_rules().get(edition_key, {})
    pools: Dict[str, Dict[str, Any]] = {}
    has_natural_recovery_feature = any(
        "natural recovery" in _norm(f.get("name") if isinstance(f, dict) else f)
        for f in (features_traits or [])
    )
    primary_low = _norm(char_class)

    for idx, entry in enumerate(classes):
        class_name = _norm(entry.get("class_name"))
        class_level = int(entry.get("level") or 1)
        use_top_sub = (
            idx == 0 or len(classes) == 1 or (bool(primary_low) and class_name == primary_low)
        )
        entry_sub = _norm(entry.get("subclass") or (subclass if use_top_sub else None))
        for rule in by_class.get(class_name, []):
            maximum = _pool_max(rule, class_level, stats)
            if maximum <= 0:
                continue
            short_from = rule.get("recharge_short_from")
            recharge = (
                "short"
                if short_from and class_level >= short_from
                else rule.get("recharge", "long")
            )
            pool = {
                "name": rule["name"],
                "max": maximum,
                "recharge": recharge,
                "auto": True,
                "_aliases": {_norm(rule["name"]), *(_norm(a) for a in rule.get("aliases", []))},
            }
            existing = pools.get(rule["id"])
            # Multiclass overlap (Cleric + Paladin Channel Divinity): keep the larger pool.
            if not existing or existing["max"] < maximum:
                pools[rule["id"]] = pool

        if class_name == "druid" and (
            ("land" in entry_sub and class_level >= (6 if edition_key == "2024" else 2))
            or (has_natural_recovery_feature and class_level >= 2)
        ):
            pools["natural_recovery"] = {
                "name": "Natural Recovery",
                "max": 1,
                "recharge": "long",
                "auto": True,
                "_aliases": {"natural recovery"},
            }

    race_low = _norm(race)
    if race_low:
        lvl = max(1, int(total_level or sum(int(c.get("level") or 1) for c in classes) or 1))
        pb = math.ceil(lvl / 4) + 1
        if "dragonborn" in race_low:
            pools["breath_weapon"] = {
                "name": "Breath Weapon",
                "max": pb if edition_key == "2024" else 1,
                "recharge": "long" if edition_key == "2024" else "short",
                "auto": True,
                "_aliases": {"breath weapon"},
            }
        if "half-orc" in race_low or race_low == "orc":
            pools["relentless_endurance"] = {
                "name": "Relentless Endurance",
                "max": 1,
                "recharge": "long",
                "auto": True,
                "_aliases": {"relentless endurance"},
            }

    return list(pools.values())


def sync_class_resources(
    current: List[Dict[str, Any]],
    classes: List[Dict[str, Any]],
    stats: Dict[str, Any],
    edition: Optional[str],
    race: Optional[str] = None,
    total_level: Optional[int] = None,
    subclass: Optional[str] = None,
    features_traits: Optional[List[Any]] = None,
    char_class: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Merges the rules pools into the character's existing ``class_resources``.

    - A pool that was full stays full when its max grows (level up); otherwise
      what was spent stays spent, capped at the new max.
    - A hand-made pool with a bigger max than the rules (item, feat, house rule)
      keeps the difference as ``bonus``, so it still grows with level: rules + bonus.
    - A new pool starts full.
    - Rules pools the character no longer qualifies for are dropped; pools the
      player made by hand are kept exactly as they are.
    """
    existing = [dict(r) for r in (current or []) if isinstance(r, dict)]
    result: List[Dict[str, Any]] = []
    used = set()

    for pool in rules_pools(
        classes,
        stats,
        edition,
        race=race,
        total_level=total_level,
        subclass=subclass,
        features_traits=features_traits,
        char_class=char_class,
    ):
        match = next(
            (
                i
                for i, r in enumerate(existing)
                if i not in used and (_norm(r.get("name")) in pool["_aliases"])
            ),
            None,
        )
        pool.pop("_aliases")
        if match is None:
            result.append({**pool, "current": pool["max"]})
            continue

        used.add(match)
        old = existing[match]
        try:
            old_max = int(old.get("max") or 0)
            old_current = int(old.get("current") if old.get("current") is not None else old_max)
            old_bonus = int(old.get("bonus") or 0)
        except (TypeError, ValueError):
            old_max, old_current, old_bonus = 0, pool["max"], 0

        rules_max = pool["max"]
        bonus = old_bonus if old.get("auto") else max(0, old_max - rules_max)
        # The bonus can be negative (a player correcting the rules down), never below one use (the schema floor).
        new_max = max(1, rules_max + bonus)
        was_full = old_current >= old_max
        current_value = new_max if was_full else min(old_current, new_max)
        result.append({**pool, "max": new_max, "bonus": bonus, "current": max(0, current_value)})

    for i, r in enumerate(existing):
        if i in used or r.get("auto"):
            continue  # adopted above, or a rules pool that no longer applies
        result.append(r)
    return result
