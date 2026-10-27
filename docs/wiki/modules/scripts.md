# 📜 Subsystem: Maintenance, Migration & Lifecycle Scripts (`scripts/`, Root)

## 📌 Overview
The repository provides maintenance CLI tools in `scripts/` as well as cross-platform automated environment setup and startup orchestration scripts at the repository root.

---

## ⚡ Root Setup & Launch Automation Scripts

To ensure zero-friction onboarding across all operating systems, the root directory includes automated one-click scripts:

| Script | Platform | Key Operations |
| :--- | :--- | :--- |
| [`setup.sh`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/setup.sh) | Linux & macOS | 1. Checks Python 3.11+, Poetry, Node.js 18+, npm.<br>2. Generates `.env` with a secure random 64-char `JWT_SECRET_KEY` if missing.<br>3. Runs `poetry install` (backend dependencies).<br>4. Runs `npm install` in `client/` (frontend dependencies).<br>5. Creates `data/portraits` storage directory.<br>6. Verifies MongoDB connectivity on port 27017. |
| [`start.sh`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/start.sh) | Linux & macOS | 1. Verifies prerequisites (invoking `./setup.sh` automatically if dependencies are missing).<br>2. Spawns FastAPI backend (`poetry run uvicorn server.main:app --reload --port 8000`).<br>3. Spawns Angular frontend (`npm start` on port 4200).<br>4. Attaches a POSIX `trap` on `EXIT INT TERM` to gracefully terminate all child processes upon `Ctrl+C`. |
| [`setup.ps1`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/setup.ps1) | Windows (PowerShell) | Full automated environment validation, `.env` generation with crypto-random JWT secret, `poetry install`, `npm install`, and directory creation. |
| [`setup.bat`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/setup.bat) | Windows (Command Prompt) | Double-clickable batch wrapper around `setup.ps1` with PowerShell execution policy bypass. |
| [`start.ps1`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/start.ps1) | Windows (PowerShell) | Launches FastAPI and Angular in concurrent asynchronous jobs or separate console windows. |
| [`start.bat`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/start.bat) | Windows (Command Prompt) | Double-clickable batch wrapper launching backend and frontend in dedicated console windows. |

---

## 🔑 Key Maintenance & Migration Scripts (`scripts/`)

| Script | Purpose | Command |
| :--- | :--- | :--- |
| [`migrate_campaign_members.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/migrate_campaign_members.py) | Database migration: migrates embedded party records into the separate `campaign_members` collection and ensures all unique/query indexes are initialized defensively via `server.db_async.init_indexes()`. | `poetry run python scripts/migrate_campaign_members.py` |
| [`test_gemini_connection.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/test_gemini_connection.py) | Diagnostics: tests `GEMINI_API_KEY` validity and live network communication with Google GenAI. | `poetry run python scripts/test_gemini_connection.py` |
| [`fetch_and_seed_spells.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/fetch_and_seed_spells.py) | Seeder: pulls standard 5e SRD spells from external sources into static JSON. | `poetry run python scripts/fetch_and_seed_spells.py` |
| [`update_classes_json.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/scripts/update_classes_json.py) | Updates class matrices, spell progressions, and subclass scaling definitions in `data/rules/classes.json`. | `poetry run python scripts/update_classes_json.py` |

---

## 📐 Invariants
1. **Root Import Resolution:** Scripts in `scripts/` append the project root directory to `sys.path` so they can import from `server` and `backend`.
2. **Idempotence:** Scripts are safe to execute repeatedly without duplicating records or corrupting database state.
3. **Cross-Platform Compatibility:** Setup scripts must not assume hardcoded absolute user home directories (e.g. `/home/dimitrisl`). All paths are dynamically derived from script directory anchors.
