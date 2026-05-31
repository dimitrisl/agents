# 🛡️ Code Review Findings & Recommendations

This document outlines key technical and architectural findings identified during a code review of the **Phyrexian Forge** backend codebase, along with concrete recommendations and their **current implementation status**.

---

## ✅ DONE — Centralized Prompt Management
* **Location:** `backend/core/prompts.py`
* **Status:** **Implemented.** All AI prompts (forge, session prep, NPC generation, rule comparison, etc.) have been extracted into `backend/core/prompts.py` and are imported by the relevant services. The prompts file is 12KB and covers all use cases including `RULE_COMPARISON_PROMPT`, `SESSION_PREP_PROMPT`, `NPC_PROMPT`, etc.

---

## ✅ DONE — PDF Field Abstraction
* **Location:** `backend/utils/pdf_exporter.py`, `data/pdf_mappings/`
* **Status:** **Implemented.** The `PDFExporter` class reads its field mappings from external JSON files in `data/pdf_mappings/` (e.g., `mapping_name.json`). Adding support for a new character sheet template requires only a new JSON file, not changes to Python code.

---

## ✅ DONE — Interactive Initiative Tracker
* **Location:** `views/dm_workspace.py` (`_render_initiative_tracker`)
* **Status:** **Implemented.** Full-featured initiative tracker exists in the DM Workspace, including HP bars, status conditions, concentration tracking, turn order management, statblock popovers, per-combatant quick roll, and a **per-combatant portrait editor** (🖼️ Portrait popover supporting URL and file upload, syncing back to MongoDB on apply).

---

## ✅ DONE — Rule Comparison Tool
* **Location:** `views/library_view.py`, `backend/services/rules_service.py`, `backend/core/prompts.py`
* **Status:** **Implemented.** A dedicated "Rule Comparison" tab exists in the Library view. The user can enter any topic and the AI returns a structured 2014 vs 2024 edition comparison using `RULE_COMPARISON_PROMPT`.

---

## ✅ DONE — AI Portrait Generation & Custom Portrait Management
* **Location:** `backend/utils/image_utils.py`, `views/player_dashboard.py`, `views/dm_workspace.py`
* **Status:** **Implemented.** Portrait generation is integrated at multiple points: during character forge, from the player dashboard (🎨 Portrait button), during PDF import, and in the DM Quick Forge. Portraits can be regenerated and previewed before being committed.
  * **New (2026-05-29):** Players can change their character portrait directly from the dashboard in Edit Mode via the "🖼️ Change Character Portrait" expander (URL or file upload).
  * **New (2026-05-29):** DMs can change any combatant's portrait mid-combat via the "🖼️ Portrait" popover in the Initiative Tracker. Changes sync back to party characters and campaign NPC records in MongoDB.
  * Local file paths are converted to base64 for rendering inside HTML cards.

---

## ✅ DONE — Testing Suite & Pydantic Validation
* **Location:** `tests/`, `backend/core/schemas.py`
* **Status:** **Implemented.** 141 tests across 16 test files, covering repositories, mechanics, dice, schemas, state manager, PDF export/import, storage facade, rule comparison, dm_service, and image_utils. All tests pass via pre-commit hooks.

---

## ✅ DONE — Edition-Specific Characters & Campaigns
* **Location:** `backend/repositories/character_repository.py`, `backend/repositories/campaign_repository.py`, `views/dm_workspace.py`, `views/player_dashboard.py`
* **Status:** **Implemented.** Characters store a `dnd_edition` field. Campaigns store a `dnd_edition` field and `list_all()` filters by edition. Character ingestion in the DM workspace (party manager, initiative tracker) only shows characters matching the active campaign edition. Legacy data without an edition field defaults to 2014 Edition.

---

## ✅ DONE — Campaign CRUD (Create, Read, Update, Delete)
* **Location:** `backend/repositories/campaign_repository.py`, `backend/core/storage.py`, `views/dm_workspace.py`
* **Status:** **Implemented.** Full campaign lifecycle: create, load, save notes, delete (with two-click confirmation in UI), join/leave party members.

---

## ✅ DONE — LRU Cache Memory Leak on Instance Methods
* **Location:** [`rules_repository.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/repositories/rules_repository.py#L29-L96)
* **Status:** **Implemented.** Methods now utilize module-level dictionaries for caching (`_class_progression_cache`, `_available_classes_cache`, `_feats_cache`, etc.). This eliminates the memory leak caused by `self` in instance-level `@lru_cache` decorators, allowing repository instances to be garbage collected normally.

---

## ✅ DONE — Pydantic Defaults Bypass in State Manager
* **Location:** [`state_manager.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/state_manager.py#L240-L251`) (`update_session_from_dict`)
* **Status:** **Implemented.** The fallback logic now inspects `CharacterSchema.model_fields` to extract correct defaults defined in the Pydantic schema instead of hardcoding `0` for fields like `armor_class`, `speed`, and `proficiency_bonus`.

---

## ✅ DONE — In-Place Mutation of Domain Objects
* **Location:** [`mechanics_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/mechanics_service.py) (`sync_character_stats`)
* **Status:** **Implemented.** `sync_character_stats` now begins by making a `copy.deepcopy(char_data)`. All updates are applied to this local copy to prevent unintended side-effects and race conditions in persistent Streamlit session states.

---

## ✅ DONE — Over-Lenient Auto-Healing on Save/Load
* **Location:** [`character_repository.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/repositories/character_repository.py#L35-L55) (`save`, `load`)
* **Status:** **Implemented.** Strict schema validation is enforced during saves and loads. If validation fails, a structured `ValueError` is raised, preventing database pollution with corrupted records.

---

## ✅ DONE — Fragile Regex & Substring Heuristics
* **Location:** [`mechanics_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/mechanics_service.py) (`calculate_weapon_stats`), [`rules_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/rules_service.py) (`regex_parse_feat_attributes`)
* **Status:** **Implemented.**
  * `Weapon` and `Equipment` schemas support an `is_custom` flag to bypass auto-calculations. Weapon stats support explicit `ability_modifier` overrides.
  * Feat parsing normalizes whitespace and punctuation prior to running regex matches.
  * `calculate_ac` now supports Monk & Barbarian Unarmored Defense (utilizing WIS and CON stats), Draconic Resilience, and Mage Armor base AC values.

---

## 🔮 FUTURE — Player / DM Authentication (OAuth2)
* **Status:** Not started.
* **Description:** Add Google/Discord login so each player and DM sees only their own characters and campaigns in MongoDB (via an `owner_id` field). This is the main blocker for making the app truly multi-user.
* **Effort:** High — requires OAuth2 integration, session token management, and query-level access control across all repositories.

---

*Last updated: 2026-05-29*
