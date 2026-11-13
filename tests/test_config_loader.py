import os

import pytest

import backend.core.config_loader as config_loader
from backend.core.config_loader import (
    DEFAULT_CONFIG,
    load_config,
    save_config,
)


@pytest.fixture
def clean_config(tmp_path, monkeypatch):
    """Isolate config.json per test so parallel xdist workers never collide."""
    isolated_cfg = str(tmp_path / "config.json")
    monkeypatch.setattr(config_loader, "CONFIG_FILE", isolated_cfg)
    yield isolated_cfg
    if os.path.exists(isolated_cfg):
        os.remove(isolated_cfg)


def test_load_config_defaults(clean_config):
    config = load_config()
    assert config == DEFAULT_CONFIG
    assert os.path.exists(clean_config)


def test_save_and_load_config(clean_config):
    custom_config = {"ai_settings": {"temperature": 1.0}}
    save_config(custom_config)

    loaded = load_config()
    assert loaded["ai_settings"]["temperature"] == 1.0
    # Verify merge with defaults
    assert loaded["ai_settings"]["preferred_model"] == "gemini-2.5-flash"


def test_load_corrupted_config(clean_config):
    with open(clean_config, "w") as f:
        f.write("{ invalid json }")

    config = load_config()
    assert config == DEFAULT_CONFIG
