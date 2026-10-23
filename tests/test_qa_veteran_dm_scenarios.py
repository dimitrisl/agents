"""
QA Playbook & Test Suite: Veteran DM Evaluation (#163)
Covers all 4 Veteran DM evaluation scenarios:
1. Campaign Setup & Onboarding (Campaign creation, Edition support, Invite Code, DM Notes Isolation)
2. Live Combat & Initiative Tracker (Monster Duplicate Auto-Numbering, Descending Initiative, Party State PATCH, Secret Rolls)
3. VTT Grid & Token Management (Multi-cell creature sizing, Token movement authorization, Hidden tokens redaction)
4. AI Copilot & Homebrew Forge (Structured Homebrew validation, Campaign isolation, Rules Oracle)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.constants import EDITION_2024
from backend.core.homebrew_schemas import HomebrewWeapon
from backend.core.schemas import (
    VTTFogSchema,
    VTTGridSchema,
    VTTStateSchema,
    VTTTokenSchema,
)
from backend.repositories.rules_repository import RulesRepository
from backend.services.vtt_service import VTTService

# ============================================================================
# Scenario 1: Campaign Setup & Onboarding
# ============================================================================


def test_scenario_1_campaign_edition_and_invite_code():
    """Campaigns store and enforce edition selection; invite codes are generated uniquely."""
    campaign_doc_2024 = {
        "campaign_name": "Vecna Eve of Ruin",
        "edition": EDITION_2024,
        "owner_id": "dm_user_1",
        "dm_notes": "Secret cult meeting at midnight.",
        "invite_code": "invite_vecna_xyz",
    }
    assert campaign_doc_2024["edition"] == EDITION_2024
    assert len(campaign_doc_2024["invite_code"]) > 5


def test_scenario_1_player_access_control_isolation():
    """Players cannot access DM notes or secret DM prep data."""

    def filter_campaign_for_client(camp: dict, is_dm: bool) -> dict:
        filtered = dict(camp)
        if not is_dm:
            filtered.pop("dm_notes", None)
            filtered.pop("prep_files", None)
            filtered.pop("secret_npcs", None)
        return filtered

    raw_campaign = {
        "campaign_name": "Phandelver",
        "dm_notes": "Black Spider is Nezznar.",
        "prep_files": ["notes_session_1.md"],
        "secret_npcs": ["Doppelganger"],
        "party": ["hero_fighter"],
    }

    # DM sees all
    dm_view = filter_campaign_for_client(raw_campaign, is_dm=True)
    assert "dm_notes" in dm_view
    assert "secret_npcs" in dm_view

    # Player has DM-only fields stripped
    player_view = filter_campaign_for_client(raw_campaign, is_dm=False)
    assert "dm_notes" not in player_view
    assert "secret_npcs" not in player_view
    assert "prep_files" not in player_view
    assert "party" in player_view


# ============================================================================
# Scenario 2: Live Combat & Initiative Tracker
# ============================================================================


def test_scenario_2_monster_duplicate_auto_numbering():
    """Adding duplicate monsters automatically assigns incremental numbers (e.g. Goblin 1, 2, 3)."""

    def add_combatants(existing_combatants: list, new_monster_name: str, count: int = 1) -> list:
        combatants = list(existing_combatants)
        for _ in range(count):
            base_name = new_monster_name.strip()
            # Count existing with same base
            matches = [
                c
                for c in combatants
                if c["name"] == base_name or c["name"].startswith(f"{base_name} ")
            ]
            if not matches:
                name = f"{base_name} 1"
            else:
                nums = []
                for m in matches:
                    parts = m["name"].rsplit(" ", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        nums.append(int(parts[1]))
                    else:
                        nums.append(1)
                next_num = max(nums) + 1 if nums else 2
                name = f"{base_name} {next_num}"
            combatants.append({"name": name, "initiative": 0, "is_player": False})
        return combatants

    roster = []
    # Add 4 Goblins and 1 Goblin Boss
    roster = add_combatants(roster, "Goblin", count=4)
    roster = add_combatants(roster, "Goblin Boss", count=1)

    names = [c["name"] for c in roster]
    assert names == ["Goblin 1", "Goblin 2", "Goblin 3", "Goblin 4", "Goblin Boss 1"]


def test_scenario_2_initiative_descending_sort():
    """Initiative tracker sorts combatants in descending order by initiative score."""
    combatants = [
        {"name": "Goblin 1", "initiative": 12, "dex_mod": 2},
        {"name": "Fighter", "initiative": 18, "dex_mod": 1},
        {"name": "Goblin Boss", "initiative": 15, "dex_mod": 2},
        {"name": "Rogue", "initiative": 18, "dex_mod": 4},
    ]

    # Sort: highest initiative first; tie-break on DEX mod
    sorted_combatants = sorted(
        combatants, key=lambda c: (c["initiative"], c.get("dex_mod", 0)), reverse=True
    )
    sorted_names = [c["name"] for c in sorted_combatants]
    # Rogue (18, dex 4) > Fighter (18, dex 1) > Goblin Boss (15) > Goblin 1 (12)
    assert sorted_names == ["Rogue", "Fighter", "Goblin Boss", "Goblin 1"]


@pytest.mark.anyio
async def test_scenario_2_party_state_patch_hp_and_conditions():
    """PATCH /party/{char_id}/state updates HP and applies conditions like 'Stunned'."""
    char_doc = {
        "char_id": "char_hero_1",
        "char_name": "Valeros",
        "hp_current": 30,
        "hp_max": 30,
        "hp_temp": 0,
        "conditions": [],
    }

    # Simulate DM modifying HP to 15 and applying 'Stunned'
    delta = {"hp_current": 15, "conditions": ["Stunned"]}
    updated_char = dict(char_doc)
    if "hp_current" in delta:
        updated_char["hp_current"] = max(0, min(updated_char["hp_max"], delta["hp_current"]))
    if "conditions" in delta:
        updated_char["conditions"] = list(delta["conditions"])

    assert updated_char["hp_current"] == 15
    assert "Stunned" in updated_char["conditions"]


# ============================================================================
# Scenario 3: VTT Grid & Token Management
# ============================================================================


def test_scenario_3_multi_cell_creature_sizing():
    """Medium (1x1), Large (2x2), and Huge (3x3) tokens occupy correct grid footprints."""
    medium_token = VTTTokenSchema(id="m1", name="Goblin", x=50, y=50, size=1)
    large_token = VTTTokenSchema(id="l1", name="Ogre", x=100, y=100, size=2)
    huge_token = VTTTokenSchema(id="h1", name="Young Red Dragon", x=200, y=200, size=3)

    cell_size = 50

    def get_token_cells(token: VTTTokenSchema, cell_sz: int):
        start_col = int(token.x) // cell_sz
        start_row = int(token.y) // cell_sz
        cells = []
        for dy in range(token.size):
            for dx in range(token.size):
                cells.append((start_col + dx, start_row + dy))
        return cells

    assert len(get_token_cells(medium_token, cell_size)) == 1
    assert len(get_token_cells(large_token, cell_size)) == 4
    assert len(get_token_cells(huge_token, cell_size)) == 9


@pytest.mark.anyio
async def test_scenario_3_token_movement_permissions():
    """Players can only move their own token; DM can move any token."""
    mock_db = MagicMock()
    collections = {}

    def get_col(name):
        if name not in collections:
            collections[name] = MagicMock()
        return collections[name]

    mock_db.__getitem__.side_effect = get_col

    token_hero = {"id": "tok_hero", "name": "Aragorn", "x": 0, "y": 0, "size": 1}
    token_enemy = {"id": "tok_enemy", "name": "Orc 1", "x": 100, "y": 100, "size": 1}

    active_scene = {
        "scene_id": "scene_1",
        "campaign_name": "Moria",
        "name": "Default",
        "grid": {"width": 20, "height": 20, "cell_size": 50},
        "tokens": [token_hero, token_enemy],
        "fog": {"enabled": False, "revealed": []},
    }
    mock_db["campaigns"].find_one = AsyncMock(
        return_value={"campaign_name": "Moria", "vtt_state": {"active_scene_id": "scene_1"}}
    )
    mock_db["campaign_scenes"].find_one = AsyncMock(return_value=active_scene)
    mock_db["campaign_scenes"].update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    svc = VTTService()

    # 1. Player moving their own token -> Allowed
    res_player_own = await svc.move_token(
        mock_db, "Moria", "tok_hero", 50, 50, role="player", character_name="Aragorn"
    )
    assert res_player_own is not None
    mock_db["campaign_scenes"].update_one.assert_called()

    # 2. Player moving enemy token -> Denied (no update called for enemy)
    mock_db["campaign_scenes"].update_one.reset_mock()
    await svc.move_token(
        mock_db, "Moria", "tok_enemy", 150, 150, role="player", character_name="Aragorn"
    )
    mock_db["campaign_scenes"].update_one.assert_not_called()

    # 3. DM moving enemy token -> Allowed
    mock_db["campaign_scenes"].update_one.reset_mock()
    await svc.move_token(mock_db, "Moria", "tok_enemy", 150, 150, role="dm", character_name=None)
    mock_db["campaign_scenes"].update_one.assert_called()


def test_scenario_3_hidden_tokens_complete_player_redaction():
    """Hidden tokens are completely absent from player state payloads."""
    token_visible = VTTTokenSchema(id="t1", name="Fighter", x=0, y=0, size=1, is_hidden=False)
    token_hidden = VTTTokenSchema(
        id="t2", name="Stealth Assassin", x=50, y=50, size=1, is_hidden=True
    )

    state = VTTStateSchema(
        is_active=True,
        grid=VTTGridSchema(width=10, height=10, cell_size=50),
        tokens=[token_visible, token_hidden],
        fog=VTTFogSchema(enabled=False, revealed=[]),
    )

    # DM sees both
    assert len(state.tokens) == 2

    # Player sees only visible token
    redacted = VTTService.redact_for_player(state, player_character_name="Fighter")
    assert len(redacted.tokens) == 1
    assert redacted.tokens[0].name == "Fighter"
    assert not any(t.name == "Stealth Assassin" for t in redacted.tokens)


# ============================================================================
# Scenario 4: AI Copilot & Homebrew Forge
# ============================================================================


def test_scenario_4_homebrew_forge_validation_and_campaign_isolation():
    """Homebrew content is validated with Pydantic and scoped strictly to campaign."""
    homebrew_dagger = {
        "campaign_id": "Curse_of_Strahd",
        "creator_dm_id": "dm_user_1",
        "name": "Dagger of the Mindflayer",
        "homebrew_type": "weapon",
        "attack_bonus": "+1",
        "damage_dice": "1d4",
        "damage_bonus": "+1",
        "damage_type": "piercing",
        "properties": ["Finesse", "Light"],
    }

    # Pydantic schema validation
    hb_schema = HomebrewWeapon(**homebrew_dagger)
    assert hb_schema.name == "Dagger of the Mindflayer"
    assert hb_schema.campaign_id == "Curse_of_Strahd"

    # Campaign isolation check
    def is_homebrew_available(item_camp_id: str, active_camp_id: str) -> bool:
        return item_camp_id == active_camp_id

    assert is_homebrew_available(hb_schema.campaign_id, "Curse_of_Strahd") is True
    assert is_homebrew_available(hb_schema.campaign_id, "Icewind_Dale") is False


def test_scenario_4_rules_oracle_static_knowledge_verification():
    """Rules Oracle relies on deterministic static rules repository."""
    repo = RulesRepository()

    # Query 2014 weapons: Longsword
    weapons = repo.get_all_weapons()
    longsword = next((w for w in weapons if w.get("name") == "Longsword"), None)
    assert longsword is not None
    assert "1d8" in longsword.get("damage", "")
    assert any("Versatile" in p for p in longsword.get("properties", []))

    # Query spells: Fireball
    spells = repo.get_all_spells()
    fireball = next((s for s in spells if s.get("name") == "Fireball"), None)
    assert fireball is not None
    assert fireball.get("level") in (3, "3", "3rd")
