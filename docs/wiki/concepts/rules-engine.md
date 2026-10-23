# ⚙️ Concept: Deterministic Rules Engine vs. AI (`docs/wiki/concepts/rules-engine.md`)

## 📌 Philosophy: The "Bio-Mechanical" Boundary
In **Phyrexian Forge**, game mechanics and AI are strictly decoupled:
* **The "Mechanical" Core (Deterministic):** All game rules, stat derivations, level-ups, combat modifiers, spell slot progressions, and legality checks are executed strictly through deterministic Python algorithms reading from static JSON datasets.
* **The "Biological" Shell (AI Generative):** Large Language Models (Gemini) are used solely for creative and unstructured tasks: character backstories, roleplay advice, session narrative summarization, and natural language query interpretation.

> [!IMPORTANT]
> **Zero Hallucination Guarantee:** Never allow an LLM to compute Armor Class, Hit Points, Saving Throw DCs, or determine legal spell slots.

---

## 🏛️ Calculation Authority: `stats_service.py`
[`backend/services/stats_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/stats_service.py) is the sole authority for all derived character statistics:

1. **Armor Class (AC) Breakdown:**
   - Computes base AC from equipped armor (Light: Base + Full DEX; Medium: Base + min(DEX, 2); Heavy: Base, no DEX).
   - Enforces the shield limit: maximum of **one shield** bonus (+2 AC) applies even if multiple shields are present in equipment.
   - Enforces Defense Fighting Style requirement: requires wearing armor (does not apply unarmored).
   - Returns both the total AC integer and an `ACBreakdown` object detailing exact mathematical components for player popovers.

2. **Retroactive Constitution Adjustments:**
   - Adjustments to Constitution score (e.g. from level-ups, ASI, or stat overrides) immediately and retroactively update both `hp_max` and `hp_current` (+1 HP per level per +1 CON mod).

3. **Multiclass Spell Slots & Warlock Pact Magic:**
   - Multiclass caster levels follow the official multiclassing table (Full Casters 1:1, Half Casters 1:2, Third Casters 1:3).
   - Warlock **Pact Magic** slots are tracked separately from standard spellcasting slots; Short Rest restores only Pact Magic slots, while regular slots require a Long Rest.

4. **2024 Weapon Masteries:**
   - Limits weapon masteries known based on 2024 class tables (Paladin/Ranger/Rogue: 2; Barbarian: 2–4; Fighter: 3–6).
   - Calculates dynamic Topple Save DC: `8 + Proficiency Bonus + STR modifier`.

---

## 🛡️ Deterministic Validation: `validation_service.py`
[`backend/services/validation_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/validation_service.py) enforces build legality:
* **Armor & Weapon Proficiencies:** Validates that equipped items match character proficiencies fetched from `RulesRepository`.
* **Subclass Level Locks:** Enforces that 2024 classes (Cleric, Fighter, etc.) select subclasses at **Level 3**, whereas 2014 classes follow their respective 1st/2nd/3rd level rules.
* **Point Buy & Array Boundaries:** Enforces base stat constraints (8 to 15 before racial/background bonuses).
