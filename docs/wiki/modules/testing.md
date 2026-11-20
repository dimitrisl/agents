# 🧪 Subsystem: Testing Architecture (`tests/` & `server/tests/`)

## 📌 Overview
The automated test suite combines unit tests, service tests, integration tests with `mongomock`, and route API tests using FastAPI `TestClient`.

---

## 🏗️ Structure & Test Categories

```
tests/
├── fixtures/                         # Mock JSON payloads for rules, campaigns, and characters
├── test_unique_indexes_and_races.py # Unique index collisions, race conditions (register, campaign, join)
├── test_integration.py               # Full-flow integration, character takeover protection, party isolation
├── test_vtt_security.py              # Token security, atomic updates, and hidden token redaction
├── test_websocket_channel.py         # Real-time WebSocket connection manager and channel isolation
├── test_campaign_roll_log.py         # Campaign sheet roll persistence, 2014/2024 parity, multi-character & homonym isolation (#197)
├── test_loot_distribution.py         # Per-item loot recipient_id routing, currency split, and item_recipient_id compatibility (#222)
├── test_board_consolidation_fixes.py # Board consolidation & QA regressions across 2014/2024 exhaustion/long-rest rules, campaign security guards, VTT/encounter/journey redaction, mixed-case invite codes, and asset URL encoding
├── test_dm_exhaustion_locks_modifiers.py # 2014 & 2024 Exhaustion L0-6 & L6 death, bypass waiver, non-destructive Athas magic suppression, signed DM modifiers, campaign-only locks & 1-shot unlocks vs Solo freedom, _roll_in_secret Disadvantage/cancellation, and campaign detach/delete cleanup
├── test_deterministic_character_math.py # Multi-class (Fighter, Wizard, Rogue, Draconic Sorcerer) Level 3 & 8 2014/2024 deterministic math, Forge/Level-Up anti-hallucination, PDF bounds, and SRD encounter hydration/fallback
├── test_code_review_fixes.py         # Full-stack security & correctness regression suite (XFF right-to-left proxy IP, magic-byte image validation, production JWT enforcement, VTT fog bounds, rules parity, level-up server authority, safe script queries)
├── test_2014_qa_fixes.py             # 2014 Edition QA regression & 2024 parity suite (Paladin/Monk/Rogue/Artificer saves, Resilient half-feat, weapon profs, feat prereqs, all 13 subclass progressions & domain/innate spells, 2014 choice pickers + Agonizing Blast, Sorcerous Restoration & racial resource pools, senses/resistances/save advantages)
├── test_mechanics*.py                # AC math, spell slots, saving throws, and conditions
├── test_dnd_rules_audit_fixes*.py    # 2014 vs. 2024 rule audit verifications
├── test_audit_critical_p0_p1_fixes.py # Regression suite for 17 code review & security audit fixes
├── test_schemas.py                   # Pydantic boundary validation
└── ...                               # Unit tests for dice, PDF, forge, sessions, and encounters

server/tests/
├── test_api.py                       # REST API route integration tests
└── test_lore.py                      # Rules query and lore prompt tests

client/src/
└── app/**/*.spec.ts                  # Angular 19 / Jest frontend unit & component tests
```

---

## 📐 Invariants & Mocks
1. **No External Network Calls:** Tests must never make live network calls to Gemini or external databases. Use `unittest.mock.patch` for AI client calls and `mongomock` for MongoDB operations.
2. **Deterministic Parallel Reproducibility:** Tests execute in parallel across CPU cores via `pytest-xdist` (`addopts = "-n auto --dist worksteal"` in [`pyproject.toml`](../../../pyproject.toml)). Every test must isolate shared state (such as `CONFIG_FILE` via `tmp_path` + `monkeypatch`) and pass deterministically (`poetry run pytest tests/ -v`, or `-n 0` for single-process debugging).
3. **Tabletop & Online QA Simulation:** Multi-client integration is verified via `scripts/qa/simulate_session.py` across both In-Person Mobile Companion (`< 1024px`) and Online VTT Desktop (`>= 1024px`) modes (`poetry run python scripts/qa/simulate_session.py --mode both`).
