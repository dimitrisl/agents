# 🧩 Subsystem: Backend Core (`backend/core/`)

## 📌 Overview
The `backend/core/` package holds fundamental data models, system prompt templates, game constants, and the Google GenAI provider abstraction layer.

---

## 🔑 Key Modules

| Module | Responsibility |
| :--- | :--- |
| [`schemas.py`](../../../backend/core/schemas.py) | Comprehensive Pydantic models for domain objects: `CharacterSchema` (including `always_prepared_spells`, `max_prepared_spells`, `weapon_proficiencies`, `senses`, `damage_resistances`, `save_advantages`, `exhaustion_bypass`, `magic_items_suppressed`, `dm_modifiers`, `dm_short_rest_unlocked`, `dm_long_rest_unlocked`, `dm_level_up_unlocked`, `dm_hp_bonus_applied`), `DmModifiersSchema`, `StatBlock`, `SpellSlotSchema`, `Weapon` (`dm_attack_bonus_applied`, `dm_damage_bonus_applied`, `magic_bonus_suppressed_applied`), `CampaignSchema`, `VTTStateSchema`, `VTTTokenSchema`, `ClassScalingResponse`, `LevelUpAnalysisSchema`, `LevelUpChoice`, `LevelUpFeatMetadata`, and API payloads. |
| [`constants.py`](../../../backend/core/constants.py) | Game constants, official class & subclass names (e.g., `"Way of Mercy"`), editions (`2014 Edition`, `2024 Edition`), stat keys (`STR`, `DEX`, `CON`, `INT`, `WIS`, `CHA`), and skill-to-ability mapping dictionaries. |
| [`subclass_features_2024.py`](../../../backend/core/subclass_features_2024.py) | Complete 2024 Revision (5.5e) subclass progression catalog (`SUBCLASS_FEATURES_DETAILS_2024` and derived `KNOWN_SUBCLASS_FEATURES_2024`) covering all 13 classes across all subclass levels (L3–L20). |
| [`prompts.py`](../../../backend/core/prompts.py) | Structured Phyrexian-themed prompt templates for character forge, DM copilot, and session narrative summaries. |
| [`ai_client.py`](../../../backend/core/ai_client.py) | Client interface for LLM models (Gemini & Anthropic Claude). Implements `generate_ai_json()` and `generate_ai_response()` delegated through `get_llm_provider()`. |
| [`providers/`](../../../backend/core/providers) | Multi-provider LLM routing (`RoutingProvider`, `GeminiProvider`, `AnthropicProvider`, `LLMProvider` in `factory.py`). Routes text/JSON calls per request based on the user's selected model and decrypted BYOK Anthropic API key; keeps file/audio uploads on Gemini. |
| [`homebrew_schemas.py`](../../../backend/core/homebrew_schemas.py) | Pydantic validation schemas for custom homebrew items, weapons, feats, and spells. |
| [`config_loader.py`](../../../backend/core/config_loader.py) | Configuration, directory path resolver, Gemini model registry (`DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"`, fallback `"gemini-3.6-flash"`, `LEGACY_GEMINI_MODEL_ALIASES` / `resolve_gemini_model_id()` legacy 2.5 migration), and request-scoped `ContextVar` storage for per-user AI model preferences and decrypted API keys. |
| [`gemini_provider.py`](../../../backend/core/providers/gemini_provider.py) | Google GenAI wrapper with automatic candidate model fallback (`_candidate_models`, `_should_retry_with_fallback`, `_call_with_model_fallback`) across text, JSON, and multimodal calls when a configured model returns `404 NOT_FOUND` or transient availability errors. |
