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
    subclass: str = None,
) -> dict:
    """
    Returns deterministic level-up vitals (hit die, average HP gain, max legal HP gain).
    """
    hit_die_str = get_hit_die_for_class(char_class, edition)
    if not hit_die_str.startswith("1"):
        hit_die_str = f"1{hit_die_str}"

    try:
        die_size = int(hit_die_str.lower().split("d")[-1])
    except Exception:
        die_size = 8

    con_mod = get_modifier(con_score)

    is_sorcerer_level = (char_class or "").strip().lower() == "sorcerer"
    from backend.services.validation_service import calculate_feature_hp_bonus_per_level

    hp_bonus_per_level, has_draconic_hp = calculate_feature_hp_bonus_per_level(
        features,
        edition=edition,
        is_sorcerer_level=is_sorcerer_level,
        count_draconic=True,
    )

    if (
        not has_draconic_hp
        and (char_class or "").strip().lower() == "sorcerer"
        and "draconic" in (subclass or "").lower()
    ):
        hp_bonus_per_level += 1

    avg_gain = (die_size // 2) + 1 + con_mod + hp_bonus_per_level
    max_gain = die_size + con_mod + hp_bonus_per_level

    return {
        "hit_die": hit_die_str,
        "die_size": die_size,
        "con_mod": con_mod,
        "hp_bonus_per_level": hp_bonus_per_level,
        "average_hp_gain": max(1, avg_gain),
        "max_hp_gain": max(1, max_gain),
    }


def is_asi_or_epic_boon_feature(name: str) -> bool:
    lower = (name or "").lower()
    return "ability score improvement" in lower or "epic boon" in lower


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
        is_asi_level = any(is_asi_or_epic_boon_feature(f.get("name", "")) for f in level_features)

    return {
        "is_asi_level": is_asi_level,
        "level_features": level_features,
        "has_progression_data": progression is not None,
    }
