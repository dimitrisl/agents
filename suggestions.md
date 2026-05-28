# 🩸 Phyrexian Forge: Project Suggestions

Following a comprehensive review of the **Phyrexian Forge** codebase, here are prioritized suggestions for architectural improvements, new features, and quality enhancements.

---

## 🛠️ 1. Architectural Improvements

### ✅ DONE — PDF Field Abstraction
The mapping of character data to PDF form fields in `backend/pdf_exporter.py` was hardcoded.
- **Status:** Implemented. Mappings now live in `data/pdf_mappings/` as JSON files. Adding a new sheet template requires no Python changes.

### Caching Strategy
Frequent Streamlit reruns can lead to unnecessary API calls and latency.
- **Suggestion:** Implement `@st.cache_data` in `backend/ai_client.py` for methods like `query_rules` or `get_flash_model`.
- **Benefit:** Reduces API costs and improves UI responsiveness.

### ✅ DONE — Centralized Prompt Management
Prompts were previously embedded within `ai_client.py`.
- **Status:** Implemented. All AI prompts are consolidated in `backend/core/prompts.py`.

---

## 🏹 2. Enhanced Feature Set

### ✅ DONE — Integrated Portrait Generation & Management
- **Status:** Implemented.
  - AI-generated portraits via Pollinations.ai at character forge time and on-demand from the player dashboard.
  - **New:** Players can change their portrait from the dashboard in Edit Mode (URL or file upload → syncs to MongoDB).
  - **New:** DMs can change any combatant's portrait mid-combat via the 🖼️ Portrait popover in the Initiative Tracker (URL or file upload → syncs back to party characters and NPC records).
  - Local file paths are base64-encoded for correct rendering inside HTML combat cards.

### ✅ DONE — Interactive Initiative Tracker
- **Status:** Implemented. Full initiative tracker in the DM Workspace covering HP bars, status conditions, concentration tracking, turn order management, statblock popovers, quick roll popover, and portrait editing.

### ✅ DONE — Rule Comparison Tool
- **Status:** Implemented. The Rules Library "Rule Comparison" tab uses `RULE_COMPARISON_PROMPT` to return a structured 2014 vs 2024 comparison for any topic.

### Player / DM Authentication (OAuth2)
- **Suggestion:** Implement a Login system (via Discord or Gmail OAuth2) and add an `owner_id` to characters and campaigns in MongoDB.
- **Benefit:** Allows players to securely manage their own roster of characters and DMs to isolate their campaigns from others.

---

## 🧪 3. Quality Assurance & DX

### ✅ DONE — Automated Testing Suite
- **Status:** Implemented. 141 tests across 16 test files (`tests/`) covering mechanics, dice, schemas, state manager, PDF export/import, repositories, storage facade, rule comparison, dm_service, and image_utils. All run automatically via pre-commit hooks.

### ✅ DONE — Robust Schema Validation (Pydantic)
- **Status:** Implemented. `backend/core/schemas.py` defines strict Pydantic models for characters, weapons, equipment, and spells. All AI-generated and user-edited data is validated before storage.

---

## 🎨 4. UI/UX Polishing

### Themed Markdown Rendering
- **Suggestion:** Use custom CSS to style the AI-generated markdown (Oracle answers, Playstyle guides) to match the dark, bio-mechanical aesthetic.
- **Benefit:** Creates a more immersive "Phyrexian" user experience.

### Character Export Preview
- **Suggestion:** Display a data summary or "preview card" in Streamlit before the user downloads the PDF.
- **Benefit:** Allows users to verify AI Forge results before committing to a download.

### Table-Ready UX Polish
- **Suggestion:** Continue refining the initiative tracker and combat flow for live in-person play — faster HP edits, keyboard shortcuts, cleaner combatant card layout.
- **Benefit:** Reduces DM friction at the table and is the last remaining blocker for the v1.0 "Friends & Family" release.
