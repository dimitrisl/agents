import json
import os
import logging

logger = logging.getLogger("DnDAssistant.Config")

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "ai_settings": {
        "preferred_model": "gemini-1.5-pro",
        "fallback_model": "gemini-1.5-flash",
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
            # Merge with defaults to ensure all keys exist
            return {**DEFAULT_CONFIG, **config}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return DEFAULT_CONFIG


def save_config(config):
    """Saves the configuration to config.json."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
