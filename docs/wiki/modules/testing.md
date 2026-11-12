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
├── test_campaign_roll_log.py         # Campaign sheet roll persistence, 2014/2024 parity, anti-spoof & DM redaction (#197)
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
2. **Deterministic Reproducibility:** Tests must pass cleanly and deterministically in any order (`poetry run pytest tests/ -v`).
3. **Tabletop & Online QA Simulation:** Multi-client integration is verified via `scripts/qa/simulate_session.py` across both In-Person Mobile Companion (`< 1024px`) and Online VTT Desktop (`>= 1024px`) modes (`poetry run python scripts/qa/simulate_session.py --mode both`).
