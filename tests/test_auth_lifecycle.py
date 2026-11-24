"""Integration & security tests for #266 Auth Lifecycle:
- Self-service password change (PBKDF2, demo exclusion, token rotation & old JWT revocation, rate limit)
- Admin one-time password reset (RBAC, self/admin/demo guards, audit logging, forced change lock)
- Optional Discord OAuth2 flow (unconfigured 503/hidden, CSRF state/cookie validation, user creation & email link, handoff replay block)
"""

from typing import Any, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx
import mongomock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.config import settings
from server.db_async import get_database
from server.dependencies.auth import get_current_user_from_token, get_password_hash
from server.main import app
from server.rate_limiter import limiter
from server.routers.auth_router import (
    _USED_OAUTH_HANDOFF_JTIS,
    _exchange_discord_code_and_fetch_profile,
)
from server.routers.websocket_router import manager


class _AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._iter = None

    def __iter__(self):
        return iter(self._cursor)

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Any]:
        docs = list(self._cursor)
        if length is not None:
            docs = docs[:length]
        return docs


class _AsyncCollection:
    def __init__(self, coll):
        self._coll = coll

    async def insert_one(self, *args, **kwargs):
        return self._coll.insert_one(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._coll.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursor(self._coll.find(*args, **kwargs))


class _AsyncDatabase:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str) -> _AsyncCollection:
        return _AsyncCollection(self._db[name])


@pytest.fixture
def mock_db():
    raw_db = mongomock.MongoClient()["phyrexian_auth_test"]
    raw_db["oauth_handoffs"].create_index("jti", unique=True)
    return _AsyncDatabase(raw_db)


@pytest.fixture
def client(mock_db):
    orig_overrides = app.dependency_overrides.copy()
    orig_limiter_enabled = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    _USED_OAUTH_HANDOFF_JTIS.clear()
    app.dependency_overrides[get_database] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides = orig_overrides
    limiter.enabled = orig_limiter_enabled
    limiter.reset()
    _USED_OAUTH_HANDOFF_JTIS.clear()


def _register_and_login(
    client: TestClient,
    username: str,
    password: str = "InitialPass123!",
    email: Optional[str] = None,
):
    reg_payload = {"username": username, "password": password}
    if email:
        reg_payload["email"] = email
    reg = client.post(
        "/api/v1/auth/register",
        json=reg_payload,
        headers={"X-Forwarded-For": "10.10.1.1"},
    )
    assert reg.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"X-Forwarded-For": "10.10.1.2"},
    )
    assert login.status_code == 200
    return login.json()


def test_self_service_change_password_and_token_revocation(client, mock_db):
    login_data = _register_and_login(client, "aria", "OldPassword123!")
    old_token = login_data["access_token"]

    # Wrong current password returns 400 (not 401 so session is not nuked prematurely)
    wrong_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword99!", "new_password": "NewPassword456!"},
        headers={"Authorization": f"Bearer {old_token}", "X-Forwarded-For": "10.2.0.1"},
    )
    assert wrong_res.status_code == 400
    assert "incorrect" in wrong_res.json()["detail"].lower()

    # Same password rejected
    same_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword123!", "new_password": "OldPassword123!"},
        headers={"Authorization": f"Bearer {old_token}", "X-Forwarded-For": "10.2.0.2"},
    )
    assert same_res.status_code == 400

    # Short password rejected by Pydantic validation
    short_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword123!", "new_password": "short"},
        headers={"Authorization": f"Bearer {old_token}", "X-Forwarded-For": "10.2.0.3"},
    )
    assert short_res.status_code == 422

    # Valid password change rotates JWT and bumps token_version
    ok_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword123!", "new_password": "NewPassword456!"},
        headers={"Authorization": f"Bearer {old_token}", "X-Forwarded-For": "10.2.0.4"},
    )
    assert ok_res.status_code == 200
    body = ok_res.json()
    new_token = body["access_token"]
    assert new_token != old_token
    assert body["user"]["must_change_password"] is False
    assert body["user"]["has_password"] is True

    # Old token is immediately revoked via token_version across endpoints
    me_old = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me_old.status_code == 401

    chars_old = client.get("/api/v1/characters/", headers={"Authorization": f"Bearer {old_token}"})
    assert chars_old.status_code == 401

    # Rotated token succeeds
    me_new = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_new.status_code == 200
    assert me_new.json()["username"] == "aria"

    # Old password fails login, new password succeeds
    fail_login = client.post(
        "/api/v1/auth/login",
        data={"username": "aria", "password": "OldPassword123!"},
        headers={"X-Forwarded-For": "10.2.0.5"},
    )
    assert fail_login.status_code == 401
    ok_login = client.post(
        "/api/v1/auth/login",
        data={"username": "aria", "password": "NewPassword456!"},
        headers={"X-Forwarded-For": "10.2.0.6"},
    )
    assert ok_login.status_code == 200


@pytest.mark.anyio
async def test_revoked_token_rejected_by_websocket_token_helper(client, mock_db):
    login_data = _register_and_login(client, "ws_hero", "InitialPass123!")
    old_token = login_data["access_token"]

    res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "InitialPass123!", "new_password": "ChangedPass456!"},
        headers={"Authorization": f"Bearer {old_token}", "X-Forwarded-For": "10.3.0.1"},
    )
    assert res.status_code == 200

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_from_token(old_token, mock_db)
    assert exc_info.value.status_code == 401


def test_websocket_revocation_on_password_change_reset_and_must_change(
    client, mock_db, monkeypatch
):
    async def _get_mock_db():
        return mock_db

    monkeypatch.setattr("server.routers.websocket_router.get_database", _get_mock_db)
    monkeypatch.setattr("server.dependencies.auth.get_database", _get_mock_db)

    # Admin + player + campaign membership
    _register_and_login(client, "ws_admin", "AdminPass123!")
    mock_db["users"]._coll.update_one({"username": "ws_admin"}, {"$set": {"is_admin": True}})
    admin_tok = client.post(
        "/api/v1/auth/login",
        data={"username": "ws_admin", "password": "AdminPass123!"},
        headers={"X-Forwarded-For": "10.3.1.1"},
    ).json()["access_token"]

    p_login = _register_and_login(client, "ws_player", "PlayerPass123!")
    p_tok = p_login["access_token"]
    p_uid = p_login["user"]["id"]
    mock_db["campaign_members"]._coll.insert_one(
        {"campaign_id": "test_camp", "user_id": p_uid, "role": "player"}
    )

    try:
        # 1. Connect active WebSocket, then change password -> active socket closed with 1008
        with client.websocket_connect("/ws/campaigns/test_camp") as ws:
            ws.send_json({"type": "auth", "token": p_tok})
            assert ws.receive_json()["type"] == "presence_sync"

            chg = client.post(
                "/api/v1/auth/change-password",
                json={"current_password": "PlayerPass123!", "new_password": "PlayerPass456!"},
                headers={"Authorization": f"Bearer {p_tok}", "X-Forwarded-For": "10.3.1.2"},
            )
            assert chg.status_code == 200
            new_tok = chg.json()["access_token"]

            with pytest.raises(WebSocketDisconnect) as ws_err:
                while True:
                    ws.receive_json()
            assert ws_err.value.code == 1008

        # 2. Reconnect with rotated token, then admin resets password -> active socket closed with 1008
        with client.websocket_connect("/ws/campaigns/test_camp") as ws2:
            ws2.send_json({"type": "auth", "token": new_tok})
            assert ws2.receive_json()["type"] == "presence_sync"

            rst = client.post(
                f"/api/v1/admin/users/{p_uid}/reset-password",
                headers={"Authorization": f"Bearer {admin_tok}"},
            )
            assert rst.status_code == 200
            temp_pwd = rst.json()["temporary_password"]

            with pytest.raises(WebSocketDisconnect) as ws_err2:
                while True:
                    ws2.receive_json()
            assert ws_err2.value.code == 1008

        # 3. Attempting new WebSocket with temporary password JWT (must_change_password=True) closes 1008
        temp_tok = client.post(
            "/api/v1/auth/login",
            data={"username": "ws_player", "password": temp_pwd},
            headers={"X-Forwarded-For": "10.3.1.3"},
        ).json()["access_token"]
        with client.websocket_connect("/ws/campaigns/test_camp") as ws3:
            ws3.send_json({"type": "auth", "token": temp_tok})
            with pytest.raises(WebSocketDisconnect) as ws_err3:
                ws3.receive_json()
            assert ws_err3.value.code == 1008
    finally:
        manager.active_connections.clear()


def test_change_password_blocks_demo_accounts_and_enforces_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "DEBUG_MODE", True)
    demo_res = client.post(
        "/api/v1/auth/demo",
        json={"demo_type": "mitsos"},
        headers={"X-Forwarded-For": "10.4.0.1"},
    )
    assert demo_res.status_code == 200
    demo_token = demo_res.json()["access_token"]
    assert demo_res.json()["user"]["is_demo"] is True

    blocked = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "demo", "new_password": "NewDemoPassword1!"},
        headers={"Authorization": f"Bearer {demo_token}", "X-Forwarded-For": "10.4.0.2"},
    )
    assert blocked.status_code == 403

    # Verify rate limit on /change-password (5/minute default)
    user_login = _register_and_login(client, "ratelimit_user", "ValidPassword1!")
    tok = user_login["access_token"]
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongPassword!", "new_password": "AnotherPass123!"},
            headers={"Authorization": f"Bearer {tok}", "X-Forwarded-For": "10.4.0.99"},
        )
        assert resp.status_code == 400
    rl_resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword!", "new_password": "AnotherPass123!"},
        headers={"Authorization": f"Bearer {tok}", "X-Forwarded-For": "10.4.0.99"},
    )
    assert rl_resp.status_code == 429


def test_admin_password_reset_rbac_guards_and_forced_change_flow(client, mock_db):
    # Create player, regular non-admin user2, second admin, and primary admin
    player_login = _register_and_login(client, "forgetful_player", "OldPass123!")
    player_token = player_login["access_token"]
    player_id = player_login["user"]["id"]

    _register_and_login(client, "second_admin", "AdminPass123!")
    mock_db["users"]._coll.update_one({"username": "second_admin"}, {"$set": {"is_admin": True}})

    _register_and_login(client, "main_admin", "MainAdminPass123!")
    mock_db["users"]._coll.update_one({"username": "main_admin"}, {"$set": {"is_admin": True}})
    main_admin_login = client.post(
        "/api/v1/auth/login",
        data={"username": "main_admin", "password": "MainAdminPass123!"},
        headers={"X-Forwarded-For": "10.5.0.10"},
    ).json()
    admin_token = main_admin_login["access_token"]
    admin_id = main_admin_login["user"]["id"]

    # 1. Non-admin cannot call reset-password -> 403
    non_admin = client.post(
        f"/api/v1/admin/users/{player_id}/reset-password",
        headers={"Authorization": f"Bearer {player_token}"},
    )
    assert non_admin.status_code == 403

    # 2. Admin cannot reset self -> 400
    self_reset = client.post(
        f"/api/v1/admin/users/{admin_id}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert self_reset.status_code == 400

    # 3. Admin cannot reset another admin -> 403
    other_admin = client.post(
        "/api/v1/admin/users/local_user_second_admin/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert other_admin.status_code == 403

    # 4. Admin cannot reset demo account -> 400
    mock_db["users"]._coll.insert_one(
        {
            "id": "local_user_mitsos",
            "username": "mitsos",
            "password_hash": "demo",
            "is_demo": True,
            "is_admin": False,
        }
    )
    demo_reset = client.post(
        "/api/v1/admin/users/local_user_mitsos/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert demo_reset.status_code == 400

    # 5. Missing user -> 404
    missing_reset = client.post(
        "/api/v1/admin/users/nonexistent_user/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert missing_reset.status_code == 404

    # 6. Admin resets forgetful_player -> returns temp password & revokes old token
    reset_res = client.post(
        f"/api/v1/admin/users/{player_id}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reset_res.status_code == 200
    reset_body = reset_res.json()
    temp_password = reset_body["temporary_password"]
    assert len(temp_password) >= 12
    assert reset_body["must_change_password"] is True

    # Audit log written without plaintext password
    audit_entry = mock_db["admin_audit_log"]._coll.find_one(
        {"action": "reset_user_password", "target_user_id": player_id}
    )
    assert audit_entry is not None
    assert temp_password not in str(audit_entry)

    # Prior player JWT immediately revoked
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {player_token}"}
        ).status_code
        == 401
    )

    # Admin list reflects must_change_password flag
    list_res = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_res.status_code == 200
    listed_player = next(u for u in list_res.json()["users"] if u["id"] == player_id)
    assert listed_player["must_change_password"] is True

    # 7. Player signs in with temp password -> forced change mode
    temp_login = client.post(
        "/api/v1/auth/login",
        data={"username": "forgetful_player", "password": temp_password},
        headers={"X-Forwarded-For": "10.5.0.20"},
    )
    assert temp_login.status_code == 200
    temp_jwt = temp_login.json()["access_token"]
    assert temp_login.json()["user"]["must_change_password"] is True

    # /auth/me works so UI knows to force password change, while /characters/ is blocked (403)
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {temp_jwt}"}).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/characters/", headers={"Authorization": f"Bearer {temp_jwt}"}
        ).status_code
        == 403
    )

    # 8. Player changes password -> clears must_change_password & unlocks endpoints
    unlock_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temp_password, "new_password": "FinalStrongPassword1!"},
        headers={"Authorization": f"Bearer {temp_jwt}", "X-Forwarded-For": "10.5.0.21"},
    )
    assert unlock_res.status_code == 200
    unlocked_jwt = unlock_res.json()["access_token"]
    assert unlock_res.json()["user"]["must_change_password"] is False

    # Now character endpoints unlock cleanly
    assert (
        client.get(
            "/api/v1/characters/", headers={"Authorization": f"Bearer {unlocked_jwt}"}
        ).status_code
        == 200
    )


def test_discord_oauth_hidden_and_disabled_without_env_vars(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "")
    monkeypatch.setattr(settings, "DISCORD_CLIENT_SECRET", "")

    providers = client.get("/api/v1/auth/providers")
    assert providers.status_code == 200
    assert providers.json() == {"local": True, "discord": False}

    assert client.get("/api/v1/auth/discord/login", follow_redirects=False).status_code == 503
    assert client.get("/api/v1/auth/discord/callback", follow_redirects=False).status_code == 503
    assert client.post("/api/v1/auth/discord/exchange", json={"code": "abc"}).status_code == 503


def test_discord_oauth_full_flow_csrf_replay_and_no_pre_hijack(client, mock_db, monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "discord-client-id-123")
    monkeypatch.setattr(settings, "DISCORD_CLIENT_SECRET", "discord-client-secret-xyz")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:4200")
    monkeypatch.setattr(
        settings, "DISCORD_REDIRECT_URI", "http://localhost:4200/api/v1/auth/discord/callback"
    )

    providers = client.get("/api/v1/auth/providers")
    assert providers.status_code == 200
    assert providers.json() == {"local": True, "discord": True}

    # 1. Start OAuth login -> 302 to Discord with signed state + nonce cookie (Secure via trusted X-Forwarded-Proto)
    login_resp = client.get(
        "/api/v1/auth/discord/login",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.1", "X-Forwarded-Proto": "https"},
    )
    assert login_resp.status_code == 302
    loc = login_resp.headers["location"]
    assert loc.startswith("https://discord.com/api/oauth2/authorize")
    state_param = parse_qs(urlparse(loc).query)["state"][0]
    assert state_param
    assert "pf_discord_oauth_nonce" in login_resp.cookies
    set_cookie_hdr = login_resp.headers.get("set-cookie", "")
    assert "Secure" in set_cookie_hdr

    # 2. Tampered CSRF state rejected -> redirects cleanly to /login?oauth_error=...
    tampered_resp = client.get(
        "/api/v1/auth/discord/callback?code=fake&state=tampered.state.jwt",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.2"},
    )
    assert tampered_resp.status_code == 302
    assert "/login?oauth_error=" in tampered_resp.headers["location"]

    # 3. Mock Discord profile exchange -> creates passwordless user and issues single-use handoff code
    async def _fake_exchange(code: str, redirect_uri: str) -> dict:
        assert code == "discord-auth-code"
        return {
            "id": "9988776655",
            "username": "jace.beleren",
            "global_name": "Jace Beleren",
            "email": "jace@ravnica.plane",
            "verified": True,
        }

    monkeypatch.setattr(
        "server.routers.auth_router._exchange_discord_code_and_fetch_profile",
        _fake_exchange,
    )

    # Restore valid nonce cookie on TestClient after tampered callback cleared it
    login_resp2 = client.get(
        "/api/v1/auth/discord/login",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.3"},
    )
    state2 = parse_qs(urlparse(login_resp2.headers["location"]).query)["state"][0]

    cb_resp = client.get(
        f"/api/v1/auth/discord/callback?code=discord-auth-code&state={state2}",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.4"},
    )
    assert cb_resp.status_code == 302
    cb_location = cb_resp.headers["location"]
    assert cb_location.startswith("http://localhost:4200/auth/callback#code=")
    handoff_code = cb_location.split("#code=", 1)[1]

    # Security: Handoff JWT MUST NOT act as a Bearer session token (before OR after exchange)
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {handoff_code}"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/characters/", headers={"Authorization": f"Bearer {handoff_code}"}
        ).status_code
        == 401
    )

    # 4. Exchange handoff code for Forge JWT + verify single-use replay rejection (memory + cross-worker DB DuplicateKeyError)
    exchange_res = client.post(
        "/api/v1/auth/discord/exchange",
        json={"code": handoff_code},
        headers={"X-Forwarded-For": "10.6.0.5"},
    )
    assert exchange_res.status_code == 200
    ex_data = exchange_res.json()
    assert ex_data["user"]["username"] == "jace_beleren"
    assert ex_data["user"]["has_password"] is False
    assert ex_data["user"]["auth_providers"] == ["discord"]
    assert mock_db["oauth_handoffs"]._coll.count_documents({}) == 1

    # Handoff JWT remains rejected as Bearer even after successful exchange
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {handoff_code}"}
        ).status_code
        == 401
    )

    # In-memory replay blocked
    replay_res = client.post(
        "/api/v1/auth/discord/exchange",
        json={"code": handoff_code},
        headers={"X-Forwarded-For": "10.6.0.6"},
    )
    assert replay_res.status_code == 401

    # Simulate second worker where in-memory cache is cold -> DB unique index DuplicateKeyError rejects replay
    _USED_OAUTH_HANDOFF_JTIS.clear()
    cross_worker_replay = client.post(
        "/api/v1/auth/discord/exchange",
        json={"code": handoff_code},
        headers={"X-Forwarded-For": "10.6.0.61"},
    )
    assert cross_worker_replay.status_code == 401

    # 5. Discord-only user can set an initial local password without current_password
    set_pwd = client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "MindSculptor99!"},
        headers={
            "Authorization": f"Bearer {ex_data['access_token']}",
            "X-Forwarded-For": "10.6.0.7",
        },
    )
    assert set_pwd.status_code == 200
    assert set_pwd.json()["user"]["has_password"] is True
    assert set(set_pwd.json()["user"]["auth_providers"]) == {"local", "discord"}

    # 6. Security: Existing local account with same email MUST NOT be pre-hijacked even when Discord email verified=True
    local_user_doc = {
        "id": "local_user_chandra",
        "username": "chandra",
        "password_hash": get_password_hash("Fireball123!"),
        "email": "chandra@kaladesh.plane",
        "name": "Chandra Nalaar",
        "has_completed_tutorial": True,
        "is_admin": False,
        "role": "player",
        "is_demo": False,
        "token_version": 0,
    }
    mock_db["users"]._coll.insert_one(local_user_doc)

    async def _fake_exchange_verified_collision(code: str, redirect_uri: str) -> dict:
        return {
            "id": "1122334455",
            "username": "chandra_discord",
            "global_name": "Chandra",
            "email": "CHANDRA@kaladesh.plane",
            "verified": True,
        }

    monkeypatch.setattr(
        "server.routers.auth_router._exchange_discord_code_and_fetch_profile",
        _fake_exchange_verified_collision,
    )

    login_resp3 = client.get(
        "/api/v1/auth/discord/login",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.8"},
    )
    state3 = parse_qs(urlparse(login_resp3.headers["location"]).query)["state"][0]
    cb_verified = client.get(
        f"/api/v1/auth/discord/callback?code=link-code&state={state3}",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.9"},
    )
    handoff_verified = cb_verified.headers["location"].split("#code=", 1)[1]
    ex_verified = client.post(
        "/api/v1/auth/discord/exchange",
        json={"code": handoff_verified},
        headers={"X-Forwarded-For": "10.6.0.10"},
    )
    assert ex_verified.status_code == 200
    assert ex_verified.json()["user"]["id"] == "discord_user_1122334455"
    assert ex_verified.json()["user"]["auth_providers"] == ["discord"]
    assert ex_verified.json()["user"]["email"] == "CHANDRA@kaladesh.plane"
    untouched_local = mock_db["users"]._coll.find_one({"id": "local_user_chandra"})
    assert untouched_local.get("discord_id") is None

    # 7. Unverified Discord email (verified=False) is discarded (stored as None)
    async def _fake_exchange_unverified(code: str, redirect_uri: str) -> dict:
        return {
            "id": "5566778899",
            "username": "liliana.vess",
            "global_name": "Liliana",
            "email": "liliana@innistrad.plane",
            "verified": False,
        }

    monkeypatch.setattr(
        "server.routers.auth_router._exchange_discord_code_and_fetch_profile",
        _fake_exchange_unverified,
    )
    login_resp4 = client.get(
        "/api/v1/auth/discord/login",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.11"},
    )
    state4 = parse_qs(urlparse(login_resp4.headers["location"]).query)["state"][0]
    cb_unv = client.get(
        f"/api/v1/auth/discord/callback?code=unv-code&state={state4}",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.6.0.12"},
    )
    handoff_unv = cb_unv.headers["location"].split("#code=", 1)[1]

    # Fail-closed check: DB persistence error rejects exchange & rolls back in-memory JTI
    orig_insert = mock_db["oauth_handoffs"]._coll.insert_one

    def _failing_insert(*args, **kwargs):
        raise RuntimeError("Simulated Mongo write outage")

    mock_db["oauth_handoffs"]._coll.insert_one = _failing_insert
    fail_closed_res = client.post(
        "/api/v1/auth/discord/exchange",
        json={"code": handoff_unv},
        headers={"X-Forwarded-For": "10.6.0.13"},
    )
    assert fail_closed_res.status_code == 401
    mock_db["oauth_handoffs"]._coll.insert_one = orig_insert

    # Now DB is healthy again -> same valid unused code can still complete cleanly!
    ex_unv = client.post(
        "/api/v1/auth/discord/exchange",
        json={"code": handoff_unv},
        headers={"X-Forwarded-For": "10.6.0.14"},
    )
    assert ex_unv.status_code == 200
    assert ex_unv.json()["user"]["email"] is None


def test_admin_reset_password_supports_legacy_idless_users(client, mock_db):
    _register_and_login(client, "legacy_admin", "AdminPass123!")
    mock_db["users"]._coll.update_one({"username": "legacy_admin"}, {"$set": {"is_admin": True}})
    admin_tok = client.post(
        "/api/v1/auth/login",
        data={"username": "legacy_admin", "password": "AdminPass123!"},
        headers={"X-Forwarded-For": "10.7.0.1"},
    ).json()["access_token"]

    mock_db["users"]._coll.insert_one(
        {
            "username": "legacy_idless",
            "password_hash": get_password_hash("OldPass123!"),
            "is_admin": False,
        }
    )

    reset_res = client.post(
        "/api/v1/admin/users/local_user_legacy_idless/reset-password",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["username"] == "legacy_idless"
    temp_pwd = reset_res.json()["temporary_password"]
    updated = mock_db["users"]._coll.find_one({"username": "legacy_idless"})
    assert updated["must_change_password"] is True

    # Legacy id-less user logs in with temp password and completes forced /change-password without 500
    temp_login = client.post(
        "/api/v1/auth/login",
        data={"username": "legacy_idless", "password": temp_pwd},
        headers={"X-Forwarded-For": "10.7.0.2"},
    )
    assert temp_login.status_code == 200
    temp_tok = temp_login.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {temp_tok}"})
    assert me_res.status_code == 200
    assert me_res.json()["id"] == "local_user_legacy_idless"

    assert (
        client.get(
            "/api/v1/characters/", headers={"Authorization": f"Bearer {temp_tok}"}
        ).status_code
        == 403
    )

    chg_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temp_pwd, "new_password": "LegacyNewPassword99!"},
        headers={"Authorization": f"Bearer {temp_tok}", "X-Forwarded-For": "10.7.0.3"},
    )
    assert chg_res.status_code == 200
    unlocked_tok = chg_res.json()["access_token"]
    assert chg_res.json()["user"]["must_change_password"] is False
    assert (
        client.get(
            "/api/v1/characters/", headers={"Authorization": f"Bearer {unlocked_tok}"}
        ).status_code
        == 200
    )


def test_handoff_jwt_rejected_by_websocket_endpoint(client, mock_db, monkeypatch):
    async def _get_mock_db():
        return mock_db

    monkeypatch.setattr("server.routers.websocket_router.get_database", _get_mock_db)
    monkeypatch.setattr("server.dependencies.auth.get_database", _get_mock_db)
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "DISCORD_CLIENT_SECRET", "csec")

    async def _fake_exchange(code: str, redirect_uri: str) -> dict:
        return {
            "id": "ws_discord_42",
            "username": "nissa",
            "global_name": "Nissa",
            "email": "nissa@zendikar.plane",
            "verified": True,
        }

    monkeypatch.setattr(
        "server.routers.auth_router._exchange_discord_code_and_fetch_profile",
        _fake_exchange,
    )

    login_resp = client.get(
        "/api/v1/auth/discord/login",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.8.0.1"},
    )
    state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]
    cb_resp = client.get(
        f"/api/v1/auth/discord/callback?code=c&state={state}",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.8.0.2"},
    )
    handoff_jwt = cb_resp.headers["location"].split("#code=", 1)[1]
    mock_db["campaign_members"]._coll.insert_one(
        {"campaign_id": "zen", "user_id": "discord_user_ws_discord_42", "role": "player"}
    )

    with client.websocket_connect("/ws/campaigns/zen") as ws:
        ws.send_json({"type": "auth", "token": handoff_jwt})
        with pytest.raises(WebSocketDisconnect) as ws_err:
            ws.receive_json()
        assert ws_err.value.code == 1008


@pytest.mark.anyio
async def test_exchange_discord_code_and_fetch_profile_with_mock_transport(monkeypatch):
    monkeypatch.setattr(settings, "DISCORD_CLIENT_ID", "cid-mock")
    monkeypatch.setattr(settings, "DISCORD_CLIENT_SECRET", "csec-mock")
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append((request.method, str(request.url), dict(request.headers)))
        if str(request.url) == "https://discord.com/api/oauth2/token":
            assert request.method == "POST"
            return httpx.Response(
                200,
                json={"access_token": "discord-access-tok", "token_type": "Bearer"},
            )
        if str(request.url) == "https://discord.com/api/users/@me":
            assert request.headers.get("authorization") == "Bearer discord-access-tok"
            return httpx.Response(
                200,
                json={
                    "id": "42",
                    "username": "urza",
                    "email": "urza@dominaria.plane",
                    "verified": True,
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    profile = await _exchange_discord_code_and_fetch_profile(
        code="auth-code-123",
        redirect_uri="http://localhost:4200/api/v1/auth/discord/callback",
        transport=transport,
    )
    assert profile["id"] == "42"
    assert profile["username"] == "urza"
    assert len(seen_requests) == 2

    def failing_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(Exception):
        await _exchange_discord_code_and_fetch_profile(
            code="bad-code",
            redirect_uri="http://localhost:4200/api/v1/auth/discord/callback",
            transport=httpx.MockTransport(failing_handler),
        )
