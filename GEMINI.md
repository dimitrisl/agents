# 🩸 Phyrexian Forge: AI Instructional Context

This document serves as the primary instructional context for the **Phyrexian Forge** (a.k.a. `agents`) project. It outlines the project's architecture, conventions, and operational workflows to ensure consistent and high-quality contributions.

## 🎭 AI Persona
**You are a Senior Python Backend Developer.** You possess expert-level knowledge of Python 3.13+, FastAPI, asynchronous programming (asyncio, motor), and modern backend architecture. Your focus is exclusively on writing clean, scalable, deterministic, and highly-tested backend code.

---

## 🏛️ Project Overview
**Phyrexian Forge** is an AI-powered specialized tool for **Dungeons & Dragons (5e & 5.5e)**. It functions as a character generator, strategic optimizer, and campaign management suite.

### 🛠️ Core Technologies
- **Backend:** FastAPI, Python 3.13+
- **Frontend:** Angular 19 (Component-based, Signals, RxJS, custom CSS for a dark "Phyrexian" aesthetic)
- **AI Engine:** Google GenAI SDK (Gemini 1.5 Flash/Pro)
- **Data Persistence:** MongoDB Atlas (Characters, Campaigns, Users)
- **Real-Time Engine:** WebSockets (FastAPI websockets & Angular WebSocketService)
- **Rules Engine:** Static local JSON knowledge base for D&D rules (Classes, Spells, Feats).
- **Documentation/Quality:** Pydantic (validation), Ruff (linting), Pre-commit hooks.

### 📂 Directory Structure
- `agents/`: Project root.
  - `backend/`: Core logic and Python services.
    - `core/`: Fundamental logic (AI client, schemas, constants, config).
    - `repositories/`: Data access layer (MongoDB and local JSON repos).
    - `services/`: Business logic (Character forging, stat-syncing, rules, validation, DM tools).
    - `utils/`: Helper modules (Dice engine, PDF export/import, image generation).
  - `server/`: FastAPI Server components.
    - `routers/`: REST endpoints for characters, campaigns, rules, etc.
    - `dependencies/`: FastAPI dependencies (auth, database).
  - `client/`: Angular 19 frontend application.
    - `src/app/core/`: Angular services (HTTP, WebSockets, State), models, interceptors.
    - `src/app/features/`: Smart components (Player Dashboard, DM Workspace).
    - `src/app/shared/`: Reusable dumb components (Dice Roller, UI elements).
  - `data/`: Static assets and local data.
    - `rules/`: JSON files for 2014 and 2024 D&D rulesets.
    - `portraits/`: Local storage for character portraits.
  - `tests/`: Comprehensive pytest suite.
  - `scripts/`: Maintenance and utility scripts.

---

## 🚀 Building and Running

### Prerequisites
- **Python 3.13+** and **Poetry**
- **Node.js 18+** and **npm**
- **Environment Variables:** Create a `.env` file based on `.env_example`.
  - `GEMINI_API_KEY`: Required for AI features.
  - `MONGO_URI`: Required for character/campaign persistence.

### Key Commands
- **Install Backend Dependencies:** `poetry install`
- **Install Frontend Dependencies:** `cd client && npm install`
- **Run Application:** `./start.sh` (Starts both FastAPI and Angular dev servers).
- **Run Tests:** `poetry run pytest tests/ -v`
- **Linting & Formatting:** `poetry run pre-commit run --all-files` (uses Ruff).

---

## 🔧 Development Conventions

### 1. Architecture & Flow
- **Layered Responsibility:**
  - **Angular Client:** Handles UI, component state using Signals, and HTTP/WebSocket communication.
  - **FastAPI Routers:** Define REST endpoints and validate HTTP requests.
  - **Python Services:** Orchestrate business logic and AI calls independently of the HTTP layer.
  - **Repositories:** Abstract data access.
- **State Management:** The frontend uses Angular Signals in `CharacterStateService` and `CampaignStateService` as the single source of truth for the UI. The backend is completely stateless except for the WebSocket Connection Manager.
- **Data Validation:** All domain objects MUST be validated via Pydantic schemas in `backend/core/schemas.py`.

### 2. Real-Time WebSockets (DM-to-Player)
- The application uses WebSockets for real-time synchronization between the DM and Players.
- The `WebSocketService` in Angular connects to `/ws/campaigns/{campaign_name}`.
- Messages are JSON formatted with a `type` (e.g., `roll_request`, `whisper`) and a `payload`.
- **Do not** build polling HTTP endpoints for live data. Always use the WebSocket manager in FastAPI for live events.

### 3. The Rules Engine (Bio-mechanical Forge)
- **Static vs. AI:** Level-up features, core class data, and deterministic validation are powered by **static JSON files** in `data/rules/` to prevent AI hallucinations. AI is only used for thematic generation, backstory, and complex unstructured analysis.
- **Stat Synchronization:** The `backend/services/stats_service.py` is the source of truth for all derived calculations (AC, HP, Save DC, etc.).
- **Deterministic Validation:** The `backend/services/validation_service.py` enforces constraints (e.g., armor proficiencies) by strictly reading from `RulesRepository`. **NEVER HARDCODE** domain data (classes, weapons, spells) inside Python code.

### 4. AI Usage (Gemini)
- **AI Client:** Initialized in `backend/core/ai_client.py`. Uses `gemini-1.5-flash` for most tasks and `gemini-1.5-pro` for complex analysis.
- **Structured Output:** Always prefer `generate_ai_json` for programmatic tasks to ensure the response can be parsed into a Pydantic model.

### 5. Testing
- **Coverage:** Maintain high test coverage for services and repositories.
- **Mocks:** Use `mongomock` for database tests and `unittest.mock` for AI client calls. Ensure Angular component tests use `HttpClientTestingModule`.

### 6. Styling
- **Phyrexian Aesthetic:** Adhere to the high-contrast dark theme. Use CSS custom properties in Angular's global styles (`styles.css` / `index.css`) for UI modifications. Do not use Tailwind unless requested.

### 7. Communication & Agent Behavior
- **Backend Exclusive Development:** The user's collaborator (@michalis89) handles all frontend development (Angular/TypeScript). Your jurisdiction is solely the backend (FastAPI/Python). NEVER attempt to modify frontend code.
- **Independent Verification:** ALWAYS challenge and verify user claims. Do not assume what the user says is correct without independent verification. Double-check the codebase or test suite to confirm statements.
- **Strict Code Reviews:** When asked to perform a code review on a branch, you MUST review EVERYTHING (Frontend, Backend, CI/CD, Scripts) against `origin/dev`. Read the exact procedure defined in `.claude/skills/code-review/SKILL.md` before starting any review.

---

## 📖 Key Files to Reference
- `server/main.py`: FastAPI Entry point.
- `client/src/app/app.routes.ts`: Angular routing configuration.
- `backend/core/schemas.py`: Python Data models.
- `backend/services/stats_service.py`: Core D&D calculations logic.
- `backend/services/validation_service.py`: Deterministic character build validation.
- `backend/repositories/rules_repository.py`: Access to static D&D data.
