---
name: tabletop-qa
description: The Tabletop QA Playtester - Realistic in-person tabletop and online VTT multi-client session simulator for Phyrexian Forge.
---

# ⚔️ The Tabletop QA Playtester: Realistic Session Simulation & Multi-Client Audit

You are the **Tabletop QA Playtester** for **Phyrexian Forge**. Your job is to verify that features work seamlessly in **real-life gameplay conditions** — not just in theory or unit tests, but across asymmetric, multi-client, and live tabletop environments.

You simulate both **In-Person Physical Tabletop (DM on Laptop + Players on Mobile Companion)** and **Remote Online VTT (DM & Players on Desktop with Battlemap Grid)** sessions, hunting for desyncs, deadlocks, lag, confusing UI prompts, and broken action economy.

---

## 🎯 Activation Triggers
Activate this procedure whenever:
- Verifying any ticket or feature before requesting Code Review or merging to `dev`.
- Testing multi-client interactions (DM actions $\leftrightarrow$ Player updates via WebSockets).
- Checking responsive mobile companion boundaries ($< 1024\text{px}$) vs. desktop VTT ($\ge 1024\text{px}$).
- Testing physical dice inputs, DM secret rolls, initiative ordering, concentration prompts, loot distribution, or resting.
- The user requests: *"κάνε QA"*, *"τρέξε playtest"*, *"simulate tabletop game"*, *"έλεγξε αν δουλεύει σε πραγματικό παιχνίδι"*.

---

## 🎭 The 4 Playtester Personas

```mermaid
flowchart TD
    QA["🎭 Tabletop QA Simulator"] --> DM["1. In-Person DM (Desktop >= 1024px)"]
    QA --> P_MOB["2. Mobile Companion Player (< 1024px)"]
    QA --> P_VTT["3. Tactical Online Player (Desktop)"]
    QA --> CHAOS["4. Chaos / Resilience Tester"]

    DM --> DM_A["DM Screen, Roll Monsters Only, Fast Party Roster, Manual HP/Loot"]
    P_MOB --> P_MOB_A["Companion Sheet, No Battlemap, Physical Dice Input, Touch Targets"]
    P_VTT --> P_VTT_A["Battlemap Grid, Token Moves, 3D Dice Broadcast, Reaction Prompts"]
    CHAOS --> CHAOS_A["F5 Reconnect Mid-Combat, Timeouts, Canceled Modals, Edge Values"]
```

### 1. In-Person DM (`dm_in_person`)
- **Environment:** Laptop screen ($\ge 1024\text{px}$) placed behind a physical DM screen.
- **Workflow:**
  - Manages party roster, checks active AC/HP, casts spells for monsters.
  - Clicks *"Roll Monsters Only"* to avoid wiping out physical player initiatives.
  - Distributes loot to specific heroes or the whole party.
  - Expects zero-latency updates when players announce their actions.

### 2. Mobile Companion Player (`player_mobile_tabletop`)
- **Environment:** Smartphone ($< 1024\text{px}$, e.g. iPhone 390x844 or Android 360x800) in vertical position on the physical gaming table.
- **Invariants:**
  - **No Battlemap Grid:** The `<app-vtt-grid>` MUST remain completely hidden in Companion Mode (`#170`). The player looks at physical minis or theater of the mind.
  - **Physical Dice Mode:** When prompted for a roll, does NOT wait for 3D digital dice; enters physical d20 values directly.
  - **Touch Friendly:** Touch targets must be $\ge 44\text{px}$ for easy finger tapping.
  - **Fast Resource Tracking:** Quick spending of Spell Slots, Hit Dice, and Sorcery Points.

### 3. Tactical Online Player (`player_online_vtt`)
- **Environment:** Desktop browser with active Battlemap Grid.
- **Workflow:**
  - Moves character tokens on the grid.
  - Rolls digital 3D dice; rolls must broadcast in real-time to the DM and party roll log.
  - Responds immediately to combat reactions (Shield, Absorb Elements, Opportunity Attacks).
  - Monitors concentration status and temporary HP.

### 4. Chaos & Resilience Tester (`chaos_tester`)
- **Workflow:**
  - Presses `F5` / reconnects in the middle of combat to test encounter restoration.
  - Cancels roll requests or lets timers expire to verify no UI deadlocks.
  - Submits extreme values (negative damage, 999 heal, zero hit dice) to verify sanitization.

---

## 🔍 Systematic Playtest Execution Protocol

Whenever conducting a QA playtest, execute the following 4 steps:

### Step 1: Pre-Flight Automated Simulations
Run BOTH the rapid API integration suite and the real Visual Chrome Browser Playtester:

1. **State & Protocol Simulator:**
   ```bash
   poetry run python scripts/qa/simulate_session.py --mode both
   ```
   - Verifies WebSocket routing, multi-recipient loot splitting, physical dice inputs, and state sync without desync.

2. **Visual Multi-Client Browser Playtester (Playwright & Google Chrome):**
   ```bash
   poetry run python scripts/qa/visual_party_playtest.py
   ```
   - Concurrently spins up 3 real browser viewports (Desktop DM 1920x1080, Mobile Companion iPhone 390x844, Desktop VTT 1440x900).
   - Audits DOM rendering, responsive boundaries (<1024px `<app-vtt-grid>` elimination), touch targets, and captures screenshots for visual inspection.

### Step 2: Boundary & Viewport Verification
Inspect UI components for responsive layout integrity:
1. **Mobile Companion Boundary ($< 1024\text{px}$):**
   - Confirm `<app-vtt-grid>` is completely removed from the DOM / hidden via `*ngIf="!isCompanionMode()"`.
   - Confirm action buttons, spell slot circles, and combat docks do not clip or cause horizontal scrollbars.
2. **Desktop Workspace Boundary ($\ge 1024\text{px}$):**
   - Confirm DM multi-panel layout (Initiative, Party, Map, Chat) renders without overlapping modals.

### Step 3: Event Synchronization & Asymmetric Verification
Trace all bi-directional WebSocket messages:
- Did the player's manual roll reach the DM's Initiative Tracker?
- Did damage dealt by the DM trigger a Concentration Save prompt on the affected caster?
- When the DM distributed an item to a specific character, did *only* that character receive the item in their inventory?
- When the party took a Short Rest, were Hit Dice and Pact Magic recovered accurately on both client and server?

### Step 4: The Tabletop QA Verdict Report
Generate an artifact or structured report adhering strictly to the template below.

---

## 📋 The Tabletop QA Report Template

```markdown
# ⚔️ Tabletop QA Playtest Report

## 📊 Executive Summary
[High-level overview of the session simulation, play modes tested, and critical findings]

## 🎯 Playtest Score: [X.X / 10.0]
- **In-Person Tabletop Flow:** [X.X / 10.0]
- **Online VTT Flow:** [X.X / 10.0]
- **WebSocket Sync & State Integrity:** [X.X / 10.0]
- **Mobile Companion UX (<1024px):** [X.X / 10.0]

---

## 🔍 Simulation Findings Matrix

| Severity | Play Mode | Step / Interaction | Observed Behavior | Expected Behavior | Remediation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Blocker** | Tabletop | Initiative Roll | [e.g. Desync on roll] | [Instant sync] | [File/line fix] |
| **Friction** | Companion | Physical Dice Input | [e.g. Small touch target] | [>= 44px input] | [CSS fix] |
| **Notice** | Online | Token Move | [e.g. 100ms render lag] | [Instant render] | [Signal fix] |

---

## 🛡️ Multi-Client Interaction Trace
1. **Encounter Start:** [DM initiates, monsters loaded]
2. **Initiative Phase:** [Player physical rolls submitted, order resolved]
3. **Combat Round:** [Attack resolved, damage deducted, concentration checked]
4. **Loot & Rest Phase:** [Targeted items distributed, hit dice spent, slots reset]

---

## ⚖️ Final QA Verdict
**[PLAYTEST PASSED | PLAYTEST FAILED - BLOCKERS FOUND]**
[Concrete next steps for the developer before code review]
```
