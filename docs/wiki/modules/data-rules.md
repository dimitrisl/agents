# 📖 Subsystem: Static Rules Data (`data/rules/`)

## 📌 Overview
The `data/rules/` directory stores static JSON datasets for the **2014 5th Edition** and **2024 5.5e Revision**. This knowledge base powers all deterministic build validation, level progressions, and stat derivations.

---

## 🔑 Key Datasets

| File / Folder | Edition | Description |
| :--- | :--- | :--- |
| `classes/` | 2014 & 2024 | Class progression tables, spell slot schedules, hit die, and feature descriptions per level. |
| `subclasses/` & `subclasses.json` | 2014 & 2024 | Archetype feature lists, domain spells, and proficiencies. |
| `spells_2014.json` / `spells_2024.json` | 2014 / 2024 | Spell catalog with level, school, casting time, range, components, duration, and descriptions. |
| `feats_2014.json` / `feats_2024.json` | 2014 / 2024 | Origin and General feat definitions, prerequisite checks, and mechanical stat bonuses. |
| `backgrounds_2014.json` / `backgrounds_2024.json` | 2014 / 2024 | Backgrounds with starting proficiencies, equipment, and 2024 Origin Feats. |
| `races_2014.json` / `races_2024.json` | 2014 / 2024 | Species traits, speed, darkvision, and ancestral mechanics. |
| `weapons.json` & `weapon_masteries_2024.json` | Both / 2024 | Weapon properties, damage dice, and 2024 mastery triggers (Topple, Nick, Vex, Slow, Sap, Push, Graze, Cleave). |
| `items.json`, `skills.json`, `languages.json` | Both | Standard items, skills with associated ability scores, and languages. |

---

## 📐 Invariants
1. **Never Hardcode Domain Data:** Code in `backend/` must never hardcode class names or spell lists; always query `RulesRepository`.
2. **Deterministic Integrity:** These files are immutable at runtime and cached in memory.
