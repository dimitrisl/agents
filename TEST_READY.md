# 🎯 Phyrexian Forge: E2E Test Readiness & Verification Report (TEST_READY.md)

**Document Version**: 1.1.0
**Date**: 2026-11-06
**Track**: E2E Testing Track (Independent Opaque-Box Suite)
**Author**: Test Writer (E2E Testing Track)
**Status**: TEST SUITE READY & VERIFIED (67 PASSED, 14 PENDING M3 IMPLEMENTATION)

---

## 1. Test Runner Commands

### 1.1 Complete E2E Suite Execution
```bash
# Execute entire E2E test suite (81 tests across 3 suites)
poetry run pytest tests/e2e/ -v
```

### 1.2 Targeted Suite Execution
```bash
# Suite 1: QA Audit Defects (F1, F2, F3, F7, F8, F9, F11, F12)
poetry run pytest tests/e2e/test_qa_audit_defects.py -v

# Suite 2: GitHub Issues (F4, F5, F6, F10, F13, F14, F15, F16)
poetry run pytest tests/e2e/test_github_issues.py -v

# Suite 3: Cross-Feature Combinations & Tabletop Workflows (Tier 3 & Tier 4)
poetry run pytest tests/e2e/test_tabletop_workflows.py -v
```

### 1.3 Full System & Dual-Mode Simulation
```bash
# Automated multi-client In-Person Tabletop + Online VTT simulator
poetry run python scripts/qa/simulate_session.py --mode both

# Pytest wrapper for tabletop simulator
poetry run pytest tests/test_qa_session_simulator.py -v
```

### 1.4 Frontend Type-Check & Build
```bash
cd client && npm run build
cd client && npm test
```

---

## 2. Feature Coverage & Execution Matrix

| Feature ID | Feature Name | Test File | Tests Written | Current Status | Milestone & Assignee |
|:---|:---|:---|:---:|:---:|:---|
| **F1** | Skills Panel Cleanup | `test_qa_audit_defects.py` | 5 | ✅ 5/5 PASSED | M1 (Worker M1) |
| **F2** | VTT Touch/Pointer Events | `test_qa_audit_defects.py` | 5 | ✅ 5/5 PASSED | M1 (Worker M1) |
| **F3** | `text-body-sm` Cleanup | `test_qa_audit_defects.py` | 5 | ✅ 5/5 PASSED | M1 (Worker M1) |
| **F4** | Mobile Companion Header Collapse | `test_github_issues.py` | 5 | ✅ 5/5 PASSED | M1 (Worker M1) |
| **F5** | Sticky Whisper Input Dock | `test_github_issues.py` | 4 | ✅ 4/4 PASSED | M1 (Worker M1) |
| **F6** | Navbar DM Role Status | `test_github_issues.py` | 4 | ✅ 4/4 PASSED | M1 (Worker M1) |
| **F7** | Multiclass Level-Up HP Die | `test_qa_audit_defects.py` | 4 | ✅ 4/4 PASSED | M2 (Worker M2) |
| **F8** | Dynamic Attunement Limits | `test_qa_audit_defects.py` | 5 | ✅ 5/5 PASSED | M2 (Worker M2) |
| **F9** | Bard & Champion Half-Proficiency | `test_qa_audit_defects.py` | 5 | ✅ 5/5 PASSED | M2 (Worker M2) |
| **F10** | Starting Armor/Shield Auto-Equip | `test_github_issues.py` | 5 | ✅ 5/5 PASSED | M2 (Worker M2) |
| **F11** | DM Roll Modal Manual Input | `test_qa_audit_defects.py` | 3 | ⏳ 0/3 (M3 planned) | M3 (Worker M3) |
| **F12** | Player Action Dock 5e Actions | `test_qa_audit_defects.py` | 5 | ⏳ 0/5 (M3 planned) | M3 (Worker M3) |
| **F13** | Initiative Tracker Suite | `test_github_issues.py` | 5 | ⏳ 3/5 PASSED (2 M3 planned) | M3 (Worker M3) |
| **F14** | Physical Dice Mode Enhancements | `test_github_issues.py` | 4 | ⏳ 1/4 PASSED (3 M3 planned) | M3 (Worker M3) |
| **F15** | Combat State Sync | `test_github_issues.py` | 3 | ⏳ 2/3 PASSED (1 M3 planned) | M3 (Worker M3) |
| **F16** | Encounter Reconnect Sync | `test_github_issues.py` | 2 | ✅ 2/2 PASSED | M3 (Worker M3) |
| **Tier 3** | Cross-Feature Interactions | `test_tabletop_workflows.py` | 10 | ✅ 10/10 PASSED | Multi-Milestone |
| **Tier 4** | Real-World Tabletop Workflows | `test_tabletop_workflows.py` | 2 | ✅ 2/2 PASSED | Multi-Milestone |
| **TOTAL** | **Comprehensive E2E Suite** | **All 3 Suites** | **81** | **67 PASSED, 14 PENDING** | **Full Scope** |

---

## 3. Milestone Completion Summary

### 3.1 Milestone 1 (Frontend UI & Mobile Ergonomics) — 100% VERIFIED
- **F1 (Skills Panel Cleanup)**: Orphan duplicate directory `client/src/app/features/player/skills-panel/` removed; 0 broken imports; all templates use `tabs/skills-panel/`.
- **F2 (VTT Touch/Pointer Events)**: Fog of War canvas responds to `pointerdown`, `pointermove`, `pointerup` with `touch-action: none;` and pointer capture.
- **F3 (`text-body-sm` Cleanup)**: Exactly 0 occurrences of undefined `text-body-sm` remaining across `client/src/app/`.
- **F4 (Mobile Companion Header Collapse #209)**: On <1024px viewport, hero header collapses into compact companion header with toggleable actions drawer.
- **F5 (Sticky Whisper Input #211)**: Whisper input dock is sticky above bottom thumb dock in mobile Table tab with `pb-52` bottom padding.
- **F6 (Navbar DM Role Status #212)**: Navbar user role badge accurately displays "Dungeon Master" for DM users / `/dm` routes.

### 3.2 Milestone 2 (D&D Rules & Stats Calculations) — 100% VERIFIED
- **F7 (Multiclass Level-Up HP Die)**: Manual HP roll derives hit die from target leveling class (`hitDieSidesFor(levelUpClass)`).
- **F8 (Dynamic Attunement Limits)**: Artificer level 10 -> 4 slots, level 14 -> 5 slots, level 18 -> 6 slots; other classes capped at 3 slots.
- **F9 (Bard & Champion Half-Proficiency)**: Jack of All Trades (Bard 2+) and Remarkable Athlete (Champion 7+) add `floor(PB/2)` to non-proficient skills and initiative; no double stacking.
- **F10 (Starting Armor/Shield Auto-Equip #210)**: Characters with starting equipment default highest AC proficient armor and shield to equipped for valid baseline AC (e.g. AC 18 for Paladin in Chain Mail + Shield).

### 3.3 Milestone 3 (Realtime Combat & Encounter Sync) — PENDING IMPLEMENTATION (14 Tests)
The remaining 14 test failures in `tests/e2e/` represent the precise scope assigned to Worker M3:
1. **F11 (DM Roll Modal Manual Input)** (3 tests):
   - Add `manual_roll: Optional[int] = None` to `RollRequestSchema` in `server/routers/campaign_router.py`.
   - Add manual physical dice input field in `client/src/app/features/dm/modals/roll-request-modal/roll-request-modal.component.html`.
2. **F12 (Player Action Dock 5e Actions)** (5 tests):
   - Add Dodge, Dash, Disengage, Help action buttons with tooltips in `client/src/app/features/player/action-dock/action-dock.component.html`.
   - Add corresponding `@Output()` emitters in `action-dock.component.ts`.
3. **F13 (Initiative Tracker - Roll Monsters Only)** (2 tests):
   - Add "🎲 Roll Monsters Only" button in `client/src/app/features/dm/panels/initiative-panel/initiative-panel.component.html`.
   - Implement `rollMonstersInitiative()` filtering `!combatant.is_player` in `dm.component.ts`.
4. **F14 (Physical Dice Mode Enhancements)** (3 tests):
   - Add manual d20 input in player roll request modal (`client/src/app/features/player/modals/roll-request-modal/`).
   - Add manual HP input in short rest modal (`client/src/app/features/player/modals/short-rest-modal/`).
   - Implement `keepConcentration()` preserving `char.concentrating_on` in `player.component.ts`.
5. **F15 (Combat State Sync)** (1 test):
   - In `server/routers/campaign_router.py` L408 (`update_party_member_state`): auto-reset `death_saves = {"successes": 0, "failures": 0}` when character HP increases from 0 to >0.

---

## 4. Verification Checklist

### QA Audit Defects
- [x] **F1: Skills Panel Cleanup**: Directory `client/src/app/features/player/skills-panel/` deleted with 0 broken imports.
- [x] **F2: VTT Touch/Pointer Events**: `vtt-grid.component.ts` canvas listens to `pointerdown`, `pointermove`, `pointerup` with `touch-action: none;`.
- [x] **F3: `text-body-sm` Cleanup**: 0 occurrences of undefined `text-body-sm` remain in `client/src/app/`.
- [x] **F4: Mobile Companion Header Collapse (#209)**: Header collapses on <1024px, reclaiming ~150px viewport space.
- [x] **F5: Sticky Whisper Input (#211)**: Whisper input is sticky above bottom dock with proper `pb-52` spacing.
- [x] **F6: Navbar DM Role Status (#212)**: Navbar displays "Dungeon Master" for DM users / `/dm` routes.
- [x] **F7: Multiclass Level-Up HP Die**: Hit die derived dynamically from leveling class (`hitDieSidesFor(levelUpClass)`).
- [x] **F8: Dynamic Attunement Limits**: Artificer levels 10, 14, 18 expand limits to 4, 5, 6; other classes capped at 3.
- [x] **F9: Bard & Champion Half-Proficiency**: Jack of All Trades (Bard 2+) & Remarkable Athlete (Champion 7+) add `PB // 2` to non-proficient checks & initiative without stacking.
- [x] **F10: Starting Armor/Shield Auto-Equip (#210)**: Paladin/Fighter starting armor and shield default to equipped for valid AC 18 baseline.
- [ ] **F11: DM Roll Modal Manual Input**: RollRequestSchema accepts `manual_roll` with auto-resolution.
- [ ] **F12: Player Action Dock 5e Actions**: Dodge, Dash, Disengage, Help buttons with tooltips in action dock.
- [ ] **F13: Initiative Tracker Suite (#194)**: Inline HP/AC editing verified; Roll Monsters Only pending M3.
- [ ] **F14: Physical Dice Mode (#195)**: Concentration Keep verified; manual d20 & short rest HP pending M3.
- [ ] **F15: Combat State Sync (#196)**: Concentration check on DM damage verified; death saves reset on heal pending M3.
- [x] **F16: Encounter Reconnect Sync (#198)**: `GET /encounter` fetched on player load and reconnect.

### Multi-Client Session Simulations
- [x] **Tabletop QA Simulator (Dual Mode)**: `scripts/qa/simulate_session.py --mode both` passed with 10.0/10.0 score.
- [x] **In-Person Multi-Client Tabletop Session**: 1 DM + 2 Mobile Companion Players session verified in pytest.
