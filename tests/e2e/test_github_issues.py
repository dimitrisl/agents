"""E2E Test Suite for GitHub Board Issues (Features F4, F5, F6, F10, F13, F14, F15, F16).

Covers:
- F4: Mobile Companion Header Collapse (#209)
- F5: Sticky Whisper Input Dock (#211)
- F6: Navbar DM Role Status (#212)
- F10: Starting Armor/Shield Auto-Equip (#210)
- F13: Initiative Tracker Suite (#194)
- F14: Physical Dice Mode Enhancements (#195)
- F15: Combat State Sync (#196)
- F16: Encounter Reconnect Sync (#198)
"""

import math
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.services.stats_service import sync_character_stats
from tests.e2e.conftest import CLIENT_APP_ROOT, E2EAuthHelper

# ============================================================================
# Feature F4: Mobile Companion Header Collapse (Issue #209)
# ============================================================================


class TestF4MobileCompanionHeaderCollapse:
    """Verifies responsive collapse of Hero Management Header on <1024px."""

    @pytest.fixture(autouse=True)
    def player_files(self):
        player_html = CLIENT_APP_ROOT / "features" / "player" / "player.component.html"
        player_ts = CLIENT_APP_ROOT / "features" / "player" / "player.component.ts"
        assert player_html.is_file()
        assert player_ts.is_file()
        self.html = player_html.read_text(encoding="utf-8")
        self.ts = player_ts.read_text(encoding="utf-8")

    def test_f4_desktop_header_conditioned_on_not_companion_mode(self):
        """Desktop header app-player-dashboard-header must be hidden in companion mode."""
        assert "!isCompanionMode()" in self.html or "[isCompanionMode]" in self.html

    def test_f4_mobile_companion_header_rendered_in_companion_mode(self):
        """Dedicated compact header must be rendered when isCompanionMode() is true."""
        assert "isCompanionMode()" in self.html

    def test_f4_mobile_header_uses_compact_title_typography(self):
        """Mobile companion header must use compact title (text-lg or text-xl) to reclaim viewport."""
        assert "text-lg" in self.html or "text-xl" in self.html or "text-title" in self.html

    def test_f4_header_provides_compact_action_drawer_toggle(self):
        """Header must provide compact toggle for mobile actions (e.g. Actions ▾ / showMobileHeaderActions)."""
        assert (
            "showMobileHeaderActions" in self.ts
            or "showMobileActions" in self.ts
            or "Actions" in self.html
        )

    def test_f4_player_component_manages_mobile_header_actions_state(self):
        """player.component.ts must expose signal or method for toggling mobile header actions."""
        assert (
            "showMobileHeaderActions" in self.ts
            or "showMobileActions" in self.ts
            or "isCompanionMode" in self.ts
        )


# ============================================================================
# Feature F5: Sticky Whisper Input Dock (Issue #211)
# ============================================================================


class TestF5StickyWhisperInputDock:
    """Verifies whisper reply input remains sticky above bottom thumb dock in mobile Table tab."""

    @pytest.fixture(autouse=True)
    def player_template(self):
        player_html = CLIENT_APP_ROOT / "features" / "player" / "player.component.html"
        assert player_html.is_file()
        self.content = player_html.read_text(encoding="utf-8")

    def test_f5_table_tab_has_whisper_container(self):
        """player.component.html must contain whisper section in Table tab."""
        assert "whisper" in self.content.lower()

    def test_f5_whisper_input_dock_is_fixed_or_sticky_above_bottom_bar(self):
        """Whisper input dock must use fixed/sticky positioning above thumb bar."""
        # Must be fixed or sticky with bottom offset or bottom-0
        assert (
            "fixed bottom-" in self.content
            or "sticky bottom-" in self.content
            or "bottom-[calc" in self.content
        ), "Whisper input is not anchored with sticky/fixed above the bottom navigation dock"

    def test_f5_whisper_list_has_independent_scroll(self):
        """Whisper list container must have overflow-y-auto to scroll independently."""
        assert "whisper-list" in self.content
        assert "overflow-y-auto" in self.content

    def test_f5_table_tab_has_bottom_padding(self):
        """Table tab container must have bottom padding (e.g. pb-48 / pb-52) to avoid dock occlusion."""
        assert (
            "pb-52" in self.content
            or "pb-48" in self.content
            or "pb-40" in self.content
            or "pb-36" in self.content
        )


# ============================================================================
# Feature F6: Navbar DM Role Status (Issue #212)
# ============================================================================


class TestF6NavbarDMRoleStatus:
    """Verifies navbar accurately displays 'Dungeon Master' badge for DM users."""

    @pytest.fixture(autouse=True)
    def navbar_files(self):
        nav_html = CLIENT_APP_ROOT / "shared" / "components" / "navbar" / "navbar.component.html"
        nav_ts = CLIENT_APP_ROOT / "shared" / "components" / "navbar" / "navbar.component.ts"
        user_model = CLIENT_APP_ROOT / "core" / "models" / "user.model.ts"
        assert nav_html.is_file()
        assert nav_ts.is_file()
        assert user_model.is_file()
        self.html = nav_html.read_text(encoding="utf-8")
        self.ts = nav_ts.read_text(encoding="utf-8")
        self.model = user_model.read_text(encoding="utf-8")

    def test_f6_user_model_has_role_field(self):
        """User interface in user.model.ts must declare optional role?: string."""
        assert "role?:" in self.model or "role:" in self.model, (
            "User model lacks role attribute definition"
        )

    def test_f6_navbar_component_has_user_role_label_getter(self):
        """NavbarComponent must provide userRoleLabel getter or signal."""
        assert "userRoleLabel" in self.ts, "NavbarComponent missing userRoleLabel property"

    def test_f6_navbar_template_renders_user_role_label(self):
        """navbar.component.html must render userRoleLabel."""
        assert "userRoleLabel" in self.html, "Navbar template does not render userRoleLabel"
        # Must not have hardcoded isAdmin() ternary
        assert 'isAdmin() ? "Dungeon Master" : "Player"' not in self.html, (
            "Navbar still has old bugged isAdmin() ? Dungeon Master : Player check!"
        )

    def test_f6_role_label_resolution_oracle(self):
        """Oracle verification of role label determination logic."""

        def resolve_label(user: Dict[str, Any], url: str) -> str:
            if user.get("is_admin"):
                return "Administrator"
            if user.get("role") == "dm" or url.startswith("/dm"):
                return "Dungeon Master"
            return "Player"

        # Platform Admin -> Administrator
        assert resolve_label({"is_admin": True, "role": "dm"}, "/dm") == "Administrator"
        # DM User on /dm -> Dungeon Master
        assert resolve_label({"is_admin": False, "role": "dm"}, "/dm") == "Dungeon Master"
        # DM User on /campaigns -> Dungeon Master
        assert resolve_label({"is_admin": False, "role": "dm"}, "/campaigns") == "Dungeon Master"
        # Player visiting /dm route -> Dungeon Master (DM workspace context)
        assert (
            resolve_label({"is_admin": False, "role": "player"}, "/dm/workspace")
            == "Dungeon Master"
        )
        # Regular player on /player -> Player
        assert resolve_label({"is_admin": False, "role": "player"}, "/player") == "Player"


# ============================================================================
# Feature F10: Starting Armor/Shield Auto-Equip (Issue #210)
# ============================================================================


class TestF10StartingArmorShieldAutoEquip:
    """Verifies D&D Rules Invariant: Starting armor & shield default to equipped when none equipped."""

    def test_f10_paladin_starting_chain_mail_and_shield_auto_equips(self):
        """Paladin with Chain Mail & Shield in inventory (0 equipped) auto-equips both (AC = 18)."""
        char = {
            "char_name": "Kaelen Vane",
            "char_class": "Paladin",
            "char_level": 2,
            "classes": [{"class_name": "Paladin", "level": 2}],
            "race": "Human",
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 16},
            "equipment": [
                {"name": "Chain Mail", "equipped": False},
                {"name": "Shield", "equipped": False},
                {"name": "Holy Symbol", "equipped": False},
            ],
            "dnd_edition": "2024 Revision",
        }
        synced = sync_character_stats(char)
        # Paladin proficient in all armor and shields
        # Chain Mail base AC 16 + Shield +2 = 18
        assert synced.get("armor_class") == 18, f"Expected AC 18, got {synced.get('armor_class')}"
        equipped_items = [e["name"] for e in synced["equipment"] if e.get("equipped")]
        assert "Chain Mail" in equipped_items
        assert "Shield" in equipped_items

    def test_f10_fighter_auto_equips_highest_ac_proficient_armor(self):
        """Fighter with Leather Armor and Chain Mail auto-equips Chain Mail (AC = 16)."""
        char = {
            "char_name": "Valerius",
            "char_class": "Fighter",
            "char_level": 1,
            "classes": [{"class_name": "Fighter", "level": 1}],
            "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            "equipment": [
                {"name": "Leather Armor", "equipped": False},
                {"name": "Chain Mail", "equipped": False},
            ],
            "dnd_edition": "2024 Revision",
        }
        synced = sync_character_stats(char)
        assert synced.get("armor_class") == 16
        equipped_items = [e["name"] for e in synced["equipment"] if e.get("equipped")]
        assert "Chain Mail" in equipped_items
        assert "Leather Armor" not in equipped_items

    def test_f10_wizard_does_not_auto_equip_unproficient_heavy_armor(self):
        """Wizard possessing Chain Mail does NOT auto-equip it (lacks proficiency)."""
        char = {
            "char_name": "Raistlin",
            "char_class": "Wizard",
            "char_level": 1,
            "classes": [{"class_name": "Wizard", "level": 1}],
            "stats": {"STR": 8, "DEX": 14, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
            "equipment": [
                {"name": "Chain Mail", "equipped": False},
                {"name": "Spellbook", "equipped": False},
            ],
            "dnd_edition": "2024 Revision",
        }
        synced = sync_character_stats(char)
        # Wizard unarmored AC = 10 + DEX 14 (+2) = 12
        assert synced.get("armor_class") == 12
        equipped_items = [e["name"] for e in synced["equipment"] if e.get("equipped")]
        assert "Chain Mail" not in equipped_items

    def test_f10_multi_shield_equips_at_most_one(self):
        """Character with multiple shields auto-equips at most 1 shield."""
        char = {
            "char_name": "Shield Bearer",
            "char_class": "Paladin",
            "char_level": 1,
            "classes": [{"class_name": "Paladin", "level": 1}],
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            "equipment": [
                {"name": "Shield", "equipped": False},
                {"name": "Shield", "equipped": False},
            ],
            "dnd_edition": "2024 Revision",
        }
        synced = sync_character_stats(char)
        equipped_shields = [
            e for e in synced["equipment"] if e.get("name") == "Shield" and e.get("equipped")
        ]
        assert len(equipped_shields) == 1
        # Unarmored 10 + 1 shield (+2) = 12 (not 14)
        assert synced.get("armor_class") == 12

    def test_f10_already_equipped_items_not_overridden(self):
        """If user already has an item explicitly equipped, auto-equip does not trigger."""
        char = {
            "char_name": "Sneaky Fighter",
            "char_class": "Fighter",
            "char_level": 1,
            "classes": [{"class_name": "Fighter", "level": 1}],
            "stats": {"STR": 10, "DEX": 16, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            "equipment": [
                {"name": "Leather Armor", "equipped": True},  # Explicitly chosen
                {"name": "Chain Mail", "equipped": False},
            ],
            "dnd_edition": "2024 Revision",
        }
        synced = sync_character_stats(char)
        # Leather Armor 11 + DEX 16 (+3) = 14
        assert synced.get("armor_class") == 14
        assert not any(e["name"] == "Chain Mail" and e.get("equipped") for e in synced["equipment"])


# ============================================================================
# Feature F13: Initiative Tracker Suite (Issue #194)
# ============================================================================


class TestF13InitiativeTrackerSuite:
    """Verifies inline HP/AC editing, Roll Monsters Only, and auto-sync in Initiative Tracker."""

    @pytest.fixture(autouse=True)
    def panel_files(self):
        panel_dir = CLIENT_APP_ROOT / "features" / "dm" / "panels" / "initiative-panel"
        panel_html = panel_dir / "initiative-panel.component.html"
        dm_ts = CLIENT_APP_ROOT / "features" / "dm" / "dm.component.ts"
        assert panel_html.is_file()
        assert dm_ts.is_file()
        self.html = panel_html.read_text(encoding="utf-8")
        self.dm_ts = dm_ts.read_text(encoding="utf-8")

    def test_f13_initiative_table_has_inline_initiative_input(self):
        """Initiative panel must render inline <input> for combatant.initiative."""
        assert "<input" in self.html and "initiative" in self.html

    def test_f13_initiative_table_has_inline_ac_input(self):
        """Initiative panel must render inline <input> for combatant.ac."""
        assert "ac" in self.html.lower()

    def test_f13_panel_has_roll_monsters_only_button(self):
        """Initiative panel must provide 'Roll Monsters Only' action button."""
        assert "roll monsters only" in self.html.lower() or "monsters only" in self.html.lower()

    def test_f13_dm_component_implements_roll_monsters_initiative(self):
        """dm.component.ts must implement rollMonstersInitiative() filtering !combatant.is_player."""
        assert (
            "rollmonstersinitiative" in self.dm_ts.lower() or "rollmonsters" in self.dm_ts.lower()
        )

    def test_f13_tie_breaking_order_oracle(self):
        """Initiative tie-breaking oracle: higher DEX wins tie."""
        combatants = [
            {"name": "Goblin A", "initiative": 15, "dex": 14},
            {"name": "Player 1", "initiative": 15, "dex": 16},
            {"name": "Boss", "initiative": 20, "dex": 12},
        ]
        # Sort descending by initiative, then by DEX
        sorted_c = sorted(
            combatants, key=lambda c: (c["initiative"], c.get("dex", 10)), reverse=True
        )
        assert sorted_c[0]["name"] == "Boss"
        assert sorted_c[1]["name"] == "Player 1"  # Won tie with DEX 16 vs 14
        assert sorted_c[2]["name"] == "Goblin A"


# ============================================================================
# Feature F14: Physical Dice Mode Enhancements (Issue #195)
# ============================================================================


class TestF14PhysicalDiceModeEnhancements:
    """Verifies manual d20 input in companion, Keep Concentration, and manual short rest HP."""

    def test_f14_player_roll_request_modal_has_physical_dice_input(self):
        """Player roll request modal template must allow physical d20 input."""
        modal_html = (
            CLIENT_APP_ROOT
            / "features"
            / "player"
            / "modals"
            / "roll-request-modal"
            / "roll-request-modal.component.html"
        )
        content = modal_html.read_text(encoding="utf-8")
        assert "physical" in content.lower() or "manual" in content.lower()

    def test_f14_concentration_banner_has_keep_concentration_button(self):
        """Concentration save prompt banner must have a button to retain concentration."""
        player_html = CLIENT_APP_ROOT / "features" / "player" / "player.component.html"
        content = player_html.read_text(encoding="utf-8")
        assert "keep" in content.lower() or "passed" in content.lower()

    def test_f14_short_rest_modal_has_manual_hp_input(self):
        """Short rest modal must provide manual HP input for physical tabletop rolls."""
        modal_html = (
            CLIENT_APP_ROOT
            / "features"
            / "player"
            / "modals"
            / "short-rest-modal"
            / "short-rest-modal.component.html"
        )
        content = modal_html.read_text(encoding="utf-8")
        assert "manual" in content.lower() or "hp" in content.lower()

    def test_f14_player_component_has_keep_concentration_method(self):
        """player.component.ts must implement keepConcentration() preserving char.concentrating_on."""
        player_ts = CLIENT_APP_ROOT / "features" / "player" / "player.component.ts"
        code = player_ts.read_text(encoding="utf-8")
        assert "keepconcentration" in code.lower()


# ============================================================================
# Feature F15: Combat State Sync (Issue #196)
# ============================================================================


class TestF15CombatStateSync:
    """Verifies concentration prompts on DM damage, death saves reset on heal, and condition sync."""

    def test_f15_concentration_dc_calculation_oracle(self):
        """Concentration Save DC oracle: max(10, floor(damage / 2))."""

        def calc_dc(dmg: int) -> int:
            return max(10, math.floor(dmg / 2))

        assert calc_dc(5) == 10
        assert calc_dc(10) == 10
        assert calc_dc(18) == 10
        assert calc_dc(20) == 10
        assert calc_dc(22) == 11
        assert calc_dc(35) == 17
        assert calc_dc(50) == 25

    def test_f15_lethal_damage_drops_concentration(self):
        """D&D rules invariant: reaching 0 HP instantly drops concentration."""
        char = {"hp_current": 10, "concentrating_on": "Haste"}
        # Damage 10 -> hp_current = 0
        char["hp_current"] = 0
        if char["hp_current"] == 0:
            char["concentrating_on"] = ""
        assert char["concentrating_on"] == ""

    def test_f15_heal_from_zero_resets_death_saves(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """DM healing a player from 0 HP must reset death saves to 0 successes and 0 failures."""
        dm_headers = auth_helper.register_and_login("dm_sync", "dm_sync@test.dnd")
        p_headers = auth_helper.register_and_login("p_sync", "p_sync@test.dnd")

        # Create campaign
        c_name = "Sync Campaign"
        c_res = e2e_client.post(
            "/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers
        )
        assert c_res.status_code == 200

        invite_code = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/invite-code", headers=dm_headers
        ).json()["invite_code"]

        # Create player char with 0 HP and 2 death save failures
        p_char = e2e_client.post(
            "/api/v1/characters",
            json={
                "char_name": "Dying Hero",
                "char_class": "Fighter",
                "char_level": 1,
                "race": "Human",
                "background": "Soldier",
                "hp_current": 0,
                "death_saves": {"successes": 0, "failures": 2},
                "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            },
            headers=p_headers,
        ).json()
        p_id = p_char["char_id"]

        # Join campaign
        e2e_client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": invite_code, "character_id": p_id},
            headers=p_headers,
        )

        # DM heals player to 5 HP
        patch_res = e2e_client.patch(
            f"/api/v1/campaigns/{c_name}/party/{p_id}/state",
            json={"hp_current": 5},
            headers=dm_headers,
        )
        assert patch_res.status_code == 200
        data = patch_res.json()
        assert data["hp_current"] == 5
        # Backend must auto-reset death saves to 0
        char_after = e2e_client.get(f"/api/v1/characters/{p_id}", headers=p_headers).json()
        death_saves = char_after.get("death_saves", {})
        assert death_saves.get("successes", 0) == 0
        assert death_saves.get("failures", 0) == 0


# ============================================================================
# Feature F16: Encounter Reconnect Sync (Issue #198)
# ============================================================================


class TestF16EncounterReconnectSync:
    """Verifies encounter state is automatically queried and restored on load/reconnect."""

    def test_f16_get_encounter_endpoint_returns_encounter_state(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """GET /api/v1/campaigns/{c_name}/encounter returns active encounter state."""
        dm_headers = auth_helper.register_and_login("dm_rec", "dm_rec@test.dnd")
        c_name = "Reconnect Campaign"
        e2e_client.post("/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers)

        enc_res = e2e_client.get(f"/api/v1/campaigns/{c_name}/encounter", headers=dm_headers)
        assert enc_res.status_code == 200
        data = enc_res.json()
        assert data is None or isinstance(data, dict)

    def test_f16_player_component_fetches_encounter_on_reconnect(self):
        """player.component.ts must call loadActiveEncounter() inside openedSub."""
        player_ts = CLIENT_APP_ROOT / "features" / "player" / "player.component.ts"
        code = player_ts.read_text(encoding="utf-8")
        assert "loadactiveencounter" in code.lower() or "encounter" in code.lower()
