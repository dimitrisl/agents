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
- **File:** [`client/src/app/features/player/character-overview-card/`](../../../client/src/app/features/player/character-overview-card)
- **Modal:** [`client/src/app/features/player/modals/portrait-modal/`](../../../client/src/app/features/player/modals/portrait-modal)
- **Three Ways to Set Character Portraits:**
  1. **AI Generation:** Generates prompt-based portraits via Google Gemini / pollinations.
  2. **Custom Image URL:** Direct external image URLs can be saved without blocking on third-party CORS preview failures.
  3. **Local File Upload:** Native `<label for="portrait-file-upload-input">` file upload directly streaming image payloads to `/api/v1/characters/{id}/portrait-upload` and storing securely in `data/portraits/<uuid>.png`.
- **Reactivity:** Updates immediately refresh the active character signal in `CharacterStateService`, resetting any prior error states on the overview card.

---

### 2. Multi-Level Progression Roadmap & Dynamic Build Advisor
- **Modal:** [`client/src/app/features/player/modals/level-up-modal/`](../../../client/src/app/features/player/modals/level-up-modal)
- **Component:** [`client/src/app/features/player/modals/build-advisor/`](../../../client/src/app/features/player/modals/build-advisor)
- **Dynamic Progression Roadmap:**
  - Provides an interactive **Level Switcher** (levels 1 through 20) allowing players to inspect upcoming class features, subclass milestones, ability score improvements (ASI), and spell slot unlocks.
  - Dynamically inspects the character's primary class (or multiclass array with robust fallback to `char_class` and `char_level`).
- **Contextual Build Suggestions:**
  - Advises on spell selections, feats, and playstyle options tailored strictly to the character's **current class, level, and existing spellbook/loadout**.
  - Prevents recommending spells or feats already known by the character.

---

### 3. Combat Engine & Weapon Breakdown
- **Component:** [`client/src/app/features/player/combat/`](../../../client/src/app/features/player/combat)
- **Incapacitation Guard (`DEF-CR-01`):**
  - Combat actions (Dodge, Dash, Disengage, Help) evaluate eligibility via [`isIncapacitated(char)`](../../../client/src/app/core/rules/hit-points.ts#L22-L35).
  - Pristine characters (`hp_current: undefined / None`) resolve to `hp_max > 0` and are not locked out of action buttons. Action execution is blocked only when `currentHp(char) <= 0` or under active incapacitating conditions (`incapacitated`, `unconscious`, `paralyzed`, `petrified`, `stunned`).
- **Weapon Damage Breakdown:**
  - Displays complete mathematical decomposition of attack and damage rolls:
    $$\text{Attack Bonus} = \text{Proficiency Bonus} + \text{Ability Mod} + \text{Magic Bonus} + \text{Fighting Style}$$
    $$\text{Damage Roll} = \text{Weapon Die} + \text{Ability Mod} + \text{Magic Bonus} + \text{Fighting Style Bonus}$$
- **Subclass Feature Dynamic Scaling:**
  - Displays dynamically scaled combat actions (e.g. Horizon Walker Ranger *Planar Warrior* automatically scaling from $1\text{d}8$ to $2\text{d}8$ at Level 11, *Distant Strike* at Level 11, and *Spectral Defense* at Level 15).

---

### 4. Interactive Skills, Reliable Talent, Rest Bonuses & Senses/Resistances Matrix
- **Component:** [`client/src/app/features/player/tabs/skills-panel/`](../../../client/src/app/features/player/tabs/skills-panel), [`character-overview-card/`](../../../client/src/app/features/player/character-overview-card), and [`modals/short-rest-modal/`](../../../client/src/app/features/player/modals/short-rest-modal)
- **Proficiency Multipliers & Reliable Talent:**
  - Players can toggle between Normal ($\times 0$), Proficient ($\times 1$), and Expertise ($\times 2$) directly on their sheet.
  - Rogues with *Reliable Talent* (L11 in 2014, L7 in 2024) render `10+ MIN` badges on proficient skills and pass `minD20 = 10` into `DiceService.rollD20()`.
- **Overview Senses, Resistances & Save Advantages; Short Rest Modals:**
  - [`CharacterOverviewCardComponent`](../../../client/src/app/features/player/character-overview-card/character-overview-card.component.ts) renders `char.senses`, `char.damage_resistances`, and `char.save_advantages` badges in the status strip.
  - [`ShortRestModalComponent`](../../../client/src/app/features/player/modals/short-rest-modal/short-rest-modal.component.ts) displays 2014 Bard *Song of Rest* dice banners, and `PlayerComponent.executeShortRest()` automatically rolls bonus Song of Rest healing and passes `char` for 2014 Sorcerer L20 *Sorcerous Restoration*.
- **Dynamic Passive Scores:**
  - Automatically recalculates Passive Perception ($10 + \text{WIS mod} + \text{Skill Bonus} + \text{Feat/Item Bonuses}$), Passive Insight, and Passive Investigation. Incorporates +5 flat bonus from the *Observant* feat.

---

## 📐 Invariants
1. **Unidirectional Reactive State:** All character state modifications dispatch through `CharacterStateService.upsertCharacter()`, preserving optimism and triggering instantaneous Angular Signal broadcasts.
2. **Deterministic Mechanics:** UI calculations for modifiers, proficiency bonuses, and DCs mirror the backend `stats_service.py` formulas precisely.
3. **Optimistic Modal Snapshot Rollback (`saveEditModal`):** Submitting character edits preserves a snapshot of the prior `activeCharacter`. If the backend persistence fails (e.g. `HTTP 409 Conflict` or network loss), state rolls back to the snapshot, the draft is re-bound, and the modal reopens, preventing data loss.
4. **Accessible Disclosure Controls:** Header drawer triggers and action buttons enforce ARIA disclosure semantics (`aria-expanded`, `aria-controls="mobile-hero-actions-drawer"`).
5. **Campaign Roll Log, Multi-Character Isolation & Sibling Alerts (`#197`+):** When enrolled in an active campaign, [`PlayerComponent`](../../../client/src/app/features/player/player.component.ts) keys its WebSocket connection effect (`wsConnectionKey`) by `${active_campaign}::${char_id || char_name}` (preventing save-induced socket churn while reconnecting cleanly across homonyms) and subscribes to `RollToastService.rollEvents$` to publish sheet rolls to `/campaigns/{name}/rolls` with `char_id` (respecting the player's `Public` vs `Whisper DM` toggle), while DM roll-request prompts and initiative (`skipBroadcast: true`) avoid duplicate broadcasts. Campaign inbox caching/filtering is keyed by `char_id` (`${campaignName}::${char_id || char_name}`), and live whispers/roll requests targeting another owned character enrolled in the same campaign raise an explicit `💬 WHISPER → <char_name>` / `🎲 ROLL REQUEST → <char_name>` alert without leaking into the active sheet's feed. [`QuickDiceDrawerComponent`](../../../client/src/app/features/player/quick-dice-drawer/quick-dice-drawer.component.ts) renders multi-die / mixed pools in 3D via `diceSides`.
6. **Redacted Combatant Status, Optimistic Skill Recompute, Level-Up Preview & DM Long-Rest Rehydration:** [`CombatPanelComponent`](../../../client/src/app/features/player/tabs/combat-panel/combat-panel.component.ts) evaluates `isCombatantDown()` and `isCombatantBloodied()` with explicit `typeof combatant.hp === 'number'` and `health_status` checks so player-redacted enemies (`hp: null`) never falsely render as `"Down"`, and computes `getToppleDc()` dynamically using `resolveWeaponStat()` so CHA/INT/WIS-based weapons scale properly. [`PlayerComponent`](../../../client/src/app/features/player/player.component.ts) clears the edited skill's stale cached `char.skills[name]` entry before calling `skillModifier()` in `toggleSkillProficiency`/`toggleSkillExpertise` and clears cached `skills`/`saving_throw_values` in `saveEditModal()`; [`LevelUpModalComponent`](../../../client/src/app/features/player/modals/level-up-modal/level-up-modal.component.ts) includes `perLevelHpBonus` (`hp_bonus_per_level`) in `rollHp()`, derives live `previewNewTotalHp` (including retroactive CON / feat per-level scaling plus `flat_hp_bonus` such as 2024 *Boon of Fortitude* `+40 HP` via `feat_metadata`) cleanly client-side, hides the half-feat stat dropdown when `has_stat_choice` is `false`, restricts stats to `stat_choice_options`, and excludes duplicate picks in `+1 to two Stats`. `PlayerComponent` also rehydrates full server `long_rest` fields, gates `<app-vtt-grid>` on active campaign enrollment, cleans up async subscriptions/object URLs via `DestroyRef`/`ngOnDestroy`, and clears `WebSocketService.vttState` on `disconnect()`.
7. **Multiclass Sheet Presentation, Pact Magic Indicators, Armor Penalty & L20 Max State:** [`CharacterOverviewCardComponent`](../../../client/src/app/features/player/character-overview-card/character-overview-card.component.ts), [`HeroSwitcherComponent`](../../../client/src/app/features/player/hero-switcher/hero-switcher.component.ts), and `PlayerComponent`'s mobile summary use `formatClassSummary()` and `formatSubclassSummary()` to render full multiclass breakdowns (e.g., `Paladin 5 / Sorcerer 3`) and full multi-die strings (`char.hit_dice`), while `openShortRestModal()` initializes `shortRestDieSize` from the primary/first class hit die option rather than descending `hit_dice` order. [`SpellsPanelComponent`](../../../client/src/app/features/player/tabs/spells-panel/spells-panel.component.ts) displays explicit Warlock `⚡ X/Y Pact (Lvl N · Short Rest)` summary badges and per-level slot badges via `pactPool` (capped at `details.pactSlotCount` when explicit `pact` keys are absent), [`CombatStatGridComponent`](../../../client/src/app/features/player/combat-stat-grid/combat-stat-grid.component.ts) shows `heavyArmorSpeedPenalty` (`-10ft STR` in `text-red`) beneath Speed, and [`ActionDockComponent`](../../../client/src/app/features/player/action-dock/action-dock.component.html) displays `★ Max Level (20)` when `canLevelUp` is `false`.
8. **Campaign Locks, Exhaustion 2014/2024 Parity & Athas Non-Destructive UI:** When enrolled in an active campaign (`active_campaign` non-empty), [`ActionDockComponent`](../../../client/src/app/features/player/action-dock/action-dock.component.html), `CombatPanelComponent`, `CharacterOverviewCardComponent`, and `EditSheetModalComponent` enforce read-only Exhaustion, read-only Level inputs, and `🔒` locks on Short Rest / Long Rest / Level Up unless DM-unlocked (`POST /characters/{id}/short-rest`, `/long-rest`, `/forge/level-up-apply`), while Solo characters retain full autonomy. [`AbilityScoreGridComponent`](../../../client/src/app/features/player/ability-score-grid/ability-score-grid.component.html) displays `abilityCheckModifier` (with 2024 Exhaustion & DM bonuses) and 2014 `DIS` indicators; [`HitPointsControlComponent`](../../../client/src/app/features/player/hit-points-control/hit-points-control.component.html) shows `💀 Deceased (Exhaustion 6)` and blocks Healing/Temp HP/Death Saves at un-waived L6; [`CombatPanelComponent`](../../../client/src/app/features/player/tabs/combat-panel/combat-panel.component.ts) dynamically reflects suppressed weapon bonuses (`weaponNotation()` & `damagePreview()`) without erasing underlying `magic_bonus` fields.
