# 📖 Subsystem: Static Rules Data (`data/rules/`)

## 📌 Overview
The `data/rules/` directory stores static JSON datasets for the **2014 5th Edition** and **2024 5.5e Revision**. This knowledge base powers all deterministic build validation, level progressions, and stat derivations.

---

## 🔑 Key Datasets

| File / Folder | Edition | Description |
| :--- | :--- | :--- |
| `classes/` | 2014 & 2024 | Class progression tables (including 2014 PHB/TCoE `primary_ability`, `scaling` schedules, Fighter starting skill choices, and Second Wind formula), spell slot schedules, hit die, and feature descriptions per level. |
| `class_choices_2014.json` / `class_choices_2024.json` | 2014 / 2024 | Structured catalogs for build choices (`fighting_styles`, 2014 `pact_boons`, `eldritch_invocations` including 2024 L1 Pact Boons, `metamagic`, `maneuvers`, `artificer_infusions`/2024 Plans, `hunter_choices`, plus 2024 `divine_orders`, `primal_orders`, and `cunning_strikes`) powering interactive level-up & Manual Forge pickers (`GET /api/v1/rules/class-choices`). |
| `class_resources.json` | 2014 & 2024 | Data-driven class & subclass resource pools (Rage, Ki/Focus Points, Sorcery Points, Bardic Inspiration, Channel Divinity, Lay on Hands, 2014 Warlock L20 *Eldritch Master*, etc.), reset triggers (Short/Long Rest), scaling schedules, and Sorcerer Metamagic options. |
| `subclasses/` & `subclasses.json` | 2014 & 2024 | Complete archetype feature & combat-scaling catalogs across **all 13 classes in both editions** (`subclasses/2014/*.json` and `subclasses/2024/*.json`, synced 1:1 with `subclasses.json`, `subclass_features_2024.py`, and Forge subclass maps), Domain/Oath/Circle/Patron/Specialist `bonus_spells`, and subclass `armor_proficiencies`/`weapon_proficiencies`. |
| `spells_2014.json` / `spells_2024.json` | 2014 / 2024 | Spell catalogs (`spells_2014.json`: 403 spells including TCoE Optional Additional Class Spell `classes` tags such as 2014 Ranger *Revivify*; `spells_2024.json`: 358 spells covering all 2024 subclass `bonus_spells` entries) with level, school, casting time, range, components, duration, and descriptions. |
| `feats_2014.json` / `feats_2024.json` | 2014 / 2024 | Origin, General (including TCoE 2014 feats like *Fey Touched*, *Shadow Touched*, *Telekinetic*, *Metamagic Adept*), and 2024 Level 19+ Epic Boon feat definitions, prerequisite checks (`min_level`, `stat_requirements` / `INT_OR_WIS` / `STR_OR_DEX` / `WIS_OR_CHA` / `DEX_OR_CON`, armor/spellcasting gates enforced across both 2014 & 2024), and mechanical bonuses (`stat_bonus`, `hp_bonus_per_level`, `flat_hp_bonus`, `speed_bonus`). |
| `backgrounds_2014.json` / `backgrounds_2024.json` | 2014 / 2024 | Backgrounds with starting proficiencies, equipment, and 2024 Origin Feats. |
| `races_2014.json` / `races_2024.json` | 2014 / 2024 | Species traits, speed, structured `senses`, `damage_resistances`, `save_advantages`, `weapon_proficiencies`, `innate_spells` (`by_level`), `lineage_spells` (2024 Elf/Gnome/Tiefling sub-lineage spells), and ancestral mechanics. |
| `weapons.json` & `weapon_masteries_2024.json` | Both / 2024 | Weapon properties, damage dice, and 2024 mastery definitions (Topple, Nick, Vex, Slow, Sap, Push, Graze, Cleave) exposed via `GET /api/v1/rules/weapon-masteries`. |
| `monsters_2014.json` / `monsters_2024.json` | 2014 / 2024 | Official SRD monster statblocks (`srd_2014:<slug>`, `srd_2024:<slug>`) with ability scores, AC, HP, CR, traits, and structured attack/damage actions. |
| `items.json`, `skills.json`, `languages.json` | Both | Expanded SRD equipment & magic items catalog (`items.json`: 150+ items covering all Light/Medium/Heavy Armors incl. `min_str` & named magic armors *Elven Chain*/*Dwarven Plate*/*Dragon Scale Mail*, Shields `+1/+2/+3`/`Sentinel`/`Spellguard`, *Bracers of Defense*, *Robe of the Archmagi*, *Stone of Good Luck*, *Bracers of Archery*, *Headband of Intellect*, *Belts of Giant Strength*, *Ioun Stones*/Tomes, *Staff of Power*/*Magi*, *Wand of the War Mage*/*Rod of the Pact Keeper*/*Amulet of the Devout* `+1/+2/+3` & TCoE foci, Potions, Scrolls, Containers, and weighted PHB Adventuring Gear / ammunition stacks such as `Arrows (20)`, `Crossbow Bolts (20)`, `Quiver`, `Backpack`, `Rations (1 day)`, `Rope`, and `Healer's Kit`), skills with associated ability scores, and languages. |

---

## 📐 Invariants
1. **Never Hardcode Domain Data:** Code in `backend/` must never hardcode class names or spell lists; always query `RulesRepository`.
2. **Deterministic Integrity:** These files are immutable at runtime and cached in memory.
