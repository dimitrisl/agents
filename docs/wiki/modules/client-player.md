# 📱 Subsystem: Player Companion & Character Sheet (`client/src/app/features/player/`)

## 📌 Overview
The Player Companion module provides the responsive, real-time character sheet interface for players. It is built in Angular 19 leveraging Angular Signals (`CharacterStateService`), reactive UI components, and real-time synchronization with the backend via REST and WebSockets.

---

## 🔑 Key Features & Architecture

```
[ CharacterOverviewCard ] ─── (Avatar, HP, AC, Level, Inspiration)
        │
        ├─► [ PortraitModal ] ─────► AI Forge Prompt | Direct Image URL | Local File Upload
        ├─► [ LevelUpModal ] ──────► Multi-Level Progression Roadmap (1-20) & Build Advisor
        ├─► [ CombatComponent ] ───► Weapon Attacks & Detailed Damage Breakdown
        ├─► [ SkillsPanel ] ───────► Normal / Proficient / Expertise Matrix & Passives
        └─► [ SpellsTab ] ─────────► Prepared Spells, Cast Triggers & Slot Tracking
```

### 1. Character Overview & Portrait System
- **File:** [`client/src/app/features/player/character-overview-card/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/player/character-overview-card/)
- **Modal:** [`client/src/app/features/player/modals/portrait-modal/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/player/modals/portrait-modal/)
- **Three Ways to Set Character Portraits:**
  1. **AI Generation:** Generates prompt-based portraits via Google Gemini / pollinations.
  2. **Custom Image URL:** Direct external image URLs can be saved without blocking on third-party CORS preview failures.
  3. **Local File Upload:** Native `<label for="portrait-file-upload-input">` file upload directly streaming image payloads to `/api/v1/characters/{id}/portrait-upload` and storing securely in `data/portraits/<uuid>.png`.
- **Reactivity:** Updates immediately refresh the active character signal in `CharacterStateService`, resetting any prior error states on the overview card.

---

### 2. Multi-Level Progression Roadmap & Dynamic Build Advisor
- **Modal:** [`client/src/app/features/player/modals/level-up-modal/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/player/modals/level-up-modal/)
- **Component:** [`client/src/app/features/player/modals/build-advisor/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/player/modals/build-advisor/)
- **Dynamic Progression Roadmap:**
  - Provides an interactive **Level Switcher** (levels 1 through 20) allowing players to inspect upcoming class features, subclass milestones, ability score improvements (ASI), and spell slot unlocks.
  - Dynamically inspects the character's primary class (or multiclass array with robust fallback to `char_class` and `char_level`).
- **Contextual Build Suggestions:**
  - Advises on spell selections, feats, and playstyle options tailored strictly to the character's **current class, level, and existing spellbook/loadout**.
  - Prevents recommending spells or feats already known by the character.

---

### 3. Combat Engine & Weapon Breakdown
- **Component:** [`client/src/app/features/player/combat/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/player/combat/)
- **Weapon Damage Breakdown:**
  - Displays complete mathematical decomposition of attack and damage rolls:
    $$\text{Attack Bonus} = \text{Proficiency Bonus} + \text{Ability Mod} + \text{Magic Bonus} + \text{Fighting Style}$$
    $$\text{Damage Roll} = \text{Weapon Die} + \text{Ability Mod} + \text{Magic Bonus} + \text{Fighting Style Bonus}$$
- **Subclass Feature Dynamic Scaling:**
  - Displays dynamically scaled combat actions (e.g. Horizon Walker Ranger *Planar Warrior* automatically scaling from $1\text{d}8$ to $2\text{d}8$ at Level 11, *Distant Strike* at Level 11, and *Spectral Defense* at Level 15).

---

### 4. Interactive Skills & Expertise Matrix
- **Component:** [`client/src/app/features/player/skills-panel/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/player/skills-panel/)
- **Proficiency Multipliers:**
  - Players can toggle between Normal ($\times 0$), Proficient ($\times 1$), and Expertise ($\times 2$) directly on their sheet.
- **Dynamic Passive Scores:**
  - Automatically recalculates Passive Perception ($10 + \text{WIS mod} + \text{Skill Bonus}$), Passive Insight, and Passive Investigation.

---

## 📐 Invariants
1. **Unidirectional Reactive State:** All character state modifications dispatch through `CharacterStateService.upsertCharacter()`, preserving optimism and triggering instantaneous Angular Signal broadcasts.
2. **Deterministic Mechanics:** UI calculations for modifiers, proficiency bonuses, and DCs mirror the backend `stats_service.py` formulas precisely.
