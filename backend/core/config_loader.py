import json
import logging
import os
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger("DnDAssistant.Config")

CONFIG_FILE = "config.json"

# Models selectable from the Settings page. Free-tier models have no Pro
# equivalent on the free Gemini API quota, so "pro" calls (module/file
# parsing) stay on the selected model instead of escalating to pro_model.
# Anthropic models run on the user's own API key (saved in Settings).
AVAILABLE_MODELS = {
    "gemini-3.5-flash": {
        "label": "Gemini 3.5 Flash (Free)",
        "provider": "gemini",
        "free_tier": True,
    },
    "gemini-3.6-flash": {
        "label": "Gemini 3.6 Flash (Fast)",
        "provider": "gemini",
        "free_tier": False,
    },
    "gemini-3.1-pro-preview": {
        "label": "Gemini 3.1 Pro (Deep Reasoning)",
        "provider": "gemini",
        "free_tier": False,
    },
    "claude-opus-5-5": {
        "label": "Claude Opus 5.5 (Best Quality)",
        "provider": "anthropic",
        "free_tier": False,
    },
    "claude-sonnet-5-5": {
        "label": "Claude Sonnet 5.5 (Balanced)",
        "provider": "anthropic",
        "free_tier": False,
    },
    "claude-haiku-5-5": {
        "label": "Claude Haiku 5.5 (Cheapest)",
        "provider": "anthropic",
        "free_tier": False,
    },
}

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"

# Map retired/legacy Gemini IDs saved in old config files or MongoDB user records
# to active replacements so existing users never hit silent 404 model failures.
LEGACY_GEMINI_MODEL_ALIASES = {
    "gemini-1.5-flash": "gemini-3.5-flash",
    "gemini-1.5-pro": "gemini-3.1-pro-preview",
    "gemini-2.0-flash": "gemini-3.5-flash",
    "gemini-2.5-flash": "gemini-3.5-flash",
    "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-pro": "gemini-3.1-pro-preview",
}


def resolve_gemini_model_id(model: Optional[str]) -> str:
    """Normalize and transparently migrate retired Gemini model IDs to active defaults."""
    clean = str(model or "").strip()
    if clean.startswith("models/"):
        clean = clean[7:]
    if not clean:
        return DEFAULT_GEMINI_MODEL
    return LEGACY_GEMINI_MODEL_ALIASES.get(clean, clean)


def is_free_tier_model(model: str) -> bool:
    return AVAILABLE_MODELS.get(model, {}).get("free_tier", False)


def provider_for_model(model: str) -> str:
    return AVAILABLE_MODELS.get(model, {}).get("provider", "gemini")


# Per-user AI preferences for the current request/task. Set by the auth
# dependency from the user document; empty for unauthenticated/background work.
_user_ai_settings: ContextVar[Optional[dict]] = ContextVar("user_ai_settings", default=None)


def set_user_ai_settings(user_settings: Optional[dict]) -> None:
    _user_ai_settings.set(user_settings or None)


def get_ai_settings() -> dict:
    """Global ai_settings from config.json, overridden by the current user's choices."""
    raw_global = load_config().get("ai_settings", {})
    ai_settings = dict(raw_global)
    for field in ("preferred_model", "fallback_model", "pro_model"):
        if field in ai_settings and provider_for_model(ai_settings[field]) == "gemini":
            migrated = resolve_gemini_model_id(ai_settings[field])
            if field == "preferred_model" and migrated not in AVAILABLE_MODELS:
                migrated = DEFAULT_GEMINI_MODEL
            ai_settings[field] = migrated

    user_settings = _user_ai_settings.get() or {}

    model = user_settings.get("preferred_model")
    if model in AVAILABLE_MODELS:
        ai_settings["preferred_model"] = model
    elif model in LEGACY_GEMINI_MODEL_ALIASES:
        migrated = LEGACY_GEMINI_MODEL_ALIASES[model]
        if migrated in AVAILABLE_MODELS:
            ai_settings["preferred_model"] = migrated

    temperature = user_settings.get("temperature")
    if isinstance(temperature, (int, float)) and 0.0 <= temperature <= 1.0:
        ai_settings["temperature"] = float(temperature)

    return ai_settings


def get_user_api_key(provider: str) -> Optional[str]:
    """The current user's own API key for a provider (already decrypted by auth)."""
    user_settings = _user_ai_settings.get() or {}
    return (user_settings.get("api_keys") or {}).get(provider) or None


DEFAULT_CONFIG = {
    "ai_settings": {
        "preferred_model": "gemini-3.5-flash",
        "fallback_model": "gemini-3.6-flash",
        "pro_model": "gemini-3.1-pro-preview",
        "temperature": 0.7,
    },
    "app_settings": {"debug_mode": False, "portrait_dir": "data/portraits"},
}


def load_config():
    """Loads configuration from config.json, creates with defaults if missing."""
    if not os.path.exists(CONFIG_FILE):
        logger.info(f"Config file {CONFIG_FILE} missing. Creating with defaults.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Shallow merge for top-level, deep merge for known dicts
            merged = DEFAULT_CONFIG.copy()
            for k, v in config.items():
                if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
            return merged
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return DEFAULT_CONFIG


def save_config(config):
    try:
        temp_file = f"{CONFIG_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(config, f, indent=4)
        os.replace(temp_file, CONFIG_FILE)
    except (IOError, OSError) as e:
        logger.error(f"IO Error saving config: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
    except TypeError as e:
        logger.error(f"Serialization Error saving config: {e}")
