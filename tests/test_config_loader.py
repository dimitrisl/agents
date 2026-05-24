import os
import pytest
from backend.core.config_loader import (
    load_config,
    save_config,
    CONFIG_FILE,
    DEFAULT_CONFIG,
)


@pytest.fixture
def clean_config():
    """Ensure config.json doesn't exist before and after tests."""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    yield
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)


def test_load_config_defaults(clean_config):
    config = load_config()
    assert config == DEFAULT_CONFIG
    assert os.path.exists(CONFIG_FILE)


def test_save_and_load_config(clean_config):
    custom_config = {"ai_settings": {"temperature": 1.0}}
    save_config(custom_config)

    loaded = load_config()
    assert loaded["ai_settings"]["temperature"] == 1.0
    # Verify merge with defaults
    assert loaded["ai_settings"]["preferred_model"] == "gemini-1.5-pro"


def test_load_corrupted_config(clean_config):
    with open(CONFIG_FILE, "w") as f:
        f.write("{ invalid json }")

    config = load_config()
    assert config == DEFAULT_CONFIG
