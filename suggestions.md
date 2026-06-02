# 🩸 Phyrexian Forge: Project Suggestions

Following a comprehensive review of the **Phyrexian Forge** codebase, here are prioritized suggestions for architectural improvements, new features, and quality enhancements.

---

## 🛠️ 1. Architectural Improvements

### ✅ DONE — PDF Field Abstraction
The mapping of character data to PDF form fields in `backend/pdf_exporter.py` was hardcoded.
- **Status:** Implemented. Mappings now live in `data/pdf_mappings/` as JSON files. Adding a new sheet template requires no Python changes.

### ✅ DONE — Caching Strategy
Frequent Streamlit reruns can lead to unnecessary API calls and latency.
- **Status:** Implemented. Decorated rules-related service calls (`query_rules` and `compare_rules` in `backend/services/rules_service.py`) with `@st.cache_data` to ensure repeat questions and comparisons are answered instantly from memory without hitting the Gemini API.
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

### ✅ DONE — Player / DM Authentication (OAuth2)
- **Status:** Implemented. Built a Discord and Google OAuth2-based authentication gate. Secured characters and campaigns in MongoDB by stamping them with `owner_id`. Implemented strict backend validation checks on load, delete, and list queries in `backend/core/storage.py` and repository classes to prevent cross-user data exposure while preserving public legacy files.
- **Benefit:** Allows players to securely manage their own roster of characters and DMs to isolate their campaigns from others.


---

## 🧪 3. Quality Assurance & DX

### ✅ DONE — Automated Testing Suite
- **Status:** Implemented. 141 tests across 16 test files (`tests/`) covering mechanics, dice, schemas, state manager, PDF export/import, repositories, storage facade, rule comparison, dm_service, and image_utils. All run automatically via pre-commit hooks.

### ✅ DONE — Robust Schema Validation (Pydantic)
- **Status:** Implemented. `backend/core/schemas.py` defines strict Pydantic models for characters, weapons, equipment, and spells. All AI-generated and user-edited data is validated before storage.

---

## 🎨 4. UI/UX Polishing

### ✅ DONE — Themed Markdown Rendering
- **Status:** Implemented. Custom CSS rules are injected globally in the app's stylesheets, targeting markdown blocks wrapped in `<div class="themed-markdown-block"></div>`. All AI-generated markdown (Oracle responses, Rule Comparisons, Playstyle Guides, Session Prep, NPC descriptions, Riddles, and Encounters) are rendered within this premium, glassmorphic dark container featuring hover micro-animations and highlighted headers/code blocks.
- **Benefit:** Creates a more immersive "Phyrexian" user experience.


### ✅ DONE — Character Export Preview
- **Status:** Implemented. Before exporting the PDF character sheet, users see a modal preview card summarizing their identity, vitals, stats, saving throws, skill proficiencies, weapons, and features.
- **Benefit:** Allows users to verify AI Forge results before committing to a download.


### ✅ DONE — Table-Ready UX Polish
- **Status:** Implemented. Integrated a quick **+/- HP Adjuster** field directly into the active combat cards of the Initiative Tracker. The DM can type damage (e.g., `-12`) or healing (e.g., `8`) and press Enter to instantly modify HP. The tracker updates in-place, synchronizes with the MongoDB records of character party members, and resets the input to `0` automatically.
- **Benefit:** Drastically reduces DM math overhead and friction at the table, completing the final blocker for the v1.0 "Friends & Family" release.
