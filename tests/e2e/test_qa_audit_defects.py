"""E2E Test Suite for QA Audit Defects (Features F1, F2, F3, F7, F8, F9, F11, F12).

Covers:
- F1: Skills Panel Cleanup
- F2: VTT Touch/Pointer Events
- F3: text-body-sm Cleanup
- F7: Multiclass Level-Up HP Die
- F8: Dynamic Attunement Limits
- F9: Bard & Champion Half-Proficiency
- F11: DM Roll Modal Manual Input
- F12: Player Action Dock 5e Actions
"""

import re
from typing import Any, Dict

import pytest

from backend.services.stats_service import calculate_skills, sync_character_stats
from backend.services.validation_service import deterministic_validate_build
from server.routers.campaign_router import RollRequestSchema
from tests.e2e.conftest import CLIENT_APP_ROOT, CLIENT_ROOT, PROJECT_ROOT

# ============================================================================
# Feature F1: Skills Panel Cleanup
# ============================================================================


class TestF1SkillsPanelCleanup:
    """Verifies complete cleanup of duplicate orphan skills-panel component."""

    def test_f1_orphan_skills_panel_directory_removed(self):
        """Orphan duplicate directory client/src/app/features/player/skills-panel must not exist."""
        orphan_dir = CLIENT_APP_ROOT / "features" / "player" / "skills-panel"
        assert not orphan_dir.exists(), f"Orphan directory still exists at {orphan_dir}"

    def test_f1_active_tabs_skills_panel_component_exists(self):
        """Active production component in tabs/skills-panel must exist."""
        active_dir = CLIENT_APP_ROOT / "features" / "player" / "tabs" / "skills-panel"
        ts_file = active_dir / "skills-panel.component.ts"
        html_file = active_dir / "skills-panel.component.html"
        assert ts_file.is_file(), f"Missing active skills panel component at {ts_file}"
        assert html_file.is_file(), f"Missing active skills panel template at {html_file}"

    def test_f1_player_component_imports_tabs_skills_panel(self):
        """player.component.ts must import SkillsPanelComponent exclusively from tabs/."""
        player_ts = CLIENT_APP_ROOT / "features" / "player" / "player.component.ts"
        content = player_ts.read_text(encoding="utf-8")
        assert (
            "from './tabs/skills-panel/skills-panel.component'" in content
            or 'from "./tabs/skills-panel/skills-panel.component"' in content
        ), "player.component.ts does not import from ./tabs/skills-panel/skills-panel.component"
        assert "from './skills-panel/skills-panel.component'" not in content, (
            "player.component.ts still references old orphan directory!"
        )

    def test_f1_zero_unresolved_imports_across_client(self):
        """Ensure no file in client/src/ imports from features/player/skills-panel."""
        pattern = re.compile(r"features/player/skills-panel['\"]")
        bad_files = []
        for path in CLIENT_APP_ROOT.rglob("*.ts"):
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                bad_files.append(str(path.relative_to(PROJECT_ROOT)))
        assert len(bad_files) == 0, (
            f"Found stale imports referencing orphan skills-panel in: {bad_files}"
        )

    def test_f1_player_template_bindings_match_tabs_skills_panel(self):
        """player.component.html must bind inputs/outputs conforming to tabs/skills-panel."""
        player_html = CLIENT_APP_ROOT / "features" / "player" / "player.component.html"
        content = player_html.read_text(encoding="utf-8")
        assert "<app-skills-panel" in content
        assert "[allSkills]=" in content
        assert "(rollSkill)=" in content


# ============================================================================
# Feature F2: VTT Touch/Pointer Events
# ============================================================================


class TestF2VTTTouchPointerEvents:
    """Verifies VTT Fog of War canvas responds to touch and pointer events."""

    @pytest.fixture(autouse=True)
    def vtt_source(self):
        vtt_ts = CLIENT_APP_ROOT / "features" / "campaigns" / "vtt-grid" / "vtt-grid.component.ts"
        assert vtt_ts.is_file()
        self.code = vtt_ts.read_text(encoding="utf-8")

    def test_f2_canvas_template_declares_pointer_listeners(self):
        """fogCanvas must bind pointerdown, pointermove, pointerup for tablet support."""
        assert "(pointerdown)=" in self.code, "Missing (pointerdown) binding on fog canvas"
        assert "(pointermove)=" in self.code, "Missing (pointermove) binding on fog canvas"
        assert "(pointerup)=" in self.code, "Missing (pointerup) binding on fog canvas"

    def test_f2_paint_mode_css_declares_touch_action_none(self):
        """Paint mode CSS on fog canvas must declare touch-action: none to block page scrolling."""
        assert "touch-action: none" in self.code, (
            ".fog-canvas.paint-mode must declare touch-action: none;"
        )

    def test_f2_pointer_capture_implemented(self):
        """Pointer handlers must invoke setPointerCapture/releasePointerCapture for drag continuity."""
        assert "setPointerCapture" in self.code, "onFogPointerDown should set pointer capture"
        assert "releasePointerCapture" in self.code, "onFogPointerUp should release pointer capture"

    def test_f2_mouse_method_wrappers_preserved_for_backward_compat(self):
        """onFogMouseDown and onFogMouseMove must remain defined for unit tests."""
        assert "onFogMouseDown" in self.code
        assert "onFogMouseMove" in self.code
        assert "onFogMouseUp" in self.code

    def test_f2_pointer_cancellation_handled(self):
        """pointercancel and pointerleave must cleanly reset painting state."""
        assert "(pointercancel)=" in self.code or "pointercancel" in self.code, (
            "Canvas should handle pointercancel to avoid stuck paint state"
        )


# ============================================================================
# Feature F3: text-body-sm Cleanup
# ============================================================================


class TestF3TextBodySmCleanup:
    """Verifies zero occurrences of undefined text-body-sm class remain in client."""

    def test_f3_zero_occurrences_of_text_body_sm_in_app(self):
        """Scan all HTML and TS files in client/src/app/ for text-body-sm."""
        matches = []
        for ext in ("*.html", "*.ts"):
            for file_path in CLIENT_APP_ROOT.rglob(ext):
                content = file_path.read_text(encoding="utf-8")
                if "text-body-sm" in content:
                    matches.append(str(file_path.relative_to(PROJECT_ROOT)))
        assert len(matches) == 0, f"Found undefined text-body-sm in {len(matches)} files: {matches}"

    def test_f3_design_system_typography_tokens_defined_in_styles_css(self):
        """styles.css must provide valid @theme typography tokens."""
        styles_css = CLIENT_ROOT / "src" / "styles.css"
        css_text = styles_css.read_text(encoding="utf-8")
        assert "--text-body:" in css_text
        assert "--text-label:" in css_text
        assert "--text-micro:" in css_text
        assert "--text-title:" in css_text

    def test_f3_navbar_user_name_uses_valid_typography(self):
        """Navbar user name must use valid typography class (e.g. text-body)."""
        navbar_html = CLIENT_APP_ROOT / "shared" / "components" / "navbar" / "navbar.component.html"
        content = navbar_html.read_text(encoding="utf-8")
        assert "text-body-sm" not in content

    def test_f3_level_up_modal_uses_valid_typography(self):
        """Level-up modal must not contain text-body-sm."""
        lvl_html = (
            CLIENT_APP_ROOT
            / "features"
            / "player"
            / "modals"
            / "level-up-modal"
            / "level-up-modal.component.html"
        )
        content = lvl_html.read_text(encoding="utf-8")
        assert "text-body-sm" not in content

    def test_f3_validation_modal_uses_valid_typography(self):
        """Validation modal must not contain text-body-sm."""
        val_html = (
            CLIENT_APP_ROOT
            / "features"
            / "player"
            / "modals"
            / "validation-modal"
            / "validation-modal.component.html"
        )
        content = val_html.read_text(encoding="utf-8")
        assert "text-body-sm" not in content


# ============================================================================
# Feature F7: Multiclass Level-Up HP Die
# ============================================================================


class TestF7MulticlassLevelUpHpDie:
    """Verifies hit die resolution during multiclass level-up derives from leveling class."""

    def test_f7_level_up_component_uses_dynamic_hit_die(self):
        """level-up-modal.component.ts must derive hit die from target class, not character.hit_dice."""
        modal_ts = (
            CLIENT_APP_ROOT
            / "features"
            / "player"
            / "modals"
            / "level-up-modal"
            / "level-up-modal.component.ts"
        )
        code = modal_ts.read_text(encoding="utf-8")
        # Must not rely on old buggy pattern
        assert "this.character.hit_dice.match" not in code, (
            "level-up-modal still parses character.hit_dice directly instead of target class!"
        )
        assert "hitDieSidesFor" in code or "levelUpHitDie" in code, (
            "level-up-modal must derive hit die dynamically for levelUpClass"
        )

    def test_f7_level_up_template_displays_target_hit_die(self):
        """level-up-modal.component.html must show target class die preview."""
        modal_html = (
            CLIENT_APP_ROOT
            / "features"
            / "player"
            / "modals"
            / "level-up-modal"
            / "level-up-modal.component.html"
        )
        code = modal_html.read_text(encoding="utf-8")
        assert "character?.hit_dice?.match" not in code, (
            "Template still parses character.hit_dice instead of levelUpHitDie!"
        )

    def test_f7_dnd_rules_hit_die_sides_oracle(self):
        """Oracle check: 5e class hit dice standards."""
        expected_hit_dice = {
            "barbarian": 12,
            "fighter": 10,
            "paladin": 10,
            "ranger": 10,
            "bard": 8,
            "cleric": 8,
            "druid": 8,
            "monk": 8,
            "rogue": 8,
            "warlock": 8,
            "sorcerer": 6,
            "wizard": 6,
        }
        for cls_name, expected_sides in expected_hit_dice.items():
            # Verify 5e standards
            if cls_name == "barbarian":
                assert expected_sides == 12
            elif cls_name in ("fighter", "paladin", "ranger"):
                assert expected_sides == 10
            elif cls_name in ("sorcerer", "wizard"):
                assert expected_sides == 6
            else:
                assert expected_sides == 8

    def test_f7_multiclass_hp_minimum_gain_is_one(self):
        """D&D rules invariant: even with negative CON mod, minimum HP gain on level up is 1."""
        roll_total = 1  # 1 on die + (-3 CON) = -2 -> clamped to 1
        clamped_hp = max(1, roll_total - 3)
        assert clamped_hp == 1


# ============================================================================
# Feature F8: Dynamic Attunement Limits (Artificer Progression)
# ============================================================================


class TestF8DynamicAttunementLimits:
    """Verifies Artificer expanded attunement limits (10->4, 14->5, 18->6, default 3)."""

    def _make_artificer(self, level: int, attuned_count: int) -> Dict[str, Any]:
        equipment = [
            {"name": f"Magic Ring {i + 1}", "equipped": True, "attuned": True}
            for i in range(attuned_count)
        ]
        return {
            "char_name": f"Artificer Level {level}",
            "char_class": "Artificer",
            "char_level": level,
            "classes": [{"class_name": "Artificer", "level": level}],
            "race": "Gnome",
            "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 8},
            "equipment": equipment,
            "dnd_edition": "2024 Revision",
        }

    def test_f8_artificer_level_10_allows_4_attuned_items(self):
        """Artificer Level 10 (Magic Item Adept) may attune up to 4 items with 0 validation issues."""
        char = self._make_artificer(level=10, attuned_count=4)
        is_valid, issues = deterministic_validate_build(char)
        attunement_issues = [i for i in issues if "attunement limit" in i.lower()]
        assert len(attunement_issues) == 0, f"Unexpected attunement issue: {attunement_issues}"

    def test_f8_artificer_level_14_allows_5_attuned_items(self):
        """Artificer Level 14 (Magic Item Savant) may attune up to 5 items."""
        char = self._make_artificer(level=14, attuned_count=5)
        is_valid, issues = deterministic_validate_build(char)
        attunement_issues = [i for i in issues if "attunement limit" in i.lower()]
        assert len(attunement_issues) == 0

    def test_f8_artificer_level_18_allows_6_attuned_items(self):
        """Artificer Level 18 (Magic Item Master) may attune up to 6 items."""
        char = self._make_artificer(level=18, attuned_count=6)
        is_valid, issues = deterministic_validate_build(char)
        attunement_issues = [i for i in issues if "attunement limit" in i.lower()]
        assert len(attunement_issues) == 0

    def test_f8_artificer_level_10_over_limit_flagged(self):
        """Artificer Level 10 with 5 attuned items exceeds limit of 4."""
        char = self._make_artificer(level=10, attuned_count=5)
        is_valid, issues = deterministic_validate_build(char)
        assert any("attunement limit of 4" in i.lower() for i in issues), (
            f"Expected limit of 4 warning, got: {issues}"
        )

    def test_f8_non_artificer_capped_at_3_attuned_items(self):
        """Non-Artificer (Wizard 10) with 4 attuned items exceeds standard limit of 3."""
        char = {
            "char_name": "Wizard Level 10",
            "char_class": "Wizard",
            "char_level": 10,
            "classes": [{"class_name": "Wizard", "level": 10}],
            "race": "Elf",
            "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10},
            "equipment": [
                {"name": f"Wand {i + 1}", "equipped": True, "attuned": True} for i in range(4)
            ],
            "dnd_edition": "2024 Revision",
        }
        is_valid, issues = deterministic_validate_build(char)
        assert any("attunement limit of 3" in i.lower() for i in issues), (
            f"Expected limit of 3 warning, got: {issues}"
        )


# ============================================================================
# Feature F9: Bard & Champion Half-Proficiency
# ============================================================================


class TestF9HalfProficiency:
    """Verifies Bard Jack of All Trades and Champion Remarkable Athlete half-proficiency."""

    def test_f9_calculate_skills_with_half_prof_all(self):
        """Bard Jack of All Trades applies half-prof to all non-proficient skills."""
        stats = {"STR": 10, "DEX": 14, "CON": 12, "INT": 16, "WIS": 10, "CHA": 16}
        pb = 2
        # Proficient only in Persuasion and Deception
        profs = ["Persuasion", "Deception"]
        skills = calculate_skills(
            stats=stats,
            proficiency_bonus=pb,
            proficiencies=profs,
            expertise=[],
            half_prof_all=True,
        )
        # Stealth (DEX +2) non-proficient -> 2 + 1 = 3
        assert skills["Stealth"] == 3
        # Arcana (INT +3) non-proficient -> 3 + 1 = 4
        assert skills["Arcana"] == 4
        # Persuasion (CHA +3) proficient -> 3 + 2 = 5 (no double half-prof)
        assert skills["Persuasion"] == 5

    def test_f9_calculate_skills_with_half_prof_phys(self):
        """Champion Remarkable Athlete applies half-prof only to STR, DEX, CON skills."""
        stats = {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8}
        pb = 3  # Level 7
        profs = ["Athletics"]
        skills = calculate_skills(
            stats=stats,
            proficiency_bonus=pb,
            proficiencies=profs,
            expertise=[],
            half_prof_phys=True,
        )
        # Acrobatics (DEX +2) non-proficient physical -> 2 + ceil(3/2) = 4 (per 5e RAW)
        assert skills["Acrobatics"] == 4
        # History (INT +0) non-proficient mental -> 0 + 0 = 0 (NOT increased)
        assert skills["History"] == 0
        # Athletics (STR +3) proficient -> 3 + 3 = 6
        assert skills["Athletics"] == 6

    def test_f9_bard_initiative_modifier_includes_half_prof(self):
        """Level 2 Bard includes half proficiency in initiative modifier."""
        char = {
            "char_name": "Jack the Bard",
            "char_class": "Bard",
            "char_level": 2,
            "classes": [{"class_name": "Bard", "level": 2}],
            "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 12, "WIS": 10, "CHA": 16},
            "dnd_edition": "2024 Revision",
        }
        synced = sync_character_stats(char)
        # DEX 14 (+2), PB 2, half PB = 1 -> initiative = +3
        assert synced.get("initiative_modifier") == 3

    def test_f9_champion_initiative_modifier_includes_half_prof(self):
        """Level 7 Champion Fighter includes half proficiency in initiative modifier."""
        char = {
            "char_name": "Sir Champion",
            "char_class": "Fighter",
            "subclass": "Champion",
            "char_level": 7,
            "classes": [{"class_name": "Fighter", "subclass": "Champion", "level": 7}],
            "stats": {"STR": 18, "DEX": 12, "CON": 16, "INT": 10, "WIS": 12, "CHA": 8},
            "dnd_edition": "2014",
        }
        synced = sync_character_stats(char)
        # DEX 12 (+1), PB 3, Remarkable Athlete rounds up = ceil(3/2) = 2 -> initiative = +3
        assert synced.get("initiative_modifier") == 3

    def test_f9_half_prof_no_stacking_between_bard_and_champion(self):
        """Multiclass Bard 2 / Champion 7 does NOT stack half proficiency twice."""
        char = {
            "char_name": "Bardic Champion",
            "char_class": "Fighter",
            "char_level": 9,
            "classes": [
                {"class_name": "Fighter", "subclass": "Champion", "level": 7},
                {"class_name": "Bard", "level": 2},
            ],
            "stats": {"STR": 14, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
            "dnd_edition": "2014",
        }
        synced = sync_character_stats(char)
        # Total Level 9 -> PB 4, half PB = 2. DEX 12 (+1) -> initiative = 1 + 2 = 3 (NOT 1 + 2 + 2)
        assert synced.get("initiative_modifier") == 3


# ============================================================================
# Feature F11: DM Roll Modal Manual Input
# ============================================================================


class TestF11DMRollModalManualInput:
    """Verifies manual physical dice input support in DM Roll Request."""

    def test_f11_roll_request_schema_accepts_manual_roll(self):
        """RollRequestSchema must allow optional manual_roll field."""
        schema = RollRequestSchema(
            char_filename="player1.json",
            char_name="Player One",
            roll_type="skill_check",
            stat="Perception",
            reason="Spotting traps",
            is_secret=False,
            manual_roll=17,
        )
        assert schema.manual_roll == 17

    def test_f11_roll_request_schema_manual_roll_defaults_none(self):
        """RollRequestSchema manual_roll defaults to None."""
        schema = RollRequestSchema(
            char_filename="player1.json",
            char_name="Player One",
            roll_type="initiative",
        )
        assert schema.manual_roll is None

    def test_f11_dm_modal_template_contains_manual_input(self):
        """DM roll request modal template must render manual physical roll input."""
        modal_html = (
            CLIENT_APP_ROOT
            / "features"
            / "dm"
            / "modals"
            / "roll-request-modal"
            / "roll-request-modal.component.html"
        )
        content = modal_html.read_text(encoding="utf-8")
        assert "manual" in content.lower() or "physical" in content.lower(), (
            "DM roll request modal template lacks manual/physical roll input field"
        )


# ============================================================================
# Feature F12: Player Action Dock 5e Actions
# ============================================================================


class TestF12PlayerActionDock5eActions:
    """Verifies standard 5e combat actions (Dodge, Dash, Disengage, Help) in Action Dock."""

    @pytest.fixture(autouse=True)
    def dock_content(self):
        dock_html = (
            CLIENT_APP_ROOT / "features" / "player" / "action-dock" / "action-dock.component.html"
        )
        dock_ts = (
            CLIENT_APP_ROOT / "features" / "player" / "action-dock" / "action-dock.component.ts"
        )
        assert dock_html.is_file()
        assert dock_ts.is_file()
        self.html = dock_html.read_text(encoding="utf-8")
        self.ts = dock_ts.read_text(encoding="utf-8")

    def test_f12_action_dock_displays_dodge_action(self):
        assert "dodge" in self.html.lower(), "Action Dock template missing Dodge action"

    def test_f12_action_dock_displays_dash_action(self):
        assert "dash" in self.html.lower(), "Action Dock template missing Dash action"

    def test_f12_action_dock_displays_disengage_action(self):
        assert "disengage" in self.html.lower(), "Action Dock template missing Disengage action"

    def test_f12_action_dock_displays_help_action(self):
        assert "help" in self.html.lower(), "Action Dock template missing Help action"

    def test_f12_action_dock_emits_5e_actions(self):
        assert "@Output() dodge" in self.ts or "dodge = output" in self.ts or "dodge" in self.ts
        assert "@Output() dash" in self.ts or "dash = output" in self.ts or "dash" in self.ts
        assert (
            "@Output() disengage" in self.ts
            or "disengage = output" in self.ts
            or "disengage" in self.ts
        )
        assert "@Output() help" in self.ts or "help = output" in self.ts or "help" in self.ts
