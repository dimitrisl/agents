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


# --- 13. [DEF-CR-02 & Audit] Rules Engine & Brooch of Shielding Fixes ---
def test_brooch_of_shielding_not_shield_and_monk_unarmored_preserved():
    """Brooch of Shielding must NOT grant +2 AC as a shield and must NOT disable Monk Unarmored Defense."""
    from backend.services.stats_service import calculate_ac, sync_character_stats

    # Monk Level 1: DEX 16 (+3), WIS 16 (+3) -> Unarmored Defense AC = 10 + 3 + 3 = 16
    monk = {
        "char_name": "Zen Monk",
        "char_class": "Monk",
        "char_level": 1,
        "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 16, "CHA": 10},
        "equipment": [
            {"name": "Brooch of Shielding", "equipped": True},
        ],
        "features_traits": [{"name": "Unarmored Defense", "source": "Monk"}],
    }
    synced = sync_character_stats(monk)
    # AC should remain 16 (10 + DEX + WIS). Brooch of Shielding must NOT add +2 or disable Unarmored Defense.
    assert synced["armor_class"] == 16
    assert synced["ac_breakdown"]["total"] == 16
    assert "Unarmored Defense" in synced["ac_breakdown"]["base_source"]
    assert synced["ac_breakdown"]["shield_bonus"] == 0

    # Also test directly in calculate_ac
    ac, breakdown = calculate_ac(
        dex_score=16,
        equipment=[{"name": "Brooch of Shielding", "equipped": True}],
        features=[{"name": "Unarmored Defense", "source": "Monk"}],
        wis_score=16,
        return_breakdown=True,
    )
    assert ac == 16
    assert breakdown["shield_bonus"] == 0


def test_auto_equip_respects_monk_and_barbarian_unarmored():
    """Monks and Barbarians with unassigned starting gear must NOT have armor auto-equipped."""
    from backend.services.stats_service import sync_character_stats

    monk = {
        "char_name": "Monk Hero",
        "char_class": "Monk",
        "char_level": 1,
        "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 16, "CHA": 10},
        "equipment": [
            {"name": "Leather Armor"},  # Unassigned equipped key
        ],
    }
    synced = sync_character_stats(monk)
    # Armor must NOT be auto-equipped
    assert synced["equipment"][0].get("equipped", False) is False
    assert synced["armor_class"] == 16  # 10 + DEX 3 + WIS 3


def test_auto_equip_respects_explicit_unequipped_state():
    """When a hero explicitly unequips all items, sync must NOT forcibly re-equip them."""
    from backend.services.stats_service import sync_character_stats

    fighter = {
        "char_name": "Fighter Resting",
        "char_class": "Fighter",
        "char_level": 1,
        "base_stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "equipment": [
            {"name": "Chain Mail", "equipped": False},
            {"name": "Shield", "equipped": False},
        ],
    }
    synced = sync_character_stats(fighter)
    assert synced["equipment"][0].get("equipped") is False
    assert synced["equipment"][1].get("equipped") is False
    assert synced["armor_class"] == 10


def test_observant_feat_passive_perception_bonus():
    """Observant feat must add +5 to passive perception."""
    from backend.services.stats_service import sync_character_stats

    # Level 1 Cleric: WIS 16 (+3), Prof +2, Trained in Perception -> Base passive = 10 + 3 + 2 = 15
    cleric_no_feat = {
        "char_name": "Cleric",
        "char_class": "Cleric",
        "char_level": 1,
        "stats": {"STR": 10, "DEX": 10, "CON": 12, "INT": 10, "WIS": 16, "CHA": 10},
        "skill_proficiencies": ["Perception"],
        "features_traits": [],
    }
    synced1 = sync_character_stats(cleric_no_feat)
    assert synced1["passive_perception"] == 15

    # With Observant feat -> 15 + 5 = 20
    cleric_observant = {
        "char_name": "Cleric Observant",
        "char_class": "Cleric",
        "char_level": 1,
        "stats": {"STR": 10, "DEX": 10, "CON": 12, "INT": 10, "WIS": 16, "CHA": 10},
        "skill_proficiencies": ["Perception"],
        "features_traits": [{"name": "Observant"}],
    }
    synced2 = sync_character_stats(cleric_observant)
    assert synced2["passive_perception"] == 20


def test_initiative_advantage_resets_cleanly_on_subclass_change():
    """Respecing out of Champion must reset initiative_advantage to False without leaking."""
    from backend.services.stats_service import sync_character_stats

    # 2024 Champion Fighter level 3 has Remarkable Athlete (initiative advantage = True)
    champion = {
        "char_name": "Champion",
        "char_class": "Fighter",
        "char_level": 3,
        "subclass": "Champion",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "features_traits": [{"name": "Remarkable Athlete"}],
    }
    synced1 = sync_character_stats(champion)
    assert synced1["initiative_advantage"] is True
    assert synced1["athletics_advantage"] is True

    # Now change subclass to Battle Master and remove Remarkable Athlete
    battlemaster = {
        "char_name": "Champion",
        "char_class": "Fighter",
        "char_level": 3,
        "subclass": "Battle Master",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "features_traits": [{"name": "Combat Superiority"}],
        "initiative_advantage": True,  # Pre-existing from old sheet
        "athletics_advantage": True,
    }
    synced2 = sync_character_stats(battlemaster)
    assert synced2["initiative_advantage"] is False
    assert synced2["athletics_advantage"] is False


def test_sheet_modifier_secret_roll_case_insensitivity_and_half_prof():
    """_sheet_modifier handles case insensitivity and includes Jack of All Trades for secret rolls."""
    from server.routers.campaign_router import _sheet_modifier

    bard = {
        "char_name": "Lute Bard",
        "char_class": "Bard",
        "char_level": 3,
        "proficiency_bonus": 2,
        "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 10, "WIS": 10, "CHA": 16},
        "saving_throws": ["DEX", "CHA"],
        "skill_proficiencies": ["Persuasion"],
        "features_traits": [{"name": "Jack of All Trades"}],
    }
    # Saving throw with lowercase "dex": DEX mod (+2) + PB (2) = +4
    assert _sheet_modifier(bard, "saving_throw", "dex") == 4
    assert _sheet_modifier(bard, "save", "DEX") == 4

    # Untrained skill with lowercase "stealth": DEX mod (+2) + half-prof (+1) = +3 (NOT +0!)
    assert _sheet_modifier(bard, "skill_check", "stealth") == 3
    assert _sheet_modifier(bard, "skill", "Stealth") == 3


# --- 14. [Batch 2 Security & Stability] ---
def test_pdf_export_ssrf_disallows_redirects(monkeypatch):
    """PDF exporter portrait fetch must disable HTTP redirects to block SSRF bypasses."""
    import inspect

    from backend.utils.pdf_exporter import create_image_overlay

    src = inspect.getsource(create_image_overlay)
    assert "allow_redirects=False" in src, (
        "requests.get must explicitly disallow redirects to prevent SSRF"
    )


def test_unbounded_dice_dos_cap():
    """Dice engine must reject expressions exceeding safe bounds to prevent event loop exhaustion."""
    from backend.services.dice_service import roll_dice

    with pytest.raises(ValueError, match="Dice expression exceeds safe limits"):
        roll_dice("5000000d6")

    with pytest.raises(ValueError, match="Dice expression exceeds safe limits"):
        roll_dice("101d20")

    # Safe compound rolls work fine
    safe_res = roll_dice("2d6 + 1d4 + 3")
    assert safe_res["total"] >= 6


def test_legacy_sha256_upgrades_on_login():
    """When a user with legacy sha256 password logs in, their hash must be upgraded to pbkdf2."""
    from server.db_async import get_database
    from server.dependencies.auth import legacy_sha256_hash, pwd_context

    raw_pw = "secretPass123!"
    legacy_hash = legacy_sha256_hash(raw_pw)

    user_doc = {
        "_id": "user_legacy_1",
        "id": "user_legacy_1",
        "username": "olduser",
        "password_hash": legacy_hash,
        "name": "Old User",
        "email": "old@example.com",
        "is_admin": False,
    }

    mock_db = MagicMock()
    mock_db["users"].find_one = AsyncMock(return_value=user_doc)
    mock_db["users"].update_one = AsyncMock()

    app.dependency_overrides[get_database] = lambda: mock_db
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "olduser", "password": raw_pw},
        )
        assert resp.status_code == 200

        # Verify update_one was called to upgrade the hash
        mock_db["users"].update_one.assert_called_once()
        call_args = mock_db["users"].update_one.call_args
        filter_arg, update_arg = call_args[0]
        assert filter_arg == {"_id": "user_legacy_1"}
        new_hash = update_arg["$set"]["password_hash"]
        assert new_hash != legacy_hash
        assert pwd_context.verify(raw_pw, new_hash)
    finally:
        app.dependency_overrides.pop(get_database, None)


def test_admin_user_search_regex_escaped():
    """Admin user search must escape regex characters to prevent ReDoS / regex injection."""
    from server.db_async import get_database
    from server.dependencies.auth import require_admin

    mock_db = MagicMock()
    collections = {}
    mock_db.__getitem__.side_effect = lambda k: collections.setdefault(k, MagicMock())

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    async def empty_cursor(*args, **kwargs):
        if False:
            yield

    mock_cursor.__aiter__ = empty_cursor
    mock_db["users"].find.return_value = mock_cursor
    mock_db["users"].count_documents = AsyncMock(return_value=0)

    admin_user = {"id": "admin_1", "username": "superadmin", "is_admin": True}
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[require_admin] = lambda: admin_user

    try:
        client = TestClient(app)
        client.get("/api/v1/admin/users?search=test.*+regex[a-z]")
        mock_db["users"].find.assert_called_once()
        query = mock_db["users"].find.call_args[0][0]
        # Query must use escaped regex (URL query '+' decodes to space)
        assert query["$or"][0]["username"]["$regex"] == r"test\.\*\ regex\[a\-z\]"
    finally:
        app.dependency_overrides.pop(get_database, None)
        app.dependency_overrides.pop(require_admin, None)


def test_whisper_query_filters_at_mongodb_level():
    """Campaign messages endpoint must filter player whispers inside MongoDB query, preventing pagination starvation."""
    from server.db_async import get_database
    from server.dependencies.auth import get_current_user

    mock_db = MagicMock()
    collections = {}
    mock_db.__getitem__.side_effect = lambda k: collections.setdefault(k, MagicMock())

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    async def empty_cursor(*args, **kwargs):
        if False:
            yield

    mock_cursor.__aiter__ = empty_cursor
    mock_db["campaigns"].find_one = AsyncMock(return_value={"campaign_name": "DragonHeist"})
    mock_db["characters"].find_one = AsyncMock(
        return_value={"char_id": "c1", "char_name": "Thorne"}
    )
    mock_db["campaign_whispers"].find.return_value = mock_cursor
    mock_db["campaign_roll_requests"].find.return_value = mock_cursor

    player_user = {"id": "player_123", "username": "player1", "is_admin": False}
    member_doc = {
        "campaign_name": "DragonHeist",
        "user_id": "player_123",
        "username": "player1",
        "role": "player",
        "character_id": "c1",
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=member_doc)

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: player_user

    try:
        client = TestClient(app)
        client.get("/api/v1/campaigns/DragonHeist/messages")
        mock_db["campaign_whispers"].find.assert_called_once()
        query = mock_db["campaign_whispers"].find.call_args[0][0]
        # Query must contain MongoDB $or condition to prevent post-pagination starvation
        assert "$or" in query
        assert {"recipient": "All"} in query["$or"]
        assert {"sender_user_id": "player_123"} in query["$or"]
        assert {"recipient_user_id": "player_123"} in query["$or"]
        assert {"sender": "Thorne"} in query["$or"]
        assert {"recipient": "Thorne"} in query["$or"]
    finally:
        app.dependency_overrides.pop(get_database, None)
        app.dependency_overrides.pop(get_current_user, None)
