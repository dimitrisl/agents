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
| [`ai_client.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/ai_client.py) | Client interface for LLM models (Gemini & Anthropic Claude). Implements `generate_ai_json()` and `generate_ai_response()` delegated through `get_llm_provider()`. |
| [`providers/`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/providers) | Multi-provider LLM routing (`RoutingProvider`, `GeminiProvider`, `AnthropicProvider`, `LLMProvider` in `factory.py`). Routes text/JSON calls per request based on the user's selected model and decrypted BYOK Anthropic API key; keeps file/audio uploads on Gemini. |
| [`homebrew_schemas.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/homebrew_schemas.py) | Pydantic validation schemas for custom homebrew items, weapons, feats, and spells. |
| [`config_loader.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/core/config_loader.py) | Configuration, directory path resolver, and request-scoped `ContextVar` storage for per-user AI model preferences and decrypted API keys. |
