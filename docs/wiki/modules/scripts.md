# 📜 Subsystem: Maintenance & Migration Scripts (`scripts/`)

## 📌 Overview
The `scripts/` directory houses CLI maintenance tools, database migrations, and diagnostic scripts.

---

## 🔑 Key Scripts

| Script | Purpose | Command |
| :--- | :--- | :--- |
| [`migrate_campaign_members.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/migrate_campaign_members.py) | Database migration: migrates embedded party records into the separate `campaign_members` collection and ensures all unique/query indexes are initialized defensively via `server.db_async.init_indexes()`. | `poetry run python scripts/migrate_campaign_members.py` |
| [`test_gemini_connection.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/test_gemini_connection.py) | Diagnostics: tests `GEMINI_API_KEY` validity and live network communication with Google GenAI. | `poetry run python scripts/test_gemini_connection.py` |
| [`fetch_and_seed_spells.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/fetch_and_seed_spells.py) | Seeder: pulls standard 5e SRD spells from external sources into static JSON. | `poetry run python scripts/fetch_and_seed_spells.py` |
| [`update_classes_json.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/update_classes_json.py) | Updates class matrices and subclass scaling definitions. | `poetry run python scripts/update_classes_json.py` |

---

## 📐 Invariants
1. **Root Import Resolution:** Scripts append the project root directory to `sys.path` so they can import from `server` and `backend`.
2. **Idempotence:** Scripts are safe to execute repeatedly without duplicating records or corrupting database state.
