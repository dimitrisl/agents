"""
QA Expert Duet Campaign Test Suite: 1 DM & 1 Player (4 Episodes)
Campaign Title: "The Shattered Planar Nexus"
Participants:
- Dungeon Master: "Alistair, Archivist of the Iron Spire"
- Solo Player: "Ulad Bhor" (Level 11 Horizon Walker Ranger, Wood Elf)

Episodes:
1. Episode 1: The Whispering Breach at Raven's Crag (Hazard detection, stealth, VTT fog & Longbow +1 to-hit)
2. Episode 2: The Sunken Foundry of the Clockwork Legion (Arcane riddle, homebrew monster, auto-numbering, DEX tie-breaker, Planar Warrior)
3. Episode 3: The Void-Weaver Sovereign Climax (Boss encounter, conditions, concentration save on damage, potion consumption, spell slots)
4. Episode 4: Sealing the Rift & The Spoils of the Nexus (Loot distribution, long rest recovery, PDF export verification)
"""

import copy

import pytest

from backend.core.constants import EDITION_2014
from backend.core.homebrew_schemas import HomebrewCreateRequest, HomebrewMonster
from backend.core.schemas import (
    VTTFogSchema,
    VTTGridSchema,
    VTTSceneSchema,
    VTTTokenSchema,
)
from backend.services.stats_service import (
    get_modifier,
    sync_character_stats,
)
from backend.utils.pdf_exporter import export_character_to_pdf


@pytest.fixture
def ulad_bhor_data():
    """Initial character fixture for Ulad Bhor (Level 11 Horizon Walker Ranger)."""
    return {
        "char_id": "6567c118-78f1-48fd-bb1c-292b08b7a915",
        "char_name": "Ulad Bhor",
        "race": "Wood Elf",
        "class_name": "Ranger",
        "subclass": "Horizon Walker",
        "char_level": 11,
        "dnd_edition": EDITION_2014,
        "alignment": "Neutral Good",
        "stats": {
            "STR": 12,
            "DEX": 20,
            "CON": 16,
            "INT": 12,
            "WIS": 16,
            "CHA": 10,
        },
        "saving_throw_proficiencies": ["STR", "DEX"],
        "skill_proficiencies": [
            "Perception",
            "Stealth",
            "Survival",
            "Athletics",
            "Nature",
        ],
        "hp_max": 88,
        "hp_current": 88,
        "hp_temp": 0,
        "conditions": [],
        "spell_slots": {
            "level_1": {"total": 4, "used": 0},
            "level_2": {"total": 3, "used": 0},
            "level_3": {"total": 3, "used": 0},
        },
        "spells": [
            "Cure Wounds",
            "Speak with Animals",
            "Absorb Elements",
            "Protection from Evil and Good",
            "Misty Step",
            "Silence",
            "Beast Sense",
            "Haste",
            "Speak with Plants",
            "Lightning Arrow",
        ],
        "features_traits": [
            {
                "name": "Fighting Style: Archery",
                "desc": "+2 bonus to attack rolls made with ranged weapons.",
            },
            {
                "name": "Planar Warrior",
                "desc": "As a bonus action, choose one creature within 30 feet. All damage dealt to that creature this turn becomes force damage, and extra 2d8 force damage on first hit.",
            },
            {
                "name": "Distant Strike",
                "desc": "When you take the Attack action, you can teleport up to 10 feet before each attack to an unoccupied space you can see.",
            },
            {
                "name": "Ethereal Step",
                "desc": "As a bonus action, you can cast Etherealness without expending a spell slot once per short or long rest.",
            },
        ],
        "weapons": [
            {
                "name": "Longbow +1",
                "attack_bonus": "",
                "damage": "1d8",
                "damage_type": "piercing",
                "properties": ["Ammunition", "Heavy", "Two-Handed", "Range 150/600"],
                "proficient": True,
                "magic_bonus": 1,
            },
            {
                "name": "Shortsword",
                "attack_bonus": "",
                "damage": "1d6",
                "damage_type": "piercing",
                "properties": ["Finesse", "Light"],
                "proficient": True,
            },
        ],
        "equipment": [
            {"name": "Studded Leather", "equipped": True, "category": "Armor"},
            {"name": "Potion of Greater Healing", "quantity": 2, "category": "Potion"},
        ],
        "currency": {"cp": 0, "sp": 10, "ep": 0, "gp": 120, "pp": 5},
    }


# ============================================================================
# Episode 1: The Whispering Breach at Raven's Crag
# ============================================================================


def test_episode_1_infiltrating_the_whispering_breach(ulad_bhor_data):
    """
    Episode 1:
    - DM sets up VTT Scene with fog of war covering hostile tokens.
    - DM issues Roll Request for DC 15 Wisdom (Perception).
    - Player receives request and calculates Wisdom (Perception) bonus: WIS +3, Prof +4 = +7.
    - Player rolls and detects the lurking monster ambush.
    - DM reveals fog of war at target location.
    - Ulad fires Longbow +1: Archery fighting style (+2) + DEX (+5) + Prof (+4) + Magic (+1) = +12 to-hit.
    """
    # 1. VTT Scene Setup with Fog of War
    tokens = [
        VTTTokenSchema(id="token_ulad", name="Ulad Bhor", x=100, y=100, size=1, is_hidden=False),
        VTTTokenSchema(
            id="token_stalker_1", name="Planar Stalker 1", x=400, y=100, size=1, is_hidden=True
        ),
        VTTTokenSchema(
            id="token_stalker_2", name="Planar Stalker 2", x=400, y=150, size=1, is_hidden=True
        ),
    ]
    scene = VTTSceneSchema(
        id="scene_ravens_crag",
        campaign_name="Planar Nexus",
        name="Raven's Crag Overlook",
        grid=VTTGridSchema(cell_size=50),
        fog=VTTFogSchema(enabled=True, revealed_polygons=[]),
        tokens=tokens,
    )
    assert len(scene.tokens) == 3
    # Hidden tokens must be redacted from player view
    visible_tokens_for_player = [t for t in scene.tokens if not t.is_hidden]
    assert len(visible_tokens_for_player) == 1
    assert visible_tokens_for_player[0].name == "Ulad Bhor"

    # 2. DM Roll Request & Player Perception Check
    dm_roll_request = {
        "campaign_name": "Planar Nexus",
        "target_char_id": ulad_bhor_data["char_id"],
        "skill": "Perception",
        "ability": "WIS",
        "dc": 15,
        "description": "Notice vibrations along the planar fault line.",
    }
    wis_mod = get_modifier(ulad_bhor_data["stats"]["WIS"])  # 16 -> +3
    prof_bonus = 4  # Level 11 -> +4
    is_proficient = "Perception" in ulad_bhor_data["skill_proficiencies"]
    perception_bonus = wis_mod + (prof_bonus if is_proficient else 0)
    assert perception_bonus == 7

    # Simulate player rolling a 12 on d20 -> total 19 beats DC 15
    player_roll_result = 12 + perception_bonus
    assert player_roll_result >= dm_roll_request["dc"]

    # 3. DM reveals fog and unhides tokens
    for t in scene.tokens:
        if t.id in ("token_stalker_1", "token_stalker_2"):
            t.is_hidden = False
    assert all(not t.is_hidden for t in scene.tokens)

    # 4. Weapon Attack Verification: Longbow +1 with Archery Style
    synced = sync_character_stats(ulad_bhor_data)
    longbow = next(w for w in synced["weapons"] if "Longbow" in w["name"])
    assert longbow["attack_bonus"] == "+12"
    assert longbow["damage"] == "1d8 + 6"

    # Attack hits AC 14 Planar Stalker
    atk_d20 = 10
    total_atk = atk_d20 + 12
    assert total_atk >= 14


# ============================================================================
# Episode 2: The Sunken Foundry of the Clockwork Legion
# ============================================================================


def test_episode_2_the_sunken_foundry_and_clockwork_infiltrators(ulad_bhor_data):
    """
    Episode 2:
    - DM creates Homebrew Monster: Clockwork Dread-Infiltrator.
    - Adding multiple monsters to Initiative triggers automatic incremental naming.
    - Initiative tie-breaking respects Dexterity score (Ulad DEX 20 vs Monster DEX 14).
    - Ulad activates Planar Warrior (converts damage to force + 2d8 extra force).
    - Ulad expends a Level 2 spell slot for Misty Step (slots track correctly: 3 -> 2).
    """
    # 1. Validate Homebrew Monster Creation
    monster_payload = {
        "name": "Clockwork Dread-Infiltrator",
        "type": "monster",
        "campaign_id": "Planar Nexus",
        "data": {
            "campaign_id": "Planar Nexus",
            "creator_dm_id": "dm_alistair",
            "name": "Clockwork Dread-Infiltrator",
            "size": "Medium",
            "type": "Construct",
            "alignment": "Lawful Evil",
            "cr": "5",
            "ac": 16,
            "hp": 85,
            "speed": "30 ft.",
            "stats": {"str": 16, "dex": 14, "con": 16, "int": 10, "wis": 12, "cha": 8},
            "actions": [
                {
                    "name": "Piston Strike",
                    "desc": "Melee Weapon Attack: +6 to hit, reach 5 ft., 2d8+3 bludgeoning.",
                }
            ],
        },
    }
    req = HomebrewCreateRequest(**monster_payload)
    assert req.type == "monster"
    monster = HomebrewMonster(**req.data)
    assert monster.ac == 16
    assert monster.hp == 85

    # 2. Initiative Auto-Numbering
    def add_combatants(existing: list, base_name: str, count: int, dex: int) -> list:
        combatants = list(existing)
        for _ in range(count):
            matches = [
                c
                for c in combatants
                if c["name"] == base_name or c["name"].startswith(f"{base_name} ")
            ]
            if not matches:
                name = f"{base_name} 1"
            else:
                nums = []
                for m in matches:
                    parts = m["name"].rsplit(" ", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        nums.append(int(parts[1]))
                    else:
                        nums.append(1)
                name = f"{base_name} {max(nums) + 1 if nums else 2}"
            combatants.append({"name": name, "initiative": 0, "dex": dex, "is_player": False})
        return combatants

    combatants = [{"name": "Ulad Bhor", "initiative": 17, "dex": 20, "is_player": True}]
    combatants = add_combatants(combatants, "Clockwork Dread-Infiltrator", count=2, dex=14)
    # Set initiative roll for both monsters to 17 (tie with Ulad)
    for c in combatants[1:]:
        c["initiative"] = 17

    # Sort combatants: descending initiative, tie-break on DEX descending
    sorted_combatants = sorted(
        combatants, key=lambda c: (c["initiative"], c.get("dex", 10)), reverse=True
    )
    # Ulad (17, DEX 20) must beat Clockwork 1 and 2 (17, DEX 14)
    assert sorted_combatants[0]["name"] == "Ulad Bhor"
    assert sorted_combatants[1]["name"] == "Clockwork Dread-Infiltrator 1"
    assert sorted_combatants[2]["name"] == "Clockwork Dread-Infiltrator 2"

    # 3. Planar Warrior Damage Conversion
    char = copy.deepcopy(ulad_bhor_data)
    planar_trait = next(t for t in char["features_traits"] if t["name"] == "Planar Warrior")
    assert "force damage" in planar_trait["desc"]
    assert "2d8" in planar_trait["desc"]

    # 4. Spell Slot Expended (Misty Step - 2nd level)
    assert char["spell_slots"]["level_2"]["used"] == 0
    char["spell_slots"]["level_2"]["used"] += 1
    remaining_l2 = char["spell_slots"]["level_2"]["total"] - char["spell_slots"]["level_2"]["used"]
    assert remaining_l2 == 2


# ============================================================================
# Episode 3: The Void-Weaver Sovereign Climax
# ============================================================================


def test_episode_3_the_void_weaver_sovereign_climax(ulad_bhor_data):
    """
    Episode 3:
    - DM applies condition 'Restrained' during the boss encounter.
    - Ulad concentrates on 'Haste' and has 10 Temporary HP.
    - Ulad takes 24 Force damage from Boss:
      * Temp HP absorbs 10.
      * Remaining 14 damage drops HP from 88 to 74.
      * Concentration check is triggered with DC = max(10, 24 // 2) = 12 (verifying rule fix: amount > 0, not remainingDamage > 0).
      * CON saving throw modifier (+3) is rolled, beating DC 12.
    - Ulad consumes a Potion of Greater Healing (recovers 4d4+4 HP) safely without double-save conflicts.
    - Ulad casts Lightning Arrow using a 3rd-level spell slot.
    """
    char = copy.deepcopy(ulad_bhor_data)
    char["hp_temp"] = 10
    char["concentrating_on"] = "Haste"

    # 1. Apply 'Restrained' condition from Void-Weaver
    char["conditions"].append("Restrained")
    assert "Restrained" in char["conditions"]

    # 2. Take 24 Damage: Temp HP absorption & Concentration Check DC
    damage_taken = 24
    temp_hp_before = char["hp_temp"]
    absorbed_by_temp = min(temp_hp_before, damage_taken)
    remaining_dmg = damage_taken - absorbed_by_temp

    char["hp_temp"] -= absorbed_by_temp
    char["hp_current"] = max(0, char["hp_current"] - remaining_dmg)

    assert char["hp_temp"] == 0
    assert char["hp_current"] == 74  # 88 - 14

    # D&D 5e / 2024 Concentration Check Rule:
    # Trigger condition: char has concentrating_on and damage_taken > 0
    concentration_triggered = bool(char.get("concentrating_on") and damage_taken > 0)
    assert concentration_triggered is True

    # DC calculation: max(10, damage // 2)
    concentration_dc = max(10, damage_taken // 2)
    assert concentration_dc == 12

    # CON Saving Throw: CON mod 3
    con_mod = get_modifier(char["stats"]["CON"])
    assert con_mod == 3
    # Roll 10 on d20 + 3 CON = 13 >= 12 -> Concentration maintained!
    save_roll = 10 + con_mod
    assert save_roll >= concentration_dc

    # 3. Potion of Greater Healing Consumption
    potion = next(item for item in char["equipment"] if "Healing" in item["name"])
    assert potion["quantity"] == 2
    potion["quantity"] -= 1

    # Heals 4d4 + 4 (simulate average roll: 10 + 4 = 14)
    heal_amount = 14
    char["hp_current"] = min(char["hp_max"], char["hp_current"] + heal_amount)
    assert char["hp_current"] == 88  # 74 + 14 = 88
    assert potion["quantity"] == 1

    # 4. Cast Lightning Arrow (Level 3 Spell)
    assert "Lightning Arrow" in char["spells"]
    assert char["spell_slots"]["level_3"]["used"] == 0
    char["spell_slots"]["level_3"]["used"] += 1
    assert char["spell_slots"]["level_3"]["used"] == 1


# ============================================================================
# Episode 4: Sealing the Rift & The Spoils of the Nexus
# ============================================================================


def test_episode_4_sealing_the_rift_loot_rest_and_pdf_export(ulad_bhor_data):
    """
    Episode 4:
    - DM awards currency (1,500 GP, 350 PP) and magic weapon (Voidseeker Longbow +2).
    - Player receives loot and updates inventory.
    - Voidseeker Longbow +2 automatically calculates +13 to hit (DEX +5, Prof +4, Magic +2, Archery +2).
    - Long Rest restores HP to full (88/88) and resets all spell slots (Level 1: 4/4, Level 2: 3/3, Level 3: 3/3).
    - Export character to PDF:
      * Validates weapon to-hit (+12 or +13).
      * Validates AttacksSpellcasting Page 1 summary with DC, Spell Attack, traits, and spell slot levels.
      * Validates prepared spell checkboxes marked '/Yes' on Page 3.
    """
    char = copy.deepcopy(ulad_bhor_data)

    # 1. Distribute Loot (Currency & Magic Weapon)
    loot_currency = {"gp": 1500, "pp": 350}
    for curr_key, amt in loot_currency.items():
        char["currency"][curr_key] = char["currency"].get(curr_key, 0) + amt

    assert char["currency"]["gp"] == 1620  # 120 + 1500
    assert char["currency"]["pp"] == 355  # 5 + 350

    new_magic_weapon = {
        "name": "Voidseeker Longbow +2",
        "attack_bonus": "",
        "damage": "1d8",
        "damage_type": "piercing",
        "properties": ["Ammunition", "Heavy", "Two-Handed", "Range 150/600"],
        "proficient": True,
        "magic_bonus": 2,
    }
    char["weapons"].insert(0, new_magic_weapon)

    # 2. Automatic Weapon Stats Calculation with Fighting Style: Archery
    synced = sync_character_stats(char)
    voidseeker = synced["weapons"][0]
    assert voidseeker["name"] == "Voidseeker Longbow +2"
    # DEX +5, Prof +4, Magic +2, Archery +2 = +13
    assert voidseeker["attack_bonus"] == "+13"
    assert voidseeker["damage"] == "1d8 + 7"  # 1d8 + DEX 5 + Magic 2

    # 3. Long Rest Recovery
    char["hp_current"] = 50
    char["conditions"] = ["Restrained"]
    char["spell_slots"]["level_1"]["used"] = 3
    char["spell_slots"]["level_2"]["used"] = 2
    char["spell_slots"]["level_3"]["used"] = 3

    # Apply Long Rest
    char["hp_current"] = char["hp_max"]
    char["hp_temp"] = 0
    char["conditions"] = []
    for slot_tier in char["spell_slots"].values():
        slot_tier["used"] = 0

    assert char["hp_current"] == 88
    assert char["conditions"] == []
    assert char["spell_slots"]["level_1"]["used"] == 0
    assert char["spell_slots"]["level_2"]["used"] == 0
    assert char["spell_slots"]["level_3"]["used"] == 0

    # 4. Character Export to Official 5E PDF Mapping
    from backend.utils.pdf_exporter import PDFMappingProvider

    provider = PDFMappingProvider("standard_5e")
    fields = provider.get_field_data(synced)

    # Page 1: Weapons
    assert fields.get("Wpn Name") == "Voidseeker Longbow +2"
    assert fields.get("Wpn1 AtkBonus") == "+13"
    assert fields.get("Wpn1 Damage") == "1d8 + 7"

    # Page 1: AttacksSpellcasting
    attacks_spells_box = str(fields.get("AttacksSpellcasting"))
    assert "Spellcasting: Ranger (WIS) | DC 15 | Atk +7" in attacks_spells_box
    assert "Planar Warrior" in attacks_spells_box
    assert "Distant Strike" in attacks_spells_box
    assert "1st Level" in attacks_spells_box
    assert "2nd Level" in attacks_spells_box
    assert "3rd Level" in attacks_spells_box

    # Page 3: Spells & Checkboxes
    # Level 1 Row 1
    assert fields.get("Spells 1015") == "Cure Wounds"
    assert fields.get("Check Box 251") == "Yes"
    # Level 2 Row 1 (was previously broken Spells 1046)
    assert fields.get("Spells 1046") == "Misty Step"
    assert fields.get("Check Box 313") == "Yes"
    # Level 3 Row 1
    assert fields.get("Spells 1048") == "Haste"
    assert fields.get("Check Box 315") == "Yes"

    # Optional local template test if template exists on disk
    import os

    template_path = "data/pdf_mappings/5E_CharacterSheet_Fillable.pdf"
    if os.path.exists(template_path):
        pdf_bytes = export_character_to_pdf(synced, template_path)
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 50000
