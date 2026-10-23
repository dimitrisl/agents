import io
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2024
from backend.services.forge_service import analyze_level_up
from backend.utils.pdf_exporter import PORTRAIT_DIR, create_image_overlay
from server.config import _generate_dev_secret, settings
from server.db_async import INDEX_DEFINITIONS, get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import get_real_ip, get_user_or_ip_key, is_trusted_proxy, limiter
from server.routers.campaign_router import _authorize_roll_request_target


# --- 1. [TICKET-P0-02] JWT Secret Key Hardening ---
def test_jwt_dev_secret_length_and_rfc7518_compliance():
    """Verify that generated dev secret is at least 32 bytes (eliminates RFC 7518 warning)."""
    import warnings

    secret = _generate_dev_secret()
    assert isinstance(secret, str)
    assert len(secret.encode("utf-8")) >= 32

    # Verify no InsecureKeyLengthWarning when encoding/decoding JWT
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        token = jwt.encode({"sub": "user_test"}, secret, algorithm="HS256")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        assert decoded["sub"] == "user_test"

    insecure_warnings = [
        w for w in record if "InsecureKeyLengthWarning" in str(w.category.__name__)
    ]
    assert len(insecure_warnings) == 0


# --- 2. [TICKET-P0-03] Rate Limiter Security ---
def test_rate_limiter_rejects_expired_token():
    """Expired JWT must not be used to claim a user bucket; must fallback to IP."""
    expired_payload = {
        "sub": "attacker_user",
        "exp": int(time.time()) - 3600,  # 1 hour ago
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    mock_request = MagicMock()
    mock_request.headers = {
        "authorization": f"Bearer {expired_token}",
    }
    mock_request.client.host = "192.168.1.100"

    key = get_user_or_ip_key(mock_request)
    assert key.startswith("ip:"), f"Expected IP key for expired token, got: {key}"
    assert "user:attacker_user" not in key


def test_rate_limiter_rejects_token_without_exp():
    """JWT without 'exp' claim must be rejected and fallback to IP."""
    no_exp_payload = {
        "sub": "forged_user",
    }
    no_exp_token = jwt.encode(no_exp_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    mock_request = MagicMock()
    mock_request.headers = {
        "authorization": f"Bearer {no_exp_token}",
    }
    mock_request.client.host = "192.168.1.100"

    key = get_user_or_ip_key(mock_request)
    assert key.startswith("ip:"), f"Expected IP key for token without exp, got: {key}"
    assert "user:forged_user" not in key


def test_rate_limiter_accepts_valid_token_and_case_insensitive_bearer():
    """Valid JWT token uses user identity bucket, even with lowercase 'bearer' prefix."""
    valid_payload = {
        "sub": "legit_user",
        "exp": int(time.time()) + 3600,
    }
    valid_token = jwt.encode(valid_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # 1. Standard "Bearer "
    mock_request = MagicMock()
    mock_request.headers = {
        "authorization": f"Bearer {valid_token}",
    }
    mock_request.client.host = "192.168.1.100"
    assert get_user_or_ip_key(mock_request) == "user:legit_user"

    # 2. Lowercase "bearer "
    mock_request.headers = {
        "authorization": f"bearer {valid_token}",
    }
    assert get_user_or_ip_key(mock_request) == "user:legit_user"


def test_rate_limiter_proxy_safety():
    """Untrusted client sending spoofed X-Forwarded-For must be ignored; trusted proxy honored."""
    # 1. Untrusted peer IP
    untrusted_request = MagicMock()
    untrusted_request.client.host = "203.0.113.195"
    untrusted_request.headers = {"x-forwarded-for": "10.0.0.1"}

    assert not is_trusted_proxy("203.0.113.195")
    ip = get_real_ip(untrusted_request)
    assert ip == "203.0.113.195"

    # 2. Trusted proxy peer IP (127.0.0.1) with X-Forwarded-For
    trusted_request = MagicMock()
    trusted_request.client.host = "127.0.0.1"
    trusted_request.headers = {"x-forwarded-for": "198.51.100.42"}

    assert is_trusted_proxy("127.0.0.1")
    ip = get_real_ip(trusted_request)
    assert ip == "198.51.100.42"

    # 3. Trusted proxy with X-Real-IP header
    real_ip_request = MagicMock()
    real_ip_request.client.host = "127.0.0.1"
    real_ip_request.headers = {"x-real-ip": "198.51.100.99"}

    ip = get_real_ip(real_ip_request)
    assert ip == "198.51.100.99"


# --- 3. [TICKET-P1-04] Campaign Assets IDOR & Tenancy Protection ---
def test_campaign_assets_idor_protection():
    """Unauthenticated or non-campaign members cannot fetch campaign assets."""
    client = TestClient(app)

    # 1. Unauthenticated request
    resp = client.get("/api/v1/campaigns/SecretCampaign/assets/map.png")
    assert resp.status_code == 401

    # 2. Authenticated but not a member of SecretCampaign
    mock_db = MagicMock()
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: (
        mock_members if k == "campaign_members" else MagicMock()
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "stranger", "username": "stranger"}
    app.dependency_overrides[get_database] = lambda: mock_db

    try:
        resp = client.get("/api/v1/campaigns/SecretCampaign/assets/map.png")
        assert resp.status_code == 403
        assert "not a member" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# --- 4. [TICKET-P1-07] Campaign Deletion Authorization & Creator Ownership ---
def test_campaign_deletion_only_by_owner():
    """Invited co-DMs cannot delete the campaign; only the original campaign creator can."""
    client = TestClient(app)

    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_members = MagicMock()

    # Campaign is owned by user "creator_dm"
    camp_doc = {
        "campaign_name": "DragonHeist",
        "owner_id": "creator_dm",
    }
    mock_campaigns.find_one = AsyncMock(return_value=camp_doc)
    mock_campaigns.delete_one = AsyncMock(return_value=MagicMock())

    # User is invited co-DM "co_dm_123"
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "DragonHeist", "user_id": "co_dm_123", "role": "dm"}
    )
    mock_members.delete_many = AsyncMock(return_value=MagicMock())

    mock_db.__getitem__.side_effect = lambda k: {
        "campaigns": mock_campaigns,
        "campaign_members": mock_members,
        "campaign_whispers": MagicMock(delete_many=AsyncMock(), update_many=AsyncMock()),
        "campaign_roll_requests": MagicMock(delete_many=AsyncMock()),
        "campaign_encounters": MagicMock(delete_many=AsyncMock()),
        "campaign_entities": MagicMock(delete_many=AsyncMock()),
        "session_logs": MagicMock(delete_many=AsyncMock()),
        "campaign_skeletons": MagicMock(delete_many=AsyncMock()),
        "homebrew_content": MagicMock(delete_many=AsyncMock()),
        "characters": MagicMock(update_many=AsyncMock()),
    }.get(k, MagicMock())

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"id": "co_dm_123", "username": "co_dm"}

    try:
        # 1. Co-DM attempt must be refused (403)
        resp = client.delete("/api/v1/campaigns/DragonHeist")
        assert resp.status_code == 403
        assert "creator" in resp.json()["detail"].lower()

        # 2. Creator DM attempt must succeed (200)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "creator_dm",
            "username": "creator",
        }
        mock_members.find_one = AsyncMock(
            return_value={"campaign_id": "DragonHeist", "user_id": "creator_dm", "role": "dm"}
        )

        with patch("server.routers.websocket_router.manager.broadcast", new=AsyncMock()):
            resp = client.delete("/api/v1/campaigns/DragonHeist")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
    finally:
        app.dependency_overrides.clear()


# --- 5. [TICKET-P1-10] Campaign Join Rate Limiting & Invite Code Entropy ---
def test_campaign_join_rate_limiting_and_invite_code():
    """Verify join_campaign_by_code rate limiting (5/min) and high entropy invite code."""
    limiter.enabled = True
    limiter.reset()

    client = TestClient(app)

    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_members = MagicMock()
    mock_chars = MagicMock()

    mock_campaigns.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda k: {
        "campaigns": mock_campaigns,
        "campaign_members": mock_members,
        "characters": mock_chars,
    }.get(k, MagicMock())

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"id": "joiner_1", "username": "joiner"}

    try:
        # First 5 join attempts (fail with 404 since invite code not found)
        for i in range(5):
            resp = client.post(
                "/api/v1/campaigns/join",
                json={"invite_code": f"bad_code_{i}", "char_filename": "char_1.json"},
                headers={"X-Forwarded-For": "10.10.10.10"},
            )
            assert resp.status_code == 404, f"Attempt {i + 1} status: {resp.status_code}"

        # 6th attempt from the same IP must be 429 Too Many Requests
        blocked_resp = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "bad_code_blocked", "char_filename": "char_1.json"},
            headers={"X-Forwarded-For": "10.10.10.10"},
        )
        assert blocked_resp.status_code == 429
        assert "Rate limit exceeded" in blocked_resp.json()["detail"]
    finally:
        limiter.reset()
        app.dependency_overrides.clear()


def test_invite_code_entropy_and_sparse_unique_index():
    """Verify invite code entropy is >= 16 characters and unique sparse index exists."""
    # Test index definition in server/db_async.py
    index_entry = next(
        (
            item
            for item in INDEX_DEFINITIONS
            if item[0] == "campaigns" and item[1] == [("invite_code", 1)]
        ),
        None,
    )
    assert index_entry is not None, "Unique sparse index on campaigns.invite_code not found!"
    _, _, kwargs = index_entry
    assert kwargs.get("unique") is True
    assert kwargs.get("sparse") is True

    # Test invite code generation endpoint
    client = TestClient(app)
    mock_db = MagicMock()
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(
        return_value={"campaign_name": "Neverwinter", "owner_id": "dm_1"}
    )
    mock_campaigns.update_one = AsyncMock(return_value=MagicMock())

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "Neverwinter", "user_id": "dm_1", "role": "dm"}
    )

    mock_db.__getitem__.side_effect = lambda k: {
        "campaigns": mock_campaigns,
        "campaign_members": mock_members,
    }.get(k, MagicMock())

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}

    try:
        resp = client.post("/api/v1/campaigns/Neverwinter/invite-code")
        assert resp.status_code == 200
        code = resp.json()["invite_code"]
        assert len(code) >= 16, f"Expected 16+ chars token_urlsafe(12), got {len(code)}: {code}"
    finally:
        app.dependency_overrides.clear()


# --- 6. [TICKET-P1-11] Roll Request Resolution Authorization Default-Deny ---
@pytest.mark.anyio
async def test_roll_request_authorization_default_deny():
    """Default-deny: unauthorized caller must receive 403 Forbidden."""
    mock_db = MagicMock()
    mock_chars = MagicMock()
    mock_db.__getitem__.return_value = mock_chars

    # 1. Target character belongs to user_alpha
    target_char = {"char_id": "char_99", "char_name": "Thorin", "owner_id": "user_alpha"}
    mock_chars.find_one = AsyncMock(return_value=target_char)

    target_req = {"char_filename": "thorin_char_99.json", "char_name": "Thorin"}
    current_user_beta = {"id": "user_beta", "username": "beta"}
    member_beta = {"role": "player"}

    # Must raise 403 when user_beta attempts to resolve user_alpha's roll request
    with pytest.raises(HTTPException) as exc_info:
        await _authorize_roll_request_target(
            mock_db, "Campaign1", target_req, current_user_beta, member_beta
        )
    assert exc_info.value.status_code == 403
    assert "Not authorized to act on this roll request" in exc_info.value.detail

    # 2. Character owner user_alpha is authorized
    current_user_alpha = {"id": "user_alpha", "username": "alpha"}
    # Should not raise
    await _authorize_roll_request_target(
        mock_db, "Campaign1", target_req, current_user_alpha, member_beta
    )

    # 3. DM is always authorized
    member_dm = {"role": "dm"}
    await _authorize_roll_request_target(
        mock_db, "Campaign1", target_req, current_user_beta, member_dm
    )

    # 4. Target character not found and does not match caller identity -> default-deny 403
    mock_chars.find_one = AsyncMock(return_value=None)
    unknown_req = {"char_filename": "stranger_c99.json", "char_name": "Stranger"}
    with pytest.raises(HTTPException) as exc_info:
        await _authorize_roll_request_target(
            mock_db, "Campaign1", unknown_req, current_user_beta, member_beta
        )
    assert exc_info.value.status_code == 403


# --- 7. [TICKET-P1-06] Character PDF Exporter Local Portraits ---
def test_pdf_exporter_local_portrait_resolution(tmp_path):
    """Local portraits in PORTRAIT_DIR must be loaded safely; path traversal & edge cases blocked."""
    test_portrait_filename = "test_avatar_123.png"
    target_dir = os.path.abspath(PORTRAIT_DIR)
    os.makedirs(target_dir, exist_ok=True)
    portrait_path = os.path.join(target_dir, test_portrait_filename)

    from PIL import Image

    img = Image.new("RGB", (30, 30), color="blue")
    img.save(portrait_path, format="PNG")

    try:
        # 1. Test local API URL format: /api/v1/portraits/{filename}
        overlay_stream = create_image_overlay(f"/api/v1/portraits/{test_portrait_filename}")
        assert overlay_stream is not None
        assert isinstance(overlay_stream, io.BytesIO)

        # 2. Test full URL format: http://localhost:8000/api/v1/portraits/{filename}
        overlay_stream_full = create_image_overlay(
            f"http://localhost:8000/api/v1/portraits/{test_portrait_filename}"
        )
        assert overlay_stream_full is not None

        # 3. Test path traversal is blocked
        blocked_overlay = create_image_overlay("../../etc/passwd")
        assert blocked_overlay is None

        # 4. Test URL-encoded path traversal is blocked
        blocked_encoded = create_image_overlay(
            "http://localhost:8000/api/v1/portraits/%2e%2e%2fetc%2fpasswd"
        )
        assert blocked_encoded is None

        # 5. Test None and empty inputs return None gracefully without raising
        assert create_image_overlay(None) is None
        assert create_image_overlay("") is None
    finally:
        if os.path.exists(portrait_path):
            os.remove(portrait_path)


# --- 9. [TICKET-P1-12] Bard Magical Secrets Spell Pre-filtering ---
def test_bard_magical_secrets_bypasses_class_filter():
    """Bard Magical Secrets at level 10 must allow spells from any class <= max_spell_level."""
    bard_level_9 = {
        "char_name": "Elan",
        "char_level": 9,
        "char_class": "Bard",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 12, "WIS": 10, "CHA": 18},
        "hit_dice": "d8",
        "hp_max": 57,
        "proficiency_bonus": 4,
        "features_traits": [],
    }

    # Level up from 9 to 10
    payload = analyze_level_up(bard_level_9)
    choices = payload.get("choices_required", [])

    secret_1 = next((c for c in choices if c.get("type") == "spell_secret_1"), None)
    secret_2 = next((c for c in choices if c.get("type") == "spell_secret_2"), None)

    assert secret_1 is not None, "Magical Secrets choice 1 missing at level 10"
    assert secret_2 is not None, "Magical Secrets choice 2 missing at level 10"

    secret_options = secret_1["options"]
    assert len(secret_options) > 0

    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    all_spells = repo.get_all_spells(EDITION_2024)
    # Check case-insensitively for spells truly not available to bards
    non_bard_spells = [
        s["name"]
        for s in all_spells
        if s.get("level", 0) <= 5 and "bard" not in [c.lower() for c in s.get("classes", [])]
    ]

    # Non-bard spells (e.g. Fireball) must be available in Magical Secrets
    overlap = set(secret_options).intersection(set(non_bard_spells))
    assert len(overlap) > 0, (
        f"Magical Secrets options should include non-Bard spells, but none were found! "
        f"Sample non-bard: {non_bard_spells[:5]}"
    )
    assert "Fireball" in secret_options

    # Also verify regular Bard level up (level 1 -> 2) includes Bard spells and excludes Wizard-only spells
    bard_level_1 = {
        "char_name": "Elan",
        "char_level": 1,
        "char_class": "Bard",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 12, "WIS": 10, "CHA": 18},
        "hit_dice": "d8",
        "hp_max": 9,
        "proficiency_bonus": 2,
        "features_traits": [],
    }
    lvl2_payload = analyze_level_up(bard_level_1)
    lvl2_choices = lvl2_payload.get("choices_required", [])
    spell_choice = next((c for c in lvl2_choices if c.get("type") == "spell"), None)
    assert spell_choice is not None
    assert len(spell_choice["options"]) > 0
    # Must include Bard spells (like Vicious Mockery or Dissonant Whispers)
    bard_sample_present = any(
        s in spell_choice["options"]
        for s in ["Dissonant Whispers", "Vicious Mockery", "Charm Person"]
    )
    assert bard_sample_present, (
        f"Expected Bard spells in regular level up options, got {spell_choice['options'][:5]}"
    )
    # Must NOT include non-Bard spells (like Mage Armor or Shield)
    assert "Mage Armor" not in spell_choice["options"]
