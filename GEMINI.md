# 🩸 Phyrexian Forge: AI Instructional Context

This document serves as the primary instructional context for the **Phyrexian Forge** (a.k.a. `agents`) project. It outlines the project's architecture, conventions, and operational workflows to ensure consistent and high-quality contributions.

---

## 🏛️ Project Overview
**Phyrexian Forge** is an AI-powered specialized tool for **Dungeons & Dragons (5e & 5.5e)**. It functions as a character generator, strategic optimizer, and campaign management suite.

### 🛠️ Core Technologies
- **Backend:** Python 3.13+
- **Frontend:** Streamlit (with extensive custom CSS for a dark "Phyrexian" aesthetic).
- **AI Engine:** Google GenAI SDK (Gemini 1.5 Flash/Pro).
- **Data Persistence:** MongoDB Atlas (Characters, Campaigns, Users).
- **Rules Engine:** Static local JSON knowledge base for D&D rules (Classes, Spells, Feats).
- **Documentation/Quality:** Pydantic (validation), Ruff (linting), Pre-commit hooks.

### 📂 Directory Structure
- `agents/`: Project root.
  - `backend/`: Core logic and services.
    - `core/`: Fundamental logic (AI client, state management, schemas, constants, config).
    - `repositories/`: Data access layer (MongoDB and local JSON repos).
    - `services/`: Business logic (Character forging, mechanics/stat-syncing, rules, DM tools).
    - `utils/`: Helper modules (Dice engine, PDF export/import, image generation, UI helpers).
  - `data/`: Static assets and local data.
    - `rules/`: JSON files for 2014 and 2024 D&D rulesets.
    - `portraits/`: Local storage for character portraits.
  - `views/`: Streamlit view components (Player Dashboard, DM Workspace, Library, Settings).
  - `tests/`: Comprehensive pytest suite.
  - `scripts/`: Maintenance and utility scripts.

---

## 🚀 Building and Running

### Prerequisites
- **Python 3.13+**
- **Poetry** (dependency management)
- **Environment Variables:** Create a `.env` file based on `.env_example`.
  - `GEMINI_API_KEY`: Required for AI features.
  - `MONGO_URI`: Required for character/campaign persistence.

### Key Commands
- **Install Dependencies:** `poetry install`
- **Run Application:** `poetry run streamlit run main.py`
- **Run Tests:** `poetry run pytest tests/ -v`
- **Linting & Formatting:** `poetry run pre-commit run --all-files` (uses Ruff).

---

## 🔧 Development Conventions

### 1. Architecture & Flow
- **Layered Responsibility:**
  - **Views:** Handle Streamlit UI components and user interaction.
  - **Services:** Orchestrate business logic and AI calls.
  - **Repositories:** Abstract data access.
  - **Core:** Contains shared schemas (Pydantic models) and state management.
- **State Management:** Use `backend/core/state_manager.py` to initialize and manage `st.session_state`. Never modify session state directly for character data; use `get_character_dict` and `update_session_from_dict`.
- **Data Validation:** All domain objects (Characters, Weapons, etc.) MUST be validated via Pydantic schemas in `backend/core/schemas.py`.

### 2. The Rules Engine (Bio-mechanical Forge)
- **Static vs. AI:** Level-up features and core class data are powered by **static JSON files** in `data/rules/` to prevent AI hallucinations. AI is used for thematic generation, backstory, and complex analysis.
- **Stat Synchronization:** The `backend/services/mechanics_service.py` is the source of truth for all derived calculations (AC, HP, Save DC, etc.).
- **Manual Overrides:** The `Weapon` and `Equipment` models support an `is_custom` flag. If `True`, the mechanics service respects manual user edits over automated calculations.

### 3. AI Usage (Gemini)
- **AI Client:** Initialized in `backend/core/ai_client.py`. Uses `gemini-1.5-flash` for most tasks and `gemini-1.5-pro` for complex analysis or long-context tasks (like PDF session prep).
- **Structured Output:** Always prefer `generate_ai_json` for programmatic tasks to ensure the response can be parsed into a Pydantic model.

### 4. Testing
- **Coverage:** Maintain high test coverage for services and repositories.
- **Mocks:** Use `mongomock` for database tests and `unittest.mock` for AI client calls.

### 5. Styling
- **Phyrexian Aesthetic:** Adhere to the high-contrast dark theme. Use `backend/utils/ui_utils.py` and `inject_custom_css` for UI modifications.

---

## 📖 Key Files to Reference
- `main.py`: Entry point and routing.
- `backend/core/schemas.py`: Data models.
- `backend/core/state_manager.py`: Session state lifecycle.
- `backend/services/mechanics_service.py`: Core D&D logic.
- `backend/services/forge_service.py`: AI generation logic.
- `backend/repositories/rules_repository.py`: Access to static D&D data.
