# 🧩 Subsystem: Backend Core (`backend/core/`)

## 📌 Overview
The `backend/core/` package holds fundamental data models, system prompt templates, game constants, and the Google GenAI provider abstraction layer.

---

## 🔑 Key Modules

| Module | Responsibility |
| :--- | :--- |
| [`schemas.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/schemas.py) | Comprehensive Pydantic models for domain objects: `CharacterSchema`, `StatBlock`, `SpellSlotSchema`, `WeaponSchema`, `CampaignSchema`, `VTTStateSchema`, `VTTTokenSchema`, `ClassScalingResponse`, and API payloads. |
| [`constants.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/constants.py) | Game constants, official class names, editions (`2014 Edition`, `2024 Edition`), stat keys (`STR`, `DEX`, `CON`, `INT`, `WIS`, `CHA`), and skill-to-ability mapping dictionaries. |
| [`prompts.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/prompts.py) | Structured Phyrexian-themed prompt templates for character forge, DM copilot, and session narrative summaries. |
| [`ai_client.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/ai_client.py) | Client interface for Gemini models (`gemini-1.5-flash`, `gemini-1.5-pro`). Implements `generate_ai_json()` for structured Pydantic generation. |
| [`providers/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/providers) | Pluggable LLM provider factory (`LLMProvider`, `GeminiProvider`, `factory.py`) with thread-safe singleton initialization. |
| [`homebrew_schemas.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/homebrew_schemas.py) | Pydantic validation schemas for custom homebrew items, weapons, feats, and spells. |
| [`config_loader.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/config_loader.py) | Configuration and directory path resolver for application assets. |
