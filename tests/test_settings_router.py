import os
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.core.config_loader import CONFIG_FILE, get_ai_settings, set_user_ai_settings
from backend.core.providers.gemini_provider import GeminiProvider
from server.db_async import get_database
from server.dependencies.auth import get_current_user, user_ai_context
from server.main import app

client = TestClient(app)


@pytest.fixture
def users_db():
    """Two users with their own ai_settings; auth resolves to whichever is 'logged in'."""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)

    users = {
        "u1": {"id": "u1", "username": "dm"},
        "u2": {
            "id": "u2",
            "username": "player",
            "ai_settings": {"preferred_model": "gemini-2.5-pro", "temperature": 0.2},
        },
    }
    state = {"current": "u1"}

    def update_one(query, update):
        users[query["id"]].update(update["$set"])
        return MagicMock()

    users_col = MagicMock()
    users_col.update_one.side_effect = update_one

    async def current_user():
        user = users[state["current"]]
        # Mirrors get_current_user_from_token
        set_user_ai_settings(user_ai_context(user.get("ai_settings")))
        return user

    app.dependency_overrides[get_database] = lambda: {"users": users_col}
    app.dependency_overrides[get_current_user] = current_user
    yield users, state
    app.dependency_overrides.clear()
    set_user_ai_settings(None)
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)


def test_get_ai_settings_lists_free_model_and_global_default(users_db):
    response = client.get("/api/v1/settings/ai")
    assert response.status_code == 200
    data = response.json()
    assert data["preferred_model"] == "gemini-2.5-flash"
    free = [m for m in data["available_models"] if m["free_tier"]]
    assert [m["id"] for m in free] == ["gemini-3.5-flash"]


def test_get_ai_settings_returns_users_own_choice(users_db):
    _, state = users_db
    state["current"] = "u2"
    data = client.get("/api/v1/settings/ai").json()
    assert data["preferred_model"] == "gemini-2.5-pro"
    assert data["temperature"] == 0.2


def test_update_only_affects_calling_user(users_db):
    users, state = users_db
    response = client.put(
        "/api/v1/settings/ai",
        json={"preferred_model": "gemini-3.5-flash", "temperature": 0.4},
    )
    assert response.status_code == 200
    assert response.json()["preferred_model"] == "gemini-3.5-flash"
    assert users["u1"]["ai_settings"] == {
        "preferred_model": "gemini-3.5-flash",
        "temperature": 0.4,
    }

    # The other user keeps their own model
    state["current"] = "u2"
    assert client.get("/api/v1/settings/ai").json()["preferred_model"] == "gemini-2.5-pro"
    # Global config untouched
    assert not os.path.exists(CONFIG_FILE) or "gemini-3.5-flash" not in open(CONFIG_FILE).read()


def test_update_ai_settings_rejects_unknown_model(users_db):
    response = client.put(
        "/api/v1/settings/ai",
        json={"preferred_model": "gpt-4", "temperature": 0.4},
    )
    assert response.status_code == 400


def test_update_ai_settings_requires_login():
    app.dependency_overrides.clear()
    response = client.put(
        "/api/v1/settings/ai",
        json={"preferred_model": "gemini-3.5-flash", "temperature": 0.4},
    )
    assert response.status_code == 401


def test_invalid_user_overrides_fall_back_to_global():
    set_user_ai_settings({"preferred_model": "not-a-model", "temperature": 7})
    try:
        ai = get_ai_settings()
        assert ai["preferred_model"] == "gemini-2.5-flash"
        assert ai["temperature"] == 0.7
    finally:
        set_user_ai_settings(None)


@pytest.fixture
def user_model():
    def _set(model):
        set_user_ai_settings({"preferred_model": model, "temperature": 0.7})

    yield _set
    set_user_ai_settings(None)


def test_free_model_skips_pro_and_model_listing(user_model):
    user_model("gemini-3.5-flash")
    provider = GeminiProvider(api_key="test")
    provider.client = MagicMock()

    assert provider._get_model() == "gemini-3.5-flash"
    assert provider._get_model(use_pro=True) == "gemini-3.5-flash"
    provider.client.models.list.assert_not_called()


def test_paid_model_still_escalates_to_pro(user_model):
    user_model("gemini-2.5-flash")
    provider = GeminiProvider(api_key="test")
    assert provider._get_model(use_pro=True) == "gemini-2.5-pro"


def test_text_cache_is_per_model(user_model):
    provider = GeminiProvider(api_key="test")
    provider.client = MagicMock()
    provider.client.models.generate_content.side_effect = lambda model, **_: MagicMock(text=model)
    GeminiProvider._generate_text_cached.cache_clear()

    user_model("gemini-3.5-flash")
    assert provider.generate_text("same prompt") == "gemini-3.5-flash"
    user_model("gemini-2.5-pro")
    provider.client.models.list.return_value = [MagicMock(name="m")]
    provider.client.models.list.return_value[0].name = "models/gemini-2.5-pro"
    assert provider.generate_text("same prompt") == "gemini-2.5-pro"


def test_quota_error_maps_to_429(user_model):
    user_model("gemini-3.5-flash")
    provider = GeminiProvider(api_key="test")
    provider.client = MagicMock()
    provider.client.models.generate_content.side_effect = Exception(
        "429 RESOURCE_EXHAUSTED quota exceeded"
    )
    GeminiProvider._generate_text_cached.cache_clear()

    with pytest.raises(HTTPException) as exc:
        provider.generate_text("quota test prompt")
    assert exc.value.status_code == 429


# --- Claude (own Anthropic key) ---


@pytest.fixture
def key_check(mocker):
    """Anthropic key verification stubbed out (it would hit the network)."""
    return mocker.patch("server.routers.settings_router._verify_anthropic_key")


def test_claude_model_requires_a_key(users_db, key_check):
    response = client.put(
        "/api/v1/settings/ai",
        json={"preferred_model": "claude-sonnet-5-5", "temperature": 0.7},
    )
    assert response.status_code == 400
    assert "Anthropic API key" in response.json()["detail"]


def test_saving_key_encrypts_it_and_only_returns_a_hint(users_db, key_check):
    users, _ = users_db
    secret = "sk-ant-test-key-1234abcd"
    response = client.put(
        "/api/v1/settings/ai",
        json={
            "preferred_model": "claude-sonnet-5-5",
            "temperature": 0.7,
            "anthropic_api_key": f"  {secret}  ",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["preferred_model"] == "claude-sonnet-5-5"
    assert data["has_anthropic_key"] is True
    assert data["anthropic_key_hint"] == "abcd"
    assert secret not in response.text
    key_check.assert_called_once_with(secret)

    stored = users["u1"]["ai_settings"]
    assert "anthropic_api_key" not in stored
    assert secret not in stored["anthropic_api_key_enc"]
    assert user_ai_context(stored)["api_keys"]["anthropic"] == secret

    # Saving again without the field keeps the key
    response = client.put(
        "/api/v1/settings/ai",
        json={"preferred_model": "claude-opus-5-5", "temperature": 0.7},
    )
    assert response.status_code == 200
    assert response.json()["has_anthropic_key"] is True


def test_empty_key_removes_it(users_db, key_check):
    users, _ = users_db
    client.put(
        "/api/v1/settings/ai",
        json={
            "preferred_model": "gemini-2.5-flash",
            "temperature": 0.7,
            "anthropic_api_key": "sk-ant-x-9999",
        },
    )
    response = client.put(
        "/api/v1/settings/ai",
        json={"preferred_model": "gemini-2.5-flash", "temperature": 0.7, "anthropic_api_key": ""},
    )
    assert response.json()["has_anthropic_key"] is False
    assert "anthropic_api_key_enc" not in users["u1"]["ai_settings"]


def test_available_models_include_claude_with_provider(users_db):
    models = client.get("/api/v1/settings/ai").json()["available_models"]
    claude = {m["id"] for m in models if m["provider"] == "anthropic"}
    assert claude == {"claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"}


@pytest.fixture
def claude_user():
    def _set(model, key="sk-ant-routing"):
        set_user_ai_settings(
            {"preferred_model": model, "temperature": 0.7, "api_keys": {"anthropic": key}}
        )

    yield _set
    set_user_ai_settings(None)


def _claude_response(text, stop_reason="end_turn"):
    return MagicMock(
        stop_reason=stop_reason,
        content=[MagicMock(type="thinking"), MagicMock(type="text", text=text)],
    )


def test_router_sends_claude_calls_to_anthropic_without_temperature(claude_user, mocker):
    from backend.core.providers.factory import RoutingProvider

    claude_user("claude-haiku-5-5")
    anthropic_cls = mocker.patch("backend.core.providers.anthropic_provider.anthropic.Anthropic")
    sdk = anthropic_cls.return_value
    sdk.messages.create.return_value = _claude_response('```json\n{"ok": true}\n```')

    router = RoutingProvider()
    router._gemini = MagicMock()
    assert router.generate_json("prompt", temperature=0.3) == {"ok": True}

    anthropic_cls.assert_called_once_with(api_key="sk-ant-routing")
    kwargs = sdk.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-5-5"
    assert "temperature" not in kwargs
    assert kwargs["output_config"] == {"effort": "medium"}
    router._gemini.generate_json.assert_not_called()


def test_opus_and_sonnet_use_server_side_fallbacks(claude_user, mocker):
    from backend.core.providers.factory import RoutingProvider

    claude_user("claude-opus-5-5", key="sk-ant-fallbacks")
    sdk = mocker.patch("backend.core.providers.anthropic_provider.anthropic.Anthropic").return_value
    sdk.beta.messages.create.return_value = _claude_response("Hello")

    assert RoutingProvider().generate_text("unique fallback prompt") == "Hello"
    kwargs = sdk.beta.messages.create.call_args.kwargs
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_refusal_becomes_http_error(claude_user, mocker):
    from backend.core.providers.factory import RoutingProvider

    claude_user("claude-haiku-5-5", key="sk-ant-refusal")
    sdk = mocker.patch("backend.core.providers.anthropic_provider.anthropic.Anthropic").return_value
    sdk.messages.create.return_value = _claude_response("", stop_reason="refusal")

    with pytest.raises(HTTPException) as exc:
        RoutingProvider().generate_text("refused prompt")
    assert exc.value.status_code == 422


def test_claude_without_key_is_a_clear_error(claude_user):
    from backend.core.providers.factory import RoutingProvider

    claude_user("claude-sonnet-5-5", key=None)
    router = RoutingProvider()
    with pytest.raises(HTTPException) as exc:
        router.generate_text("x")
    assert exc.value.status_code == 400
    assert router.client is None


def test_file_calls_stay_on_gemini_for_claude_users(claude_user):
    from backend.core.providers.factory import RoutingProvider

    claude_user("claude-opus-5-5")
    router = RoutingProvider()
    router._gemini = MagicMock()
    router.upload_file("module.pdf")
    router.generate_json_from_files(["f1"], "prompt")
    router._gemini.upload_file.assert_called_once_with("module.pdf")
    router._gemini.generate_json_from_files.assert_called_once()


def test_gemini_ignores_claude_choice_for_its_own_model(claude_user):
    claude_user("claude-opus-5-5")
    provider = GeminiProvider(api_key="test")
    provider.client = MagicMock()
    listed = MagicMock()
    listed.name = "models/gemini-2.5-flash"
    provider.client.models.list.return_value = [listed]
    assert provider._get_model() == "gemini-2.5-flash"
