from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server.dependencies.auth import create_access_token, get_current_user
from server.main import app
from server.rate_limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Ensure limiter is enabled and clean between test runs."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_login_rate_limiting(client):
    """
    POST /api/v1/auth/login must be rate limited to 5 attempts per minute per IP.
    The 6th attempt from the same IP must return HTTP 429 Too Many Requests with Retry-After.
    A request from a different IP should remain unblocked.
    """
    mock_db = MagicMock()
    mock_users = MagicMock()
    mock_users.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.return_value = mock_users

    from server.db_async import get_database

    app.dependency_overrides[get_database] = lambda: mock_db

    # 1. First 5 requests from IP 10.0.0.1 (login fails with 401, but rate limit counts them)
    for i in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "wrongpassword"},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert resp.status_code == 401, f"Attempt {i + 1} unexpected status: {resp.status_code}"
        assert resp.headers.get("x-ratelimit-limit") == "5"

    # 2. 6th request from IP 10.0.0.1 must be rejected with 429
    blocked_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "wrongpassword"},
        headers={"X-Forwarded-For": "10.0.0.1"},
    )
    assert blocked_resp.status_code == 429
    data = blocked_resp.json()
    assert "detail" in data
    assert "error" in data
    assert "Rate limit exceeded" in data["detail"]
    assert blocked_resp.headers.get("retry-after") is not None
    assert blocked_resp.headers.get("x-ratelimit-remaining") == "0"

    # 3. Request from a different IP (10.0.0.2) must NOT be blocked
    other_ip_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "wrongpassword"},
        headers={"X-Forwarded-For": "10.0.0.2"},
    )
    assert other_ip_resp.status_code == 401  # Not 429


def test_auth_register_rate_limiting(client):
    """
    POST /api/v1/auth/register must be rate limited to 3 registrations per minute per IP.
    The 4th attempt must return HTTP 429.
    """
    mock_db = MagicMock()
    mock_users = MagicMock()
    # Mock user not existing, insertion succeeds
    mock_users.find_one = AsyncMock(return_value=None)
    mock_users.insert_one = AsyncMock(return_value=MagicMock())
    mock_db.__getitem__.return_value = mock_users

    from server.db_async import get_database

    app.dependency_overrides[get_database] = lambda: mock_db

    for i in range(3):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"newuser_{i}",
                "password": "Password123!",
                "email": f"new_{i}@example.com",
            },
            headers={"X-Forwarded-For": "10.0.0.5"},
        )
        assert resp.status_code == 201, f"Attempt {i + 1} status: {resp.status_code}"

    # 4th registration from the same IP must be 429
    blocked_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser_blocked",
            "password": "Password123!",
            "email": "blocked@example.com",
        },
        headers={"X-Forwarded-For": "10.0.0.5"},
    )
    assert blocked_resp.status_code == 429
    assert "Rate limit exceeded" in blocked_resp.json()["detail"]


def test_ai_generation_rate_limiting_per_user(client):
    """
    AI endpoints (e.g. POST /api/v1/rules/query) must be rate limited to 10 requests/min per user.
    The 11th request for user_alpha must be 429.
    A different user_beta from the SAME IP must NOT be blocked.
    """
    token_alpha = create_access_token({"sub": "user_alpha", "username": "alpha"})
    token_beta = create_access_token({"sub": "user_beta", "username": "beta"})

    app.dependency_overrides[get_current_user] = lambda: {"id": "user_alpha", "username": "alpha"}

    with patch("server.routers.rules_router.query_rules", return_value="Rules explanation"):
        # 1. 10 requests for user_alpha
        for i in range(10):
            resp = client.post(
                "/api/v1/rules/query",
                json={"query": "How does sneak attack work?", "edition": "2024"},
                headers={
                    "Authorization": f"Bearer {token_alpha}",
                    "X-Forwarded-For": "10.0.0.50",
                },
            )
            assert resp.status_code == 200, f"Attempt {i + 1} failed: {resp.status_code}"
            assert resp.headers.get("x-ratelimit-limit") == "10"

        # 2. 11th request for user_alpha must return 429
        blocked_resp = client.post(
            "/api/v1/rules/query",
            json={"query": "How does sneak attack work?", "edition": "2024"},
            headers={
                "Authorization": f"Bearer {token_alpha}",
                "X-Forwarded-For": "10.0.0.50",
            },
        )
        assert blocked_resp.status_code == 429
        assert blocked_resp.headers.get("retry-after") is not None
        assert "Rate limit exceeded" in blocked_resp.json()["detail"]

        # 3. user_beta from the same IP (10.0.0.50) must NOT be blocked
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_beta", "username": "beta"}
        beta_resp = client.post(
            "/api/v1/rules/query",
            json={"query": "How does fireball work?", "edition": "2024"},
            headers={
                "Authorization": f"Bearer {token_beta}",
                "X-Forwarded-For": "10.0.0.50",
            },
        )
        assert beta_resp.status_code == 200


def test_audio_session_rate_limiting(client):
    """
    POST /api/v1/campaigns/{name}/sessions/audio must be rate limited to 2 requests/min per DM.
    The 3rd request must return 429.
    """
    token_dm = create_access_token({"sub": "dm_user", "username": "dm_user"})

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_user", "username": "dm_user"}

    mock_db = MagicMock()
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value={"user_id": "dm_user", "role": "dm"})
    mock_db.__getitem__.side_effect = lambda key: (
        mock_members if key == "campaign_members" else MagicMock()
    )
    mock_db.campaign_entities.insert_many = AsyncMock(return_value=MagicMock(inserted_ids=["1"]))
    mock_db.session_logs.insert_one = AsyncMock(return_value=MagicMock(inserted_id="log_1"))
    from server.db_async import get_database

    app.dependency_overrides[get_database] = lambda: mock_db

    with patch(
        "server.routers.session_router.session_service.process_audio_session",
        new=AsyncMock(
            return_value={
                "title": "Session 1",
                "summary": "Summary",
                "extracted_entities": [],
                "audio_file_id": "file_1",
            }
        ),
    ):
        # 1. First 2 requests succeed
        for i in range(2):
            resp = client.post(
                "/api/v1/campaigns/Neverwinter/sessions/audio",
                data={"session_number": i + 1},
                files={"audio_file": ("test.mp3", b"dummy audio content", "audio/mpeg")},
                headers={"Authorization": f"Bearer {token_dm}"},
            )
            assert resp.status_code == 200, f"Attempt {i + 1} status: {resp.status_code}"
            assert resp.headers.get("x-ratelimit-limit") == "2"

        # 2. 3rd request must be blocked with 429
        blocked_resp = client.post(
            "/api/v1/campaigns/Neverwinter/sessions/audio",
            data={"session_number": 3},
            files={"audio_file": ("test.mp3", b"dummy audio content", "audio/mpeg")},
            headers={"Authorization": f"Bearer {token_dm}"},
        )
        assert blocked_resp.status_code == 429
        assert blocked_resp.headers.get("retry-after") is not None
        assert "Rate limit exceeded" in blocked_resp.json()["detail"]


def test_rate_limiter_disabled_bypass(client):
    """
    When limiter.enabled is False (testing hook), requests beyond the rate limit must succeed.
    """
    limiter.enabled = False

    mock_db = MagicMock()
    mock_users = MagicMock()
    mock_users.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.return_value = mock_users

    from server.db_async import get_database

    app.dependency_overrides[get_database] = lambda: mock_db

    # Send 10 login attempts (limit is normally 5)
    for _ in range(10):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "wrongpassword"},
            headers={"X-Forwarded-For": "10.0.0.99"},
        )
        assert resp.status_code == 401  # Never 429


def test_global_rate_limiting_headers(client):
    """
    Verify that global fallback endpoints return rate limit headers.
    """
    token = create_access_token({"sub": "user_123", "username": "user123"})
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_123", "username": "user123"}
    resp = client.get("/api/v1/rules/classes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.headers.get("x-ratelimit-limit") == "100"
    assert resp.headers.get("x-ratelimit-remaining") is not None
