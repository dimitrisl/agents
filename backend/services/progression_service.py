import functools
import logging
import math
from typing import List

logger = logging.getLogger("DnDAssistant.ProgressionService")


@functools.lru_cache(maxsize=128)
def get_modifier(score: int) -> int:
    """Calculates the D&D ability modifier from a score."""
    return math.floor((score - 10) / 2)


def get_hit_die_for_class(char_class: str, edition: str = "2014 Edition") -> str:
    """
    Returns the hit die string (e.g. 'd10') for a given class.
    Exclusively uses the RulesRepository (JSON files) as the source of truth.
    """
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    progression = repo.get_class_progression(char_class, edition)

    if progression and "hit_die" in progression:
        die = str(progression["hit_die"]).lower()
        return f"d{die.split('d')[-1]}"

    logger.warning(
        f"Could not find hit die for {char_class} in {edition} rules. Falling back to d8."
    )
    return "d8"


def get_level_up_vitals(
    char_class: str,
    current_level: int,
    con_score: int,
    edition: str = "2014 Edition",
    features: List[dict] = None,
) -> dict:
    """
    Returns standard level-up vitals (hit die, average HP gain).
    """
    hit_die_str = get_hit_die_for_class(char_class, edition)
    if not hit_die_str.startswith("1"):
        hit_die_str = f"1{hit_die_str}"

    try:
        die_size = int(hit_die_str.lower().split("d")[-1])
    except Exception:
        die_size = 8

    con_mod = get_modifier(con_score)

    hp_bonus_per_level = 0
    if features:
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        feat_library = repo.get_all_feats(edition)
        feat_lookup = {f["name"].lower(): f for f in feat_library} if feat_library else {}
        for f in features:
            if isinstance(f, dict):
                feat_name = f.get("name", "").lower().replace("feat: ", "").strip()
                feat_data = feat_lookup.get(feat_name)
                if not feat_data:
                    for k, v in feat_lookup.items():
                        if k in feat_name or feat_name in k:
                            feat_data = v
                            break
                if feat_data and feat_data.get("hp_bonus_per_level", 0) > 0:
                    hp_bonus_per_level += feat_data["hp_bonus_per_level"]
                else:
                    desc = f.get("description", "").lower()
                    if "dwarven toughness" in desc:
                        hp_bonus_per_level += 1

    avg_gain = (die_size // 2) + 1 + con_mod + hp_bonus_per_level

    return {
        "hit_die": hit_die_str,
        "die_size": die_size,
        "con_mod": con_mod,
        "hp_bonus_per_level": hp_bonus_per_level,
        "average_hp_gain": max(1, avg_gain),
    }


def check_progression_features(
    char_class: str, target_level: int, edition: str = "2014 Edition"
) -> dict:
    """
    Checks for ASI and other features at a specific level.
    """
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    progression = repo.get_class_progression(char_class, edition)

    is_asi_level = False
    level_features = []

    if progression:
        level_data = progression.get("progression", {}).get(str(target_level), {})
        level_features = level_data.get("features", [])
        is_asi_level = any("Ability Score Improvement" in f.get("name", "") for f in level_features)

    return {
        "is_asi_level": is_asi_level,
        "level_features": level_features,
        "has_progression_data": progression is not None,
    }
