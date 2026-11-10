# 🖥️ Subsystem: Frontend Architecture, DM Workspace & Forge (`client/src/app/`)

## 📌 Overview
The Angular 19 frontend uses a standalone component architecture powered by **Angular Signals** for reactive state, pure TypeScript rule helpers in `core/rules/`, a custom dark "Phyrexian" UI component library in `shared/ui/`, and real-time WebSocket synchronization.

> [!NOTE]
> For detailed documentation on the **Player Sheet & Companion (`client/src/app/features/player/`)**, see **[Player Companion & Character Sheet](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/client-player.md)**.

---

## 🧠 Core State, Rules & Interceptors (`client/src/app/core/`)

### 1. Reactive State & Domain Services (`core/services/`)
| Service | Responsibility |
| :--- | :--- |
| [`character-state.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/character-state.service.ts) | Single source of truth for the hero vault (`characters`, `activeCharacter`, `dndEdition`, `vaultStatus`). Implements `ensureLoaded()` with `shareReplay(1)` to prevent duplicate fetches, `upsertCharacter()` to patch state in-place without full reloads, and persists the active hero ID in `localStorage` (`phyrexian_forge_active_char`). |
| [`websocket.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/websocket.service.ts) | Manages `/ws/campaigns/{name}` lifecycle, sends the initial `{type: "auth", token}` frame upon connection, and streams typed live events (`roll_request`, `roll_result`, `whisper`, `vtt_update`, `party_update`, `presence`). |
| [`settings.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/settings.service.ts) | Manages per-user AI model selection (Gemini free tier vs. Claude models) and user-supplied Anthropic API keys (`/api/v1/settings`). |
| [`admin.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/admin.service.ts) | Admin dashboard queries: paginated user list, role promotion/demotion, deletion, and system activity metrics. |
| [`dice.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/dice.service.ts) & [`roll-toast.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/roll-toast.service.ts) | Orchestrates dice expression evaluation, advantage/disadvantage modes, 3D dice triggers, critical hit animations, and save-for-half calculations in the dice tray. |
| [`spell-rules.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/spell-rules.service.ts) & [`class-combat.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/class-combat.service.ts) | Client-side lookups for spell scaling, concentration tracking, and class-specific combat riders (e.g. Sneak Attack, Rage, Divine Smite, Planar Warrior). |
| [`bestiary.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/bestiary.service.ts) | Queries `/api/v1/bestiary` for official SRD and custom monsters with source filtering (`include_official`, `include_mine`, `include_community` defaulting to `false`), cloning, creation, visibility toggling, and deletion. |
| [`character-import.service.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/services/character-import.service.ts) | Handles PDF character sheet upload (`/characters/import-pdf`) and JSON character import/export flows. |

### 2. Pure Client Rules Engine (`core/rules/`)
Pure, deterministic TypeScript functions tested in isolation that mirror `backend/services/stats_service.py`:
- [`ability.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/ability.ts), [`hit-points.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/hit-points.ts), [`skills.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/skills.ts): Ability modifiers, proficiency bonuses, HP bounds, and passive scores.
- [`spell-casting.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/spell-casting.ts) & [`spell-slots.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/spell-slots.ts): Upcast damage/healing dice scaling, spell attack crits, and slot consumption.
- [`flexible-casting.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/flexible-casting.ts) & [`metamagic.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/metamagic.ts): Sorcerer spell slot $\leftrightarrow$ Sorcery Point conversions and Metamagic cost/effect rules.
- [`weapon-calc.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/weapon-calc.ts) & [`weapon-masteries.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/weapon-masteries.ts): Weapon to-hit/damage calculation, conditional weapon effects (e.g., *vs undead*, *vs fiend*), and 2024 mastery triggers.
- [`rest.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/rest.ts), [`level-up.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/level-up.ts), [`recommendations.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/rules/recommendations.ts): Short/Long Rest recovery rules (including class resource pool resets), level-up progression helpers, and Background/Species mandatory grants (`getBackgroundSkills`, `getBackgroundOriginFeat`, `getRacialSkills`).

### 3. Interceptors & Guards (`core/interceptors/`, `core/guards/`)
- [`jwt.interceptor.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/interceptors/jwt.interceptor.ts): Attaches `Authorization: Bearer <token>` to outgoing API requests.
- [`error.interceptor.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/interceptors/error.interceptor.ts): Normalizes HTTP errors (`401`, `403`, `409 Conflict`, `429 Rate Limit`) into user-readable notifications.
- [`auth.guard.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/guards/auth.guard.ts) & [`admin.guard.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/core/guards/admin.guard.ts): Route guards enforcing authentication and admin privileges.

---

## 🐉 DM Workspace & Virtual Tabletop (`client/src/app/features/dm/`, `campaigns/vtt-grid/`)

- **Entry Component:** [`dm.component.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/dm.component.ts) — Organized into two top-level Master Modes (`⚔️ Live DM` for `initiative`, `vtt`, `party`, and `notes`; `🛠️ DM Preparation` for `homebrew` Bestiary & Homebrew, `generators`, `prep`, and `entities`) with a pinned Active Combat Strip across non-initiative Live DM tabs.
- **Panels (`features/dm/panels/`):**
  - [`party-panel`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/panels/party-panel): Live party HP, AC, passive scores, conditions, and online presence indicators.
  - [`initiative-panel`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/panels/initiative-panel): Turn tracker with automatic DEX tiebreaking, monster HP adjustments, condition toggles, and Unified Bestiary Quick-Add search with source filter chips (`Official`, `Mine`, `3rd-Party`).
  - [`entities-panel`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/panels/entities-panel) & [`prep-panel`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/panels/prep-panel): NPCs, villains, locations, monster statblocks, and AI session transcription/prep tools.
  - [`generators-panel`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/panels/generators-panel) & [`homebrew-panel`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/panels/homebrew-panel): AI encounter balancer (scaled to actual party levels), NPC & Riddle/Trap generators, Unified Bestiary explorer (with SRD cloning and private/public visibility toggles), and campaign homebrew forge.
- **Modals (`features/dm/modals/`):**
  - [`statblock-modal`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/modals/statblock-modal): Renders structured monster statblocks (ability scores with modifiers, traits, and actions) with 1-click `[ 🎲 +X to Hit ]` and `[ 💥 XdY+Z Damage ]` rolls wired through `DiceService` and `RollToastService`.
  - [`roll-request-modal`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/modals/roll-request-modal) & [`whisper-modal`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/modals/whisper-modal): Dispatches targeted or party-wide WebSocket roll prompts (including secret DM rolls) and private whispers.
  - [`paste-go-modal`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/modals/paste-go-modal): AI extraction of raw pasted text into structured `CampaignEntitySchema` records.
  - [`loot-distribute-modal`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/dm/modals/loot-distribute-modal): Assigns items/currency directly to party member sheets.
- **Virtual Tabletop (`features/campaigns/vtt-grid/`):**
  - Integrated into the `🗺️ Tactical VTT Map` tab inside `Live DM` mode; features multi-scene battlemap canvas, grid calibration, drag-and-drop token movement with canvas boundary clamping (`[0, (cols - 1) * cellSize]`), hidden DM tokens, and interactive Fog of War polygon/cell reveal synced over WebSockets.

---

## ⚒️ Character Forge & Other Features (`client/src/app/features/`)

- **Character Forge (`features/forge/`):**
  - [`forge.component.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/forge/forge.component.ts) orchestrates three flows: **AI Forge** (`ai-form`), **Manual Builder** (`manual-form` with deterministic 2014/2024 validation and automatic visual badges for Background/Species-granted skills and 2024 Origin Feats), and **PDF/JSON Import** (`character-import-panel`), previewed via `hero-preview`.
- **Settings (`features/settings/`):**
  - [`settings.component.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/settings/settings.component.ts): Allows any user to choose their preferred AI model (Gemini Flash/Pro or Claude Sonnet/Opus) and store/remove their personal Anthropic API key.
- **Admin (`features/admin/`):**
  - [`admin.component.ts`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/client/src/app/features/admin/admin.component.ts): Paginated user management, live online status, and role controls.
- **Rules & FAQ (`features/rules/`, `features/faq/`):**
  - Searchable 2014 vs. 2024 rules comparator, AI Rules Oracle, and interactive player/DM FAQ.

---

## 🎨 Shared Design System (`client/src/app/shared/`)

- **Phyrexian UI Primitives (`shared/ui/`):** Reusable standalone components (`forge-button`, `forge-card`, `forge-modal`, `forge-tabs`, `forge-switcher`, `forge-icon`, `forge-spinner`, `forge-skeleton`, `forge-markdown`, `forge-confirm`, `forge-stat-box`, `forge-badge`) styled via global CSS variables (`[data-edition="2014"|"2024"]`).
- **Interactive Shared Components (`shared/components/`):** `dice-roller`, `dice-3d`, `roll-toast`, `command-palette`, `navbar`, and `character-import-panel`.

---

## 📐 Frontend Invariants
1. **Prevent `409 Conflict` on Saves:** Always update `CharacterStateService` from the HTTP response of `PUT /characters/{id}` (`tap(updated => ...)`), which carries the incremented `version` from the backend. Never fire concurrent uncoordinated full-sheet `PUT` requests with a stale `version`.
2. **No Polling for Live Campaign State:** Never poll REST endpoints for party HP, initiative, whispers, or VTT state; subscribe to `WebSocketService` streams.
3. **Pure Rules in `core/rules/`:** Keep mechanical math in `client/src/app/core/rules/` free of Angular DI or DOM dependencies so it remains unit-testable and deterministic.
