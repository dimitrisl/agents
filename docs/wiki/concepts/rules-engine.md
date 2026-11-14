# ⚙️ Concept: Deterministic Rules Engine vs. AI (`docs/wiki/concepts/rules-engine.md`)

## 📌 Philosophy: The "Bio-Mechanical" Boundary
In **Phyrexian Forge**, game mechanics and AI are strictly decoupled:
* **The "Mechanical" Core (Deterministic):** All game rules, stat derivations, level-ups, combat modifiers, spell slot progressions, and legality checks are executed strictly through deterministic Python algorithms reading from static JSON datasets.
* **The "Biological" Shell (AI Generative):** Large Language Models (Gemini) are used solely for creative and unstructured tasks: character backstories, roleplay advice, session narrative summarization, and natural language query interpretation.

> [!IMPORTANT]
> **Zero Hallucination Guarantee:** Never allow an LLM to compute Armor Class, Hit Points, Saving Throw DCs, or determine legal spell slots.

---

## 🏛️ Calculation Authority: `stats_service.py`
[`backend/services/stats_service.py`](../../../backend/services/stats_service.py) is the sole authority for all derived character statistics:

1. **Armor Class (AC) Breakdown & Equipment Invariants:**
   - Computes base AC from equipped armor (Light: Base + Full DEX; Medium: Base + min(DEX, 2); Heavy: Base, no DEX).
   - **Shield Detection & Classification Invariant (`_is_shield_item`):**
     - Recognizes shields by checking catalog item type `shield` or canonical shield names (`"shield"`, `"wooden shield"`, `"steel shield"`, `"buckler"`, `"tower shield"`, or `r"^shield(\s*,\s*|\s+)\+[1-3]$"`).
     - Explicitly excludes wondrous accessories, rings, amulets, and cloaks (e.g. *Brooch of Shielding*) to prevent granting an illegitimate +2 shield bonus or disabling Monk/Barbarian Unarmored Defense.
     - Enforces the shield limit: maximum of **one shield** bonus (+2 AC) applies even if multiple shields are present in equipment.
   - **Starting Equipment Auto-Equip Invariant (`DEF-CR-02`):**
     - Starting equipment auto-equip executes **only** when `(is_initial_sync or has_unassigned_equipment)` (e.g., initial character creation where `base_stats` is unset or equipment has no `equipped` key).
     - **Player Intent Preservation:** When an existing character explicitly unequips an item (`equipped: False`), future saves, rests, or syncs **never** re-equip it automatically.
     - **Unarmored Defense Protection:** Monks (`char_class == "monk"`) are strictly excluded from armor and shield auto-equip to preserve their Unarmored Defense.
   - **Attunement Slots Fallback:** Defaults dynamically to 3 attunement slots, scaling to 4, 5, or 6 if Artificer subclass/class features (*Magic Item Adept*, *Magic Item Savant*, *Magic Item Master*) are present.
   - Enforces Defense Fighting Style requirement: requires wearing armor (does not apply unarmored).
   - Returns both the total AC integer and an `ACBreakdown` object detailing exact mathematical components for player popovers.

2. **Retroactive Constitution Adjustments:**
   - Adjustments to Constitution score (e.g. from level-ups, ASI, or stat overrides) immediately and retroactively update both `hp_max` and `hp_current` (+1 HP per level per +1 CON mod).

3. **Multiclass Spell Slots & Warlock Pact Magic:**
   - Multiclass caster levels follow the official multiclassing table (Full Casters 1:1, Half Casters 1:2, Third Casters 1:3), with `total_caster_level > 20` clamped to the level 20 table in `calculate_max_spell_slots`.
   - Warlock **Pact Magic** slots are tracked separately from standard spellcasting slots; Short Rest restores only Pact Magic slots, while regular slots require a Long Rest.

4. **Rest Recovery Invariants (`client/src/app/core/rules/rest.ts`):**
   - **Long Rest Hit Dice Recovery:**
     - **2024 Revision (PHB 2024, p. 370):** A character regains all lost HP and **all spent Hit Point Dice** (`hitDiceRecovered = totalHitDice`, `hitDiceUsed = 0`).
     - **2014 Edition (PHB 2014, p. 186):** A character regains up to half of their total Hit Dice floored (`Math.floor(totalHitDice / 2) || 1`).
     - **Edition Detection:** Evaluated via `is2024Edition(char)`, inspecting both `char.dnd_edition` and `char.ruleset_version`.
   - **Short Rest Resource Resets:**
     - 2024 rules recover +1 expended use on Short Rest for *Rage*, *Second Wind*, *Channel Divinity*, and *Wild Shape*.

5. **2024 Weapon Masteries:**
   - Limits weapon masteries known based on 2024 class tables (Paladin/Ranger/Rogue: 2; Barbarian: 2–4; Fighter: 3–6).
   - Calculates dynamic Topple Save DC: `8 + Proficiency Bonus + STR modifier`.

5. **Weapon Attack & Damage Mathematical Breakdown:**
   - **Attack Bonus:** `Proficiency Bonus (if proficient) + Ability Mod (STR or Finesse/Ranged DEX) + Magic Bonus (+1/+2/+3) + Fighting Style (Archery +2)`.
   - **Damage Roll Breakdown:** Returns an itemized structure including base weapon damage dice, ability score modifier, magical bonus, and conditional fighting style additions (e.g., Dueling +2 when wielding a melee weapon in one hand with no other weapons).

6. **Subclass Feature Resolution & Dynamic Scaling:**
   - Ingests class matrices from `data/rules/classes.json` and evaluates level gates dynamically.
   - **Horizon Walker Ranger:**
     - *Planar Warrior:* Base 1d8 force damage on weapon hit, automatically scaling to **2d8** at Ranger Level 11.
     - *Distant Strike (Level 11):* Resolves teleportation feature (up to 10 feet before each attack) and enables a 3rd attack against a distinct target.
     - *Spectral Defense (Level 15):* Reaction ability granting resistance against all damage dealt by the incoming attack.
   - Enforces backwards and forward compatibility between 2014 and 2024 rulesets.

7. **Interactive Skills, Expertise & Passive Scores:**
   - Skills support three distinct states: **Normal** (no bonus), **Proficient** (`+PB`), and **Expertise** (`+2 * PB`).
   - Toggling state recalculates the total skill check modifier dynamically: `AbilityMod + (PB * Multiplier)`.
   - Passive perception, passive insight, and passive investigation update automatically based on active proficiency/expertise:
     - Passive Perception: `10 + WIS mod + (PB if proficient, 2*PB if expertise, or half_prof if Jack of All Trades) + bonus_modifier`.
     - Automatically integrates flat feat bonuses (e.g. **+5** from the *Observant* feat) and custom `passive_perception_bonus`.
     - Passive Insight: `10 + WIS mod + (PB if proficient, 2*PB if expertise)`.
     - Passive Investigation: `10 + INT mod + (PB if proficient, 2*PB if expertise)`.

8. **2014 vs. 2024 Edition Split (Jack of All Trades & Remarkable Athlete):**
   - **Jack of All Trades (Bard Level 2):**
     - Both 2014 & 2024 RAW: Applies $\lfloor PB / 2 \rfloor$ to all ability checks lacking proficiency.
   - **Remarkable Athlete (Champion Fighter Level 7):**
     - **2014 RAW:** Applies $\lceil PB / 2 \rceil$ (half PB rounded up) to physical ability checks (Strength, Dexterity, Constitution) lacking proficiency. This applies to physical skill checks (Athletics, Acrobatics, Sleight of Hand, Stealth) and to Initiative (`DEX mod + ceil(PB / 2)`).
     - **2024 RAW:** Grants **Advantage** on Initiative checks and Athletics checks, with no numeric modifier bonus.

9. **Dynamic Advantage State Hygiene:**
   - Evaluates boolean advantage flags (`initiative_advantage`, `athletics_advantage`) dynamically on each sync cycle from subclass features (e.g. 2024 Remarkable Athlete, Barbarian *Feral Instinct*) and equipped magic items (e.g. *Weapon of Warning*).
   - Replaces sticky `setdefault(..., False)` logic to guarantee that changing subclasses or unequipping items cleanly clears active advantage flags.

10. **Combat Action Incapacitation Guard (`DEF-CR-01`):**
    - Checked via [`isIncapacitated(char)`](../../../client/src/app/core/rules/hit-points.ts#L22-L35).
    - Pristine characters (`hp_current: undefined / None`) resolve effective HP via `currentHp(char)` to `char.hp_max > 0` and are **not** incapacitated.
    - Characters are blocked from combat actions (Dodge, Dash, Disengage, Help) **only** when `currentHp(char) <= 0` or when affected by active incapacitating conditions (`incapacitated`, `unconscious`, `paralyzed`, `petrified`, `stunned`).

11. **Deterministic Mandatory Build Grants (`inject_mandatory_character_grants`):**
    - Executed in [`backend/services/rules_service.py`](../../../backend/services/rules_service.py) across `forge_character`, `forge_character_manual`, and `autofix_character_build`:
    - **Species / Racial Grants:** Automatically injects all static species traits from `races_{edition}.json` (`source: "Race"`), racial skill proficiencies (*Keen Senses* $\rightarrow$ `Perception`, 2024 *Naturally Stealthy* $\rightarrow$ `Stealth`, 2014 *Menacing* $\rightarrow$ `Intimidation`), and racial base speeds (`35 ft` for Goliath, `25 ft` for 2014 Dwarf/Halfling/Gnome).
    - **Background Grants:** Automatically merges mandatory background skill proficiencies (`backgrounds_{edition}.json`) into `skill_proficiencies`, injects background tool proficiencies and 2014 background features (`source: "Background"`), and injects the 2024 Background Origin Feat (plus the 2nd Origin Feat for 2024 Humans via *Versatile*) into `features_traits` and `advancements`.
    - **Class & Starting Loadout Fallback:** Deterministically injects all class and active subclass features up to `char_level` and populates canonical starting weapons, armor/equipment, languages, and spellcaster cantrips/prepared spells whenever omitted during character forging.

12. **Exhaustion (`exhaustion_level`) & Epic Boon ASI Cap:**
    - `exhaustion_level` is clamped to `[0, 6]` in [`backend/services/stats_service.py`](../../../backend/services/stats_service.py) (`sync_character_stats`): applies a `-5 * exhaustion_level` ft speed penalty and `exhaustion_penalty = 2 * exhaustion_level` to skills, saving throws, weapon attack bonuses, `spell_save_dc`, and `spell_attack_bonus`.
    - **Level 19+ Epic Boon Cap:** [`POST /forge/level-up-apply`](../../../server/routers/forge_router.py) enforces `stat_cap = 30` when `char_level >= 19` and `"2024" in dnd_edition`, else `20`.

---

## 🛡️ Deterministic Validation: `validation_service.py`
[`backend/services/validation_service.py`](../../../backend/services/validation_service.py) enforces build legality:
* **Armor & Weapon Proficiencies:** Validates that equipped items match character proficiencies fetched from `RulesRepository`.
* **Subclass Level Locks:** Enforces that 2024 classes (Cleric, Fighter, etc.) select subclasses at **Level 3**, whereas 2014 classes follow their respective 1st/2nd/3rd level rules.
* **Point Buy & Array Boundaries:** Enforces base stat constraints (8 to 15 before racial/background bonuses).
