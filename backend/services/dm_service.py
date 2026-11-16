import logging

from backend.core.ai_client import generate_ai_json, generate_ai_response
from backend.core.constants import EDITION_2014
from backend.core.prompts import (
    NPC_PROMPT,
    RANDOM_ENCOUNTER_PROMPT,
    RIDDLE_PROMPT,
    SESSION_PREP_PROMPT,
)
from backend.core.schemas import EncounterSchema
from backend.repositories.rules_repository import RulesRepository

logger = logging.getLogger("DnDAssistant.DMService")

# DMG 5e XP thresholds per character level: (Easy, Medium, Hard, Deadly)
_XP_THRESHOLDS: dict[int, tuple[int, int, int, int]] = {
    1: (25, 50, 75, 100),
    2: (50, 100, 150, 200),
    3: (75, 150, 225, 400),
    4: (125, 250, 375, 500),
    5: (250, 500, 750, 1100),
    6: (300, 600, 900, 1400),
    7: (350, 750, 1100, 1700),
    8: (450, 900, 1400, 2100),
    9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800),
    11: (800, 1600, 2400, 3600),
    12: (1000, 2000, 3000, 4500),
    13: (1100, 2200, 3400, 5100),
    14: (1250, 2500, 3800, 5700),
    15: (1400, 2800, 4300, 6400),
    16: (1600, 3200, 4800, 7200),
    17: (2000, 3900, 5900, 8800),
    18: (2100, 4200, 6300, 9500),
    19: (2400, 4900, 7300, 10900),
    20: (2800, 5700, 8500, 12700),
}
_DIFFICULTY_INDEX = {
    "easy": 0,
    "low": 0,
    "medium": 1,
    "moderate": 1,
    "hard": 2,
    "high": 2,
    "deadly": 3,
}

# Canonical 5e SRD Challenge Rating -> XP mapping
_CR_TO_XP: dict[str, int] = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "30": 155000,
}


def _monster_xp(monster: dict) -> int:
    """Resolve XP deterministically from explicit 'xp', string 'cr', or numeric 'cr_numeric'."""
    raw_xp = monster.get("xp")
    if isinstance(raw_xp, (int, float)) and raw_xp > 0:
        return int(raw_xp)

    cr_str = str(monster.get("cr") or "").strip()
    if cr_str in _CR_TO_XP:
        return _CR_TO_XP[cr_str]

    cr_num = monster.get("cr_numeric")
    if isinstance(cr_num, (int, float)):
        if cr_num <= 0:
            return _CR_TO_XP["0"]
        if abs(cr_num - 0.125) < 0.01:
            return _CR_TO_XP["1/8"]
        if abs(cr_num - 0.25) < 0.01:
            return _CR_TO_XP["1/4"]
        if abs(cr_num - 0.5) < 0.01:
            return _CR_TO_XP["1/2"]
        rounded = str(int(round(cr_num)))
        if rounded in _CR_TO_XP:
            return _CR_TO_XP[rounded]

    return _CR_TO_XP["1/4"]


def _monster_dex(monster: dict) -> int:
    stats = monster.get("stats") or {}
    val = stats.get("dex") or stats.get("DEX") or monster.get("dex") or 10
    try:
        return int(val)
    except (TypeError, ValueError):
        return 10


def _hydrate_encounter_from_bestiary(encounter: dict, edition: str) -> dict:
    """Replace AI-guessed HP/AC/DEX with canonical SRD monster numbers when a match exists."""
    repo = RulesRepository()
    monsters = repo.get_all_monsters(edition)
    lookup = {str(m.get("name", "")).strip().lower(): m for m in monsters if m.get("name")}
    for entry in encounter.get("monsters") or []:
        if not isinstance(entry, dict):
            continue
        m_name = str(entry.get("name") or "").strip().lower()
        srd = lookup.get(m_name)
        if srd:
            if isinstance(srd.get("hp"), int) and srd["hp"] > 0:
                entry["hp"] = srd["hp"]
            if isinstance(srd.get("ac"), int) and srd["ac"] > 0:
                entry["ac"] = srd["ac"]
            entry["dex"] = _monster_dex(srd)
    return encounter


def _build_deterministic_encounter(
    party_size: int,
    avg_level: int,
    location: str,
    edition: str,
    difficulty: str,
) -> dict | None:
    """Build a balanced encounter directly from the static SRD monster dataset without AI."""
    repo = RulesRepository()
    all_monsters = repo.get_all_monsters(edition)
    if not all_monsters:
        return None

    lvl = max(1, min(20, int(avg_level or 1)))
    p_size = max(1, int(party_size or 4))
    diff_idx = _DIFFICULTY_INDEX.get((difficulty or "medium").strip().lower(), 1)
    budget = _XP_THRESHOLDS[lvl][diff_idx] * p_size

    candidates = [
        m for m in all_monsters if 0 < _monster_xp(m) <= budget and (m.get("hp") or 0) > 0
    ]
    if not candidates:
        valid_monsters = [m for m in all_monsters if (m.get("hp") or 0) > 0]
        if valid_monsters:
            lowest_xp = min(_monster_xp(m) for m in valid_monsters)
            candidates = [m for m in valid_monsters if _monster_xp(m) == lowest_xp]
    if not candidates:
        return None

    # Deterministic selection scored by proximity to 1/2 - 1/3 of encounter XP budget
    target_unit_xp = max(10, budget // 3)
    candidates.sort(key=lambda m: (abs(_monster_xp(m) - target_unit_xp), str(m.get("name") or "")))
    chosen = candidates[0]
    unit_xp = max(10, _monster_xp(chosen))
    quantity = max(1, min(6, budget // unit_xp))
    # Account roughly for 5e multi-monster multiplier when >= 2 foes
    if quantity >= 3:
        quantity = max(1, quantity // 2)

    encounter_dict = {
        "encounter_text": (
            f"**{difficulty.title()} {edition} Encounter ({location or 'Wilderness'})**\n\n"
            f"A group of **{quantity}x {chosen['name']}** (CR {chosen.get('cr', '?')}, {unit_xp} XP each) "
            f"ambushes the party of {p_size} level-{lvl} adventurers."
        ),
        "monsters": [
            {
                "name": chosen["name"],
                "hp": int(chosen.get("hp", 10)),
                "ac": int(chosen.get("ac", 12)),
                "dex": _monster_dex(chosen),
                "quantity": quantity,
                "statblock_summary": (
                    f"{chosen.get('size', '')} {chosen.get('type', '')} | "
                    f"CR {chosen.get('cr', '?')} | AC {chosen.get('ac', 12)} | HP {chosen.get('hp', 10)}"
                ).strip(),
            }
        ],
    }
    return EncounterSchema(**encounter_dict).model_dump()


def generate_random_encounter(
    party_size: int,
    avg_level: int,
    location: str,
    edition: str = EDITION_2014,
    difficulty: str = "Medium",
) -> dict:
    """Generates an encounter with canonical SRD monster stats and deterministic fallback."""
    prompt = RANDOM_ENCOUNTER_PROMPT.format(
        edition=edition,
        party_size=party_size,
        avg_level=avg_level,
        location=location,
        difficulty=difficulty,
    )
    result = generate_ai_json(prompt)
    if isinstance(result, dict):
        try:
            hydrated = _hydrate_encounter_from_bestiary(dict(result), edition)
            return EncounterSchema(**hydrated).model_dump()
        except Exception as e:
            logger.warning(f"Encounter generation failed validation: {e}")

    return _build_deterministic_encounter(party_size, avg_level, location, edition, difficulty)


def generate_riddle(location: str, edition: str = EDITION_2014) -> str:
    """Generates a thematic riddle based on the environment."""
    prompt = RIDDLE_PROMPT.format(
        edition=edition,
        location=location[:2000],
    )
    return generate_ai_response(prompt, use_cache=False)


def generate_npc(npc_concept: str, edition: str = EDITION_2014) -> str:
    """Creates a thematic NPC."""
    prompt = NPC_PROMPT.format(
        edition=edition,
        npc_concept=npc_concept[:2000],
    )
    return generate_ai_response(prompt, use_cache=False)


def generate_session_prep(campaign_notes: str, party_info: str) -> str:
    """Generates plot hooks and session developments."""
    prompt = SESSION_PREP_PROMPT.format(
        campaign_notes=f"<notes>\n{campaign_notes[:12000]}\n</notes>",
        party_info=party_info[:6000],
    )
    return generate_ai_response(prompt, use_cache=False)


def create_manual_npc(
    name: str,
    role: str,
    race: str,
    ac: int,
    hp_max: int,
    speed: int,
    char_level: int,
    stats: dict,
    weapons: list = None,
    features_traits: list = None,
    backstory: str = "",
    dnd_edition: str = "2014 Edition",
    char_portrait: str = None,
) -> dict:
    """Builds and validates a manual NPC character dictionary."""
    import uuid

    from backend.core.schemas import CharacterSchema

    if not name or not name.strip():
        raise ValueError("NPC name cannot be empty.")

    new_char_id = str(uuid.uuid4())[:8]

    # Ensure stats are formatted correctly
    stats_clean = {
        "STR": int(stats.get("STR", 10)),
        "DEX": int(stats.get("DEX", 10)),
        "CON": int(stats.get("CON", 10)),
        "INT": int(stats.get("INT", 10)),
        "WIS": int(stats.get("WIS", 10)),
        "CHA": int(stats.get("CHA", 10)),
    }

    weapons_clean = []
    if weapons:
        for w in weapons:
            weapons_clean.append(
                {
                    "name": str(w.get("name") or "Unknown Weapon"),
                    "attack_bonus": str(w.get("attack_bonus") or "+0"),
                    "damage_dice": str(w.get("damage_dice") or "1d4"),
                    "damage_bonus": str(w.get("damage_bonus") or "+0"),
                    "is_custom": True,
                }
            )

    features_clean = []
    if features_traits:
        for ft in features_traits:
            features_clean.append(
                {
                    "name": str(ft.get("name") or "Feature"),
                    "description": str(ft.get("description") or ""),
                }
            )

    char_dict = {
        "char_id": new_char_id,
        "is_npc": True,
        "char_name": name.strip(),
        "char_class": role[:20] if role else "Monster",
        "race": race.strip() if race else "Unknown",
        "background": "Manual NPC",
        "dnd_edition": dnd_edition,
        "char_level": max(1, int(char_level)),
        "armor_class": max(0, int(ac)),
        "hp_max": max(1, int(hp_max)),
        "hp_current": max(1, int(hp_max)),
        "speed": max(0, int(speed)),
        "stats": stats_clean,
        "features_traits": features_clean,
        "weapons": weapons_clean,
        "backstory": backstory.strip(),
        "equipment": [],
        "languages": ["Common"],
        "tool_proficiencies": [],
        "char_portrait": char_portrait,
    }

    # Validate against CharacterSchema
    validated = CharacterSchema.model_validate(char_dict, strict=False)
    return validated.model_dump()
