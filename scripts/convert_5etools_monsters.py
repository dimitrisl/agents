#!/usr/bin/env python3
"""5e.tools Bestiary Converter for Phyrexian Forge.

Converts raw 5e.tools bestiary JSON files (e.g., bestiary-mm.json) into the
project's native Pydantic Monster format (data/rules/monsters_{edition}.json).

Features:
- Cleans 5e.tools formatting tags ({@damage ...}, {@hit ...}, {@spell ...}, etc.)
- Normalizes sizes, alignments, speeds, AC, and HP
- Parses attack bonuses, damage dice, and damage types from action descriptions
- Validates every monster against backend.core.schemas.Monster
- Supports merging with existing monsters without duplicates
- Supports optional direct seeding to MongoDB Atlas / local DB
"""

import argparse
import asyncio
import glob
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import pymongo

# Add repository root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.schemas import Monster, MonsterAction, MonsterStats, MonsterTrait  # noqa: E402
from server.db_async import get_database  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BestiaryConverter")

# Size mapping
SIZE_MAP = {
    "T": "Tiny",
    "S": "Small",
    "M": "Medium",
    "L": "Large",
    "H": "Huge",
    "G": "Gargantuan",
}

# Alignment mapping
ALIGNMENT_MAP = {
    "L": "lawful",
    "N": "neutral",
    "C": "chaotic",
    "G": "good",
    "E": "evil",
    "U": "unaligned",
    "A": "any alignment",
}


def clean_5etools_tags(text: str) -> str:
    """Removes or converts 5e.tools markup tags into readable standard English.

    Examples:
    - {@hit 5} -> +5
    - {@damage 1d6 + 2} -> 1d6 + 2
    - {@dc 13} -> DC 13
    - {@spell fireball} -> Fireball
    - {@condition poisoned} -> poisoned
    - {@atk mw} -> Melee Weapon Attack:
    """
    if not isinstance(text, str):
        return str(text)

    # Attack types (2014 @atk and 2024 @atkr)
    text = re.sub(r"\{@atkr? mw\}", "Melee Weapon Attack:", text)
    text = re.sub(r"\{@atkr? rw\}", "Ranged Weapon Attack:", text)
    text = re.sub(r"\{@atkr? ms\}", "Melee Spell Attack:", text)
    text = re.sub(r"\{@atkr? rs\}", "Ranged Spell Attack:", text)
    text = re.sub(r"\{@atkr? mw,rw\}", "Melee or Ranged Weapon Attack:", text)
    text = re.sub(r"\{@atkr? m\}", "Melee Attack:", text)
    text = re.sub(r"\{@atkr? r\}", "Ranged Attack:", text)
    text = re.sub(r"\{@atkr? m,r\}", "Melee or Ranged Attack:", text)
    text = re.sub(r"\{@atkr? [^}]+\}", "Attack:", text)

    # Hit / DC
    text = re.sub(r"\{@hit ([+-]?\d+)\}", r"+\1", text)
    text = re.sub(r"\{@dc (\d+)\}", r"DC \1", text)
    text = re.sub(r"\{@h\}", "Hit: ", text)

    # Dice & Damage
    text = re.sub(r"\{@damage ([^}]+)\}", r"\1", text)
    text = re.sub(r"\{@dice ([^}]+)\}", r"\1", text)

    # Entities: spells, items, conditions, creatures, skills, senses
    text = re.sub(
        r"\{@(spell|item|condition|creature|skill|sense|feat|action) ([^}|]+)(?:\|[^}]+)?\}",
        r"\2",
        text,
    )

    # Generic remaining tags {@tag content|...} -> content
    text = re.sub(r"\{@[a-zA-Z0-9_]+ ([^}|]+)(?:\|[^}]+)?\}", r"\1", text)

    # Clean double spaces
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def parse_cr(cr_raw: Any) -> Tuple[str, float]:
    """Extracts string CR and numeric CR (e.g. '1/4' -> ('1/4', 0.25))."""
    if isinstance(cr_raw, dict):
        cr_str = str(cr_raw.get("cr", "0"))
    else:
        cr_str = str(cr_raw or "0")

    cr_str = cr_str.strip()
    if "/" in cr_str:
        try:
            num, den = cr_str.split("/")
            return cr_str, float(num) / float(den)
        except Exception:
            return cr_str, 0.0

    try:
        return cr_str, float(cr_str)
    except Exception:
        return cr_str, 0.0


def parse_size(size_raw: Any) -> str:
    """Parses 5e.tools size array or string into full name."""
    if isinstance(size_raw, list) and size_raw:
        val = str(size_raw[0]).upper()
        return SIZE_MAP.get(val, "Medium")
    if isinstance(size_raw, str):
        val = size_raw.upper()
        return SIZE_MAP.get(val, size_raw.capitalize())
    return "Medium"


def parse_type(type_raw: Any) -> str:
    """Parses type which can be string or dict with tags."""
    if isinstance(type_raw, dict):
        base = type_raw.get("type", "humanoid")
        tags = type_raw.get("tags", [])
        if tags:
            tag_str = ", ".join(t if isinstance(t, str) else t.get("tag", "") for t in tags)
            return f"{base} ({tag_str})"
        return base
    if isinstance(type_raw, str):
        return type_raw.lower()
    return "humanoid"


def parse_alignment(alignment_raw: Any) -> str:
    """Parses alignment array like ['L', 'E'] -> 'lawful evil'."""
    if not alignment_raw:
        return "unaligned"
    if isinstance(alignment_raw, str):
        return alignment_raw.lower()

    if isinstance(alignment_raw, list):
        parts = []
        for a in alignment_raw:
            if isinstance(a, str):
                parts.append(ALIGNMENT_MAP.get(a.upper(), a.lower()))
            elif isinstance(a, dict) and "alignment" in a:
                parts.append(parse_alignment(a["alignment"]))
        return " ".join(parts) if parts else "unaligned"
    return "unaligned"


def parse_ac(ac_raw: Any) -> int:
    """Parses AC array/int/dict from 5e.tools."""
    if isinstance(ac_raw, int):
        return ac_raw
    if isinstance(ac_raw, list) and ac_raw:
        first = ac_raw[0]
        if isinstance(first, int):
            return first
        if isinstance(first, dict):
            return int(first.get("ac", 10))
    if isinstance(ac_raw, dict):
        return int(ac_raw.get("ac", 10))
    try:
        return int(ac_raw)
    except Exception:
        return 10


def parse_hp(hp_raw: Any) -> int:
    """Parses HP object or number."""
    if isinstance(hp_raw, int):
        return max(1, hp_raw)
    if isinstance(hp_raw, dict):
        return max(1, int(hp_raw.get("average", 10)))
    try:
        return max(1, int(hp_raw))
    except Exception:
        return 10


def parse_speed(speed_raw: Any) -> str:
    """Converts 5e.tools speed dict/string into readable speed."""
    if isinstance(speed_raw, str):
        return speed_raw
    if isinstance(speed_raw, dict):
        parts = []
        walk = speed_raw.get("walk")
        if walk is not None:
            if isinstance(walk, dict):
                parts.append(f"{walk.get('number', 30)} ft. ({walk.get('condition', '')})")
            else:
                parts.append(f"{walk} ft.")
        for mode in ["fly", "swim", "climb", "burrow"]:
            if mode in speed_raw:
                val = speed_raw[mode]
                if isinstance(val, dict):
                    parts.append(f"{mode} {val.get('number', 0)} ft.")
                elif val:
                    parts.append(f"{mode} {val} ft.")
        return ", ".join(parts) if parts else "30 ft."
    return "30 ft."


def parse_entries_to_text(entries: Any) -> str:
    """Extracts and flattens nested entries into clean text."""
    if isinstance(entries, str):
        return clean_5etools_tags(entries)
    if not isinstance(entries, list):
        return ""

    lines = []
    for item in entries:
        if isinstance(item, str):
            lines.append(clean_5etools_tags(item))
        elif isinstance(item, dict):
            if "name" in item and "entries" in item:
                sub_text = parse_entries_to_text(item["entries"])
                lines.append(f"{item['name']}: {sub_text}")
            elif "entries" in item:
                lines.append(parse_entries_to_text(item["entries"]))
    return " ".join(lines).strip()


def parse_actions(actions_raw: Optional[List[Dict[str, Any]]]) -> List[MonsterAction]:
    """Converts 5e.tools action list into MonsterAction list with robust damage/attack extraction."""
    results = []
    if not isinstance(actions_raw, list):
        return results

    for act in actions_raw:
        name = act.get("name", "Action")
        entries = act.get("entries", [])
        raw_str = json.dumps(entries)
        desc = parse_entries_to_text(entries)

        # 1. Extract attack bonus directly from raw {@hit X} tag or text
        attack_bonus = None
        hit_tag_match = re.search(r"\{@hit\s+([+-]?\d+)\}", raw_str)
        if hit_tag_match:
            try:
                attack_bonus = int(hit_tag_match.group(1))
            except Exception:
                pass
        else:
            hit_match = re.search(r"([+-]\d+)\s+to\s+hit", desc, re.IGNORECASE)
            if hit_match:
                try:
                    attack_bonus = int(hit_match.group(1))
                except Exception:
                    pass

        # 2. Extract damage dice directly from raw {@damage X} tag or text
        damage_dice = None
        dmg_tag_match = re.search(r"\{@damage\s+([^}]+)\}", raw_str)
        if dmg_tag_match:
            damage_dice = dmg_tag_match.group(1).strip()
        else:
            dmg_match = re.search(r"Hit:\s*(?:\d+\s*)?(?:\(([^)]+)\))", desc, re.IGNORECASE)
            if dmg_match:
                damage_dice = dmg_match.group(1).strip()

        # 3. Extract damage type
        damage_type = None
        type_match = re.search(
            r"\b(bludgeoning|piercing|slashing|fire|cold|lightning|thunder|acid|poison|necrotic|radiant|force|psychic)\s+damage\b",
            desc,
            re.IGNORECASE,
        )
        if type_match:
            damage_type = type_match.group(1).lower()

        results.append(
            MonsterAction(
                name=name,
                attack_bonus=attack_bonus,
                damage_dice=damage_dice,
                damage_type=damage_type if damage_type else None,
                description=desc,
            )
        )
    return results


def parse_traits(traits_raw: Optional[List[Dict[str, Any]]]) -> List[MonsterTrait]:
    """Converts traits into MonsterTrait list."""
    results = []
    if not isinstance(traits_raw, list):
        return results
    for t in traits_raw:
        name = t.get("name", "Trait")
        desc = parse_entries_to_text(t.get("entries", []))
        results.append(MonsterTrait(name=name, description=desc))
    return results


def flatten_string_list(raw_list: Any) -> List[str]:
    """Flattens mixed string or dict lists (like immunities/resistances)."""
    if not raw_list or not isinstance(raw_list, list):
        return []
    output = []
    for item in raw_list:
        if isinstance(item, str):
            output.append(clean_5etools_tags(item).lower())
        elif isinstance(item, dict):
            for k in ["resist", "immune", "conditionImmune"]:
                if k in item and isinstance(item[k], list):
                    output.extend(flatten_string_list(item[k]))
    return list(set(output))


def convert_5etools_monster(raw: Dict[str, Any], edition: str = "2014") -> Optional[Monster]:
    """Converts a single 5e.tools monster dictionary to our Pydantic Monster model."""
    name = raw.get("name")
    if not name or not isinstance(name, str):
        return None

    name = name.strip()
    source = str(raw.get("source", "MM")).upper()
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

    if source in ("MM", "XMM"):
        monster_id = f"srd_{slug}_{edition}"
        display_name = name
    else:
        monster_id = f"srd_{slug}_{source.lower()}_{edition}"
        display_name = f"{name} ({source})"

    cr_str, cr_num = parse_cr(raw.get("cr", "0"))
    hp_val = parse_hp(raw.get("hp", 10))

    # Core stats
    stats = MonsterStats(
        str=max(1, min(30, int(raw.get("str", 10)))),
        dex=max(1, min(30, int(raw.get("dex", 10)))),
        con=max(1, min(30, int(raw.get("con", 10)))),
        int=max(1, min(30, int(raw.get("int", 10)))),
        wis=max(1, min(30, int(raw.get("wis", 10)))),
        cha=max(1, min(30, int(raw.get("cha", 10)))),
    )

    # Senses & languages
    senses_list = raw.get("senses", [])
    senses = (
        ", ".join(clean_5etools_tags(s) for s in senses_list)
        if isinstance(senses_list, list)
        else str(senses_list)
    )
    passive = raw.get("passive")
    if passive and "passive Perception" not in senses:
        senses = f"{senses}, passive Perception {passive}".strip(", ")

    languages_list = raw.get("languages", [])
    languages = (
        ", ".join(clean_5etools_tags(lang) for lang in languages_list)
        if isinstance(languages_list, list)
        else str(languages_list)
    )

    # Immunities
    resists = flatten_string_list(raw.get("resist"))
    immunes = flatten_string_list(raw.get("immune"))
    cond_immunes = flatten_string_list(raw.get("conditionImmune"))

    raw_desc = clean_5etools_tags(raw.get("flavor", "") or "")
    source_prefix = f"[{source}]"
    final_desc = f"{source_prefix} {raw_desc}".strip() if raw_desc else source_prefix

    try:
        monster = Monster(
            id=monster_id,
            name=display_name,
            edition=edition,
            origin="official",
            is_public=True,
            size=parse_size(raw.get("size")),
            type=parse_type(raw.get("type")),
            alignment=parse_alignment(raw.get("alignment")),
            cr=cr_str,
            cr_numeric=cr_num,
            ac=parse_ac(raw.get("ac", 10)),
            hp=hp_val,
            max_hp=hp_val,
            speed=parse_speed(raw.get("speed")),
            stats=stats,
            senses=senses,
            languages=languages,
            description=final_desc,
            traits=parse_traits(raw.get("trait")),
            actions=parse_actions(raw.get("action")),
            bonus_actions=parse_actions(raw.get("bonus")),
            reactions=parse_actions(raw.get("reaction")),
            legendary_actions=parse_actions(raw.get("legendary")),
            damage_resistances=resists,
            damage_immunities=immunes,
            condition_immunities=cond_immunes,
        )
        return monster
    except Exception as e:
        logger.warning(f"Failed to validate monster {name}: {e}")
        return None


async def seed_to_mongo(monsters: List[Monster]) -> bool:
    """Seeds converted monsters directly into MongoDB Atlas `official_monsters` collection."""
    if not monsters:
        logger.warning("No monsters to seed into MongoDB.")
        return False

    try:
        db = await get_database()
        collection = db["official_monsters"]

        # Ensure performance indexes
        await collection.create_index(
            [("id", pymongo.ASCENDING)], unique=True, name="uniq_official_monsters_id"
        )
        await collection.create_index(
            [
                ("edition", pymongo.ASCENDING),
                ("cr_numeric", pymongo.ASCENDING),
                ("name", pymongo.ASCENDING),
            ],
            name="idx_official_monsters_edition_cr_name",
        )
        await collection.create_index(
            [("edition", pymongo.ASCENDING), ("type", pymongo.ASCENDING)],
            name="idx_official_monsters_edition_type",
        )

        operations = []
        for m in monsters:
            doc = m.model_dump(mode="python")
            operations.append(pymongo.UpdateOne({"id": m.id}, {"$set": doc}, upsert=True))

        if operations:
            res = await collection.bulk_write(operations, ordered=False)
            logger.info(
                f"MongoDB Seed Complete: {res.upserted_count} inserted, "
                f"{res.modified_count} updated, {res.matched_count} matched."
            )
            total = await collection.count_documents({})
            logger.info(f"Total official monsters currently in MongoDB: {total}")
        return True
    except Exception as e:
        logger.error(f"Failed to seed monsters to MongoDB: {e}")
        return False


def run_conversion(
    input_paths: List[str],
    output_path: Optional[str] = None,
    default_edition: str = "2014",
    merge: bool = True,
    seed_mongo: bool = False,
):
    """Processes one or more input JSON files, optionally writes output JSON, and optionally seeds MongoDB."""
    matched_files = []
    for pattern in input_paths:
        expanded = glob.glob(pattern)
        if expanded:
            matched_files.extend(expanded)
        elif os.path.exists(pattern):
            matched_files.append(pattern)

    matched_files = sorted(list(set(matched_files)))
    if not matched_files:
        logger.error(f"No matching files found for inputs: {input_paths}")
        return False

    logger.info(
        f"Processing {len(matched_files)} files: {[os.path.basename(f) for f in matched_files]}"
    )

    converted_monsters: List[Monster] = []
    converted_dict: Dict[str, dict] = {}

    # Load existing if merge & file output
    if output_path and merge and os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    for m in existing:
                        if isinstance(m, dict) and "id" in m:
                            converted_dict[m["id"]] = m
            logger.info(f"Loaded {len(converted_dict)} existing monsters for merging.")
        except Exception as e:
            logger.warning(f"Could not load existing file {output_path} for merging: {e}")

    total_raw = 0
    total_converted = 0

    for filepath in matched_files:
        filename = os.path.basename(filepath).lower()
        edition = "2024" if "xmm" in filename or "2024" in filename else default_edition

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read JSON from {filepath}: {e}")
            continue

        raw_monsters = data.get("monster", []) if isinstance(data, dict) else data
        if not isinstance(raw_monsters, list):
            logger.warning(f"Skipping {filepath}: no monster list found.")
            continue

        file_converted = 0
        for raw in raw_monsters:
            total_raw += 1
            m = convert_5etools_monster(raw, edition=edition)
            if m:
                converted_monsters.append(m)
                converted_dict[m.id] = m.model_dump(mode="json")
                file_converted += 1
                total_converted += 1

        logger.info(
            f"-> {os.path.basename(filepath)} ({edition}): {file_converted}/{len(raw_monsters)} converted."
        )

    if output_path:
        final_list = sorted(
            list(converted_dict.values()),
            key=lambda x: (x.get("cr_numeric", 0.0), x.get("name", "")),
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully wrote {len(final_list)} monsters to {output_path}!")

    if seed_mongo:
        logger.info(
            f"Seeding {len(converted_monsters)} converted monsters to MongoDB Atlas collection 'official_monsters'..."
        )
        asyncio.run(seed_to_mongo(converted_monsters))

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert 5e.tools bestiary to Phyrexian Forge format"
    )
    parser.add_argument(
        "--input",
        "-i",
        nargs="+",
        required=True,
        help="Path(s) or glob pattern(s) to raw 5e.tools JSON files (e.g. ~/Downloads/bestiary-*.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional path to destination JSON file (omit if only seeding to MongoDB)",
    )
    parser.add_argument(
        "--edition",
        "-e",
        default="2014",
        choices=["2014", "2024"],
        help="Default D&D edition if not inferred from filename",
    )
    parser.add_argument(
        "--no-merge", action="store_true", help="Overwrite instead of merging with existing dataset"
    )
    parser.add_argument(
        "--seed-mongo",
        "--db",
        action="store_true",
        help="Seed converted monsters directly into MongoDB Atlas",
    )

    args = parser.parse_args()
    success = run_conversion(
        input_paths=args.input,
        output_path=args.output,
        default_edition=args.edition,
        merge=not args.no_merge,
        seed_mongo=args.seed_mongo,
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
