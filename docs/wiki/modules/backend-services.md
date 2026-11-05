# ⚙️ Subsystem: Backend Services (`backend/services/`)

## 📌 Overview
The `backend/services/` package houses the core business logic of Phyrexian Forge. Services encapsulate domain rules independently of HTTP frameworks and database drivers where possible.

---

## 🔑 Key Services

| Service | Responsibility |
| :--- | :--- |
| [`stats_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/stats_service.py) | Mathematical calculation authority: calculates derived stats (`process_character_update`), AC breakdown (including magic armor $+N$, homebrew AC items, and attunement = attuned AND equipped), HP with retroactive CON adjustments, multiclass spell slots, weapon attack & damage breakdown calculations, weapon mastery Save DCs, and dynamic skill proficiency/expertise multipliers with passive scores. |
| [`class_resources_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/class_resources_service.py) | Data-driven class resource pools (`data/rules/class_resources.json`, 2014 & 2024) synced on every save: follows level-ups and multiclassing, adopts hand-made pools, preserves user `max_adjustment` across level-ups, and powers Sorcerer Flexible Casting & Metamagic. |
| [`validation_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/validation_service.py) | Deterministic build validation: verifies ability scores, proficiencies, subclass progression levels, and feat requirements against `RulesRepository`. |
| [`forge_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/forge_service.py) | Character creation engine: orchestrates prompt generation, AI character synthesis, portrait prompt generation, and manual character enrichment. |
| [`character_import_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/character_import_service.py) | Parses and normalizes external PDF character sheets and JSON exports into validated `CharacterSchema` objects. |
| [`vtt_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/vtt_service.py) | Virtual Tabletop engine: atomic token movement, token additions/removals, multi-scene management, Fog of War, grid configuration, and player state redaction (hiding secret DM tokens). |
| [`session_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/session_service.py) | Session recap engine: audio streaming to Gemini multimodal, transcription, entity extraction (NPCs, locations, loot), and text session processing. |
| [`rules_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/rules_service.py) | Subclass progression scaling resolution (Planar Warrior, Distant Strike, Spectral Defense), 2014/2024 class matrix evaluation, rules comparison engine, and PDF character extraction parser. |
| [`homebrew_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/homebrew_service.py) | CRUD operations, AI forge generation, and JSON export/import for custom campaign homebrew items. |
| [`dm_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/dm_service.py) & [`encounter_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/encounter_service.py) | AI Dungeon Master assistant: dynamic encounter balancing against actual party levels, tactical monster briefs, on-the-fly NPC generation, and session prep tools. |
| [`campaign_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/campaign_service.py) & [`user_admin_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/user_admin_service.py) | Campaign lifecycle helpers and administrative user management (pagination, role changes, cascading cleanup). |
| [`dice_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/dice_service.py) & [`progression_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/progression_service.py) | Server-side dice roll validation/dispatch and character level progression helpers. |
| [`module_parser_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/module_parser_service.py) | Ingests D&D adventure modules (PDF/Markdown), extracts maps, handouts, and encounters, and cleans temporary assets older than 24h. |
