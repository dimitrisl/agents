---
name: python-fastapi-mongo
description: Repo-specific pitfalls, invariants, and testing patterns for the Phyrexian Forge Python 3.13 + FastAPI + Motor (MongoDB) backend. Load BEFORE writing or editing any code under server/, backend/, or tests/. Enforces 2014 vs 2024 D&D Edition parity, atomic MongoDB updates, RBAC guards, Split-Brain backend/frontend sync, and the mongomock TestClient test setup. Triggers on: adding/modifying FastAPI endpoints, Pydantic schemas, MongoDB queries, D&D backend services, or pytest suites.
---

# Python / FastAPI / Motor Backend — This Repo

LLMs know FastAPI and Python generically. This file covers the **repo-specific traps, invariants, and 2024 ruleset checks** that fail silently or cause regressions here.

---

## 1. Layering & "God File" Discipline

| Layer | Responsibility | Never put here |
|---|---|---|
| `server/routers/` | HTTP validation, RBAC (`Depends`), WS broadcast | D&D math, stat/HP formulas, hardcoded rules |
| `backend/services/` | Domain & D&D logic (`stats_service`, `forge_service`, `validation_service`) | FastAPI `Request`/`Depends`, raw JWT handling |
| `backend/repositories/` | Static `data/rules/` JSON lookup (`RulesRepository`) | Business mutations |
| `backend/core/schemas.py` | Pydantic v2 models (`CharacterSchema`, etc.) | DB queries |

**Watch the mega-files:** `campaign_router.py` (~86 KB), `stats_service.py` (~87 KB), `forge_service.py` (~72 KB), `character_router.py` (~40 KB), `schemas.py` (1,200+ lines). **Search inside them before implementing** — e.g. `POST /characters` must route derived stats through `stats_service` rather than inventing inline fallbacks.

---

## 2. 2014 vs 2024 Edition Parity — MANDATORY CHECK

Most existing code prioritizes 2014 (`EDITION_2014 = "2014 Edition"`), which is also `CharacterSchema.dnd_edition`'s default. **Every new endpoint, fix, or service change must work cleanly for `EDITION_2024 = "2024 Revision (5.5e)"` too.**

- **Edition detection:** Client payloads may carry `dnd_edition` or `ruleset_version`. Check `"2024" in str(edition or char_data.get("dnd_edition") or char_data.get("ruleset_version") or "")` — never assume exact string equality or omit the 2024 branch.
- **Core 2024 invariants not to break:** Subclasses unlock at Level 3 (not 1/2), Origin Feats (Alert, Tough, Savage Attacker) apply at Level 1, Paladin/Ranger half-casters round up from Level 1 (`ceil`), Weapon Masteries exist, Long Rest recovers **all** spent Hit Point Dice, `RulesRepository` normalizes `"2024"` vs `"2014"`, and bestiary queries handle `edition=2024`.
- **Split-Brain Check:** D&D calculations exist in **both** `backend/services/` (Python) and `client/src/app/core/rules/` (TypeScript). If you alter a rule or `CharacterSchema` field, verify the TypeScript mirror (`core/rules/` + `character.model.ts`) so frontend and backend don't drift apart.
- **Mandatory 2024 Test Rule:** Any test touching D&D rules, characters, rests, level-up, spells, or bestiary **must explicitly assert BOTH `"2014 Edition"` and `"2024 Revision (5.5e)"`**. Passing only with default `2014` fixtures is insufficient.

---

## 3. MongoDB (`motor`), Security & Real-Time Sync

- **Atomic updates over full-doc overwrites:** Never do `read -> mutate dict -> replace_one` on live shared documents (campaigns, party inventory/loot, VTT scenes, characters). Use atomic Mongo operators (`$set` on specific dotted paths, `$inc`, `$push`, `$pull`, `find_one_and_update`) and optimistic locking (`version`) where present.
- **Indexes live in `server/db_async.py`:** Add any new collection or query filter path to `INDEX_DEFINITIONS`.
- **Campaigns are keyed by `campaign_name`:** `campaign_members` stores `campaign_id == campaign_name`. Keep campaign/user cleanup cascades and path sanitizers (`backend/utils/`) intact.
- **RBAC dependencies (`server/dependencies/`):**
  - User auth: `Depends(get_current_user)`
  - Admin only: `Depends(require_admin)` (verifies DB `is_admin`, never JWT claim)
  - Campaign guards: `Depends(require_campaign_role("dm"))` or `Depends(require_campaign_member())`
- **WebSocket & Redaction order:** Persist to MongoDB **first**, then broadcast via `ConnectionManager`. Strip DM-only fields (hidden monster HP, secret rolls, hidden tokens) before returning responses or broadcasting to players.

---

## 4. Testing Pitfalls (`pytest`, no `conftest.py`)

There is **no shared `tests/conftest.py`**. Mocking `motor` via `mongomock` lives inline in router tests (reference: `tests/test_bestiary_api.py`).

1. **Avoid real Mongo lifespan:** `with TestClient(app):` triggers `lifespan` -> `connect_to_mongo()` in `server/main.py`! Either use `client = TestClient(app)` without `with` (like `test_integration.py`), or ensure all DB calls use overridden mocks cleanly without hanging.
2. **Write synchronous router tests (`def test_...`):** `pytest-asyncio` async router fixtures are not needed for `TestClient` and cause plugin warnings if misused.
3. **Seed `mongomock` synchronously:** Wrap `mongomock.MongoClient()` in `_AsyncDatabase`/`_AsyncCollection`, then seed data via `mock_db["coll"]._coll.insert_one(...)` inside sync tests.
4. **Always clean up overrides & rate limits:**
```python
@pytest.fixture
def client(mock_db):
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "dm"}
    yield TestClient(app)
    app.dependency_overrides = orig
    limiter.reset()
```

---

## 5. Verification Gates (Must Run Before Reporting Done)

```bash
export PATH=$HOME/.local/bin:$PATH
poetry run ruff check .
poetry run ruff format --check .
poetry run pytest tests/<relevant_tests>.py -v   # MUST cover both 2014 & 2024 paths
```

Before concluding any task, run the full suite (`poetry run pytest tests/ -v`) and perform the `doc-sync` audit (`docs/wiki/`). Never use `--no-verify`.
