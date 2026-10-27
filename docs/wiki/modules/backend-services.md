# ⚙️ Subsystem: Backend Services (`backend/services/`)

## 📌 Overview
The `backend/services/` package houses the core business logic of Phyrexian Forge. Services encapsulate domain rules independently of HTTP frameworks and database drivers where possible.

---

## 🔑 Key Services

| Service | Responsibility |
| :--- | :--- |
| [`stats_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/stats_service.py) | Mathematical calculation authority: calculates derived stats (`process_character_update`), AC breakdown, HP with retroactive CON adjustments, multiclass spell slots, weapon attack & damage breakdown calculations, weapon mastery Save DCs, and dynamic skill proficiency/expertise multipliers with passive scores. |
| [`validation_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/validation_service.py) | Deterministic build validation: verifies ability scores, proficiencies, subclass progression levels, and feat requirements against `RulesRepository`. |
| [`forge_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/forge_service.py) | Character creation engine: orchestrates prompt generation, AI character synthesis, portrait prompt generation, and manual character enrichment. |
| [`vtt_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/vtt_service.py) | Virtual Tabletop engine: atomic token movement, token additions/removals, grid configuration, and player state redaction (hiding secret DM tokens). |
| [`session_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/session_service.py) | Session recap engine: audio streaming to Gemini 1.5 multimodal, transcription, entity extraction (NPCs, locations, loot), and text session processing. |
| [`rules_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/rules_service.py) | Subclass progression scaling resolution (Planar Warrior, Distant Strike, Spectral Defense), 2014/2024 class matrix evaluation, rules comparison engine, and PDF character extraction parser. |
| [`homebrew_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/homebrew_service.py) | CRUD operations, AI forge generation, and JSON export/import for custom campaign homebrew items. |
| [`dm_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/dm_service.py) | AI Dungeon Master assistant: dynamic encounter balancing, tactical monster briefs, on-the-fly NPC generation, and session prep tools. |
| [`module_parser_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/module_parser_service.py) | Ingests D&D adventure modules (PDF/Markdown), extracts maps, handouts, and encounters, and cleans temporary assets older than 24h. |
