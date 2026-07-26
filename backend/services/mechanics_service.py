"""
Mechanics Service Facade
Re-exports domain functions from dice_service, stats_service, and progression_service
for backward compatibility across the codebase.
"""

from backend.services.dice_service import (
    rebuild_damage_formula,
    roll_dice,
)

from backend.services.stats_service import (
    get_modifier,
    calculate_proficiency_bonus,
    calculate_hp,
    calculate_ac,
    calculate_passive_perception,
    calculate_skills,
    calculate_saving_throws,
    calculate_spell_stats,
    calculate_max_spell_slots,
    calculate_weapon_stats,
    sync_character_stats,
)

from backend.services.progression_service import (
    get_hit_die_for_class,
    get_level_up_vitals,
    check_progression_features,
)

__all__ = [
    "get_modifier",
    "get_hit_die_for_class",
    "calculate_proficiency_bonus",
    "calculate_hp",
    "get_level_up_vitals",
    "calculate_ac",
    "calculate_passive_perception",
    "calculate_skills",
    "calculate_saving_throws",
    "calculate_spell_stats",
    "rebuild_damage_formula",
    "calculate_weapon_stats",
    "calculate_max_spell_slots",
    "sync_character_stats",
    "check_progression_features",
    "roll_dice",
]
