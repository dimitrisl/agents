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
├── test_mechanics*.py                # AC math, spell slots, saving throws, and conditions
├── test_dnd_rules_audit_fixes*.py    # 2014 vs. 2024 rule audit verifications
├── test_schemas.py                   # Pydantic boundary validation
└── ...                               # Unit tests for dice, PDF, forge, sessions, and encounters

server/tests/
├── test_api.py                       # REST API route integration tests
└── test_lore.py                      # Rules query and lore prompt tests
```

---

## 📐 Invariants & Mocks
1. **No External Network Calls:** Tests must never make live network calls to Gemini or external databases. Use `unittest.mock.patch` for AI client calls and `mongomock` for MongoDB operations.
2. **Deterministic Reproducibility:** Tests must pass cleanly and deterministically in any order (`poetry run pytest`).
