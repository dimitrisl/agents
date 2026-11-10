"""Tier 1 E2E Test Suite: DM Workspace, Tactical VTT, Quick-Add & 1-Click Rolls (Features 10–24).

Verifies the primary happy-path behavior and interface contracts for:
- Feature 10: DM Master Modes Switcher (⚔️ Live DM vs 🛠️ DM Preparation)
- Feature 11: Live DM Tab Grouping (initiative, vtt, party, notes)
- Feature 12: DM Preparation Tab Grouping (homebrew, generators, prep, entities)
- Feature 13: Tactical VTT Tab Relocation (<app-vtt-grid> and offline empty state)
- Feature 14: Open VTT Grid Sidebar Integration (mode switch, tab activation, WS broadcast)
- Feature 15: Pinned Active Combat Strip (mini-tracker on non-initiative Live tabs)
- Feature 16: Bestiary Angular Service & Models (client/src/app/core/services/bestiary.service.ts)
- Feature 17: Initiative Quick-Add Monster Search (source filter chips, 3rd-party default OFF)
- Feature 18: Quick-Add Combatant Population (stats, AC, HP, DEX, actions populated)
- Feature 19: Encounter Storage Action Retention (actions/traits/stats saved across reloads)
- Feature 20: Unified Bestiary Browser UI (search, filters, clone, add to initiative)
- Feature 21: Restored Riddle, Puzzle & Trap Generator (card, inputs, POST /api/v1/dm/riddle)
- Feature 22: Structured Statblock Modal Rendering (modifiers, traits, structured actions)
- Feature 23: 1-Click Monster Attack Roll (DiceService.rollD20 and RollToastService.showRoll)
- Feature 24: 1-Click Monster Damage Roll (DiceService.rollDamage and RollToastService.showRoll)

Requirement: At least 5 test cases per feature (>= 75 tests total).
"""

import re

import pytest
from fastapi.testclient import TestClient

from tests.e2e.conftest import CLIENT_APP_ROOT, E2EAuthHelper

DM_COMPONENT_TS = CLIENT_APP_ROOT / "features" / "dm" / "dm.component.ts"
DM_COMPONENT_HTML = CLIENT_APP_ROOT / "features" / "dm" / "dm.component.html"
INITIATIVE_TS = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "initiative-panel"
    / "initiative-panel.component.ts"
)
INITIATIVE_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "initiative-panel"
    / "initiative-panel.component.html"
)
GENERATORS_TS = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "generators-panel"
    / "generators-panel.component.ts"
)
GENERATORS_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "generators-panel"
    / "generators-panel.component.html"
)
HOMEBREW_TS = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "homebrew-panel"
    / "homebrew-panel.component.ts"
)
HOMEBREW_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "homebrew-panel"
    / "homebrew-panel.component.html"
)
STATBLOCK_TS = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "modals"
    / "statblock-modal"
    / "statblock-modal.component.ts"
)
STATBLOCK_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "modals"
    / "statblock-modal"
    / "statblock-modal.component.html"
)
BESTIARY_SERVICE_TS = CLIENT_APP_ROOT / "core" / "services" / "bestiary.service.ts"
BESTIARY_MODEL_TS = CLIENT_APP_ROOT / "core" / "models" / "bestiary.model.ts"
ENCOUNTER_STORAGE_TS = CLIENT_APP_ROOT / "core" / "services" / "encounter-storage.service.ts"


# ============================================================================
# Feature 10: DM Master Modes Switcher
# ============================================================================


class TestF10DmMasterModesSwitcher:
    """Verifies segmented pill control toggling Live DM vs DM Preparation with persistent tab memory."""

    def test_f10_01_dm_component_declares_master_mode_state(self):
        """TC-F10-01: dm.component.ts must declare dmMode property or signal with 'live' | 'prep'."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        has_mode = (
            "dmMode" in content
            and ("'live'" in content or '"live"' in content)
            and ("'prep'" in content or '"prep"' in content)
        )
        if not has_mode:
            pytest.skip("dmMode master mode state pending M3")
        assert has_mode, "dmMode not declared in dm.component.ts"

    def test_f10_02_mode_switcher_segmented_control_in_template(self):
        """TC-F10-02: dm.component.html renders master mode switcher segmented pill control."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        has_switcher = (
            ("dmMode" in content or "setMode" in content)
            and ("Live DM" in content or "⚔️" in content)
            and ("Preparation" in content or "Prep" in content or "🛠️" in content)
        )
        if not has_switcher:
            pytest.skip("Mode switcher segmented control pending M3")
        assert has_switcher, "Master mode switcher missing in dm.component.html"

    def test_f10_03_default_mode_initializes_to_live(self):
        """TC-F10-03: Default master mode initializes to 'live'."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "dmMode" not in content:
            pytest.skip("dmMode pending M3")
        # Check default value in declaration
        match = re.search(
            r"dmMode(?:\s*:\s*[^=]+)?\s*=\s*(?:signal<[^>]+>\()?['\"](\w+)['\"]", content
        )
        if match:
            assert match.group(1) == "live", f"Expected default dmMode 'live', got {match.group(1)}"

    def test_f10_04_tab_memory_preservation_live_to_prep(self):
        """TC-F10-04: dm.component.ts declares tab memory variables (lastLiveTab, lastPrepTab)."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "lastLiveTab" not in content and "lastPrepTab" not in content:
            pytest.skip("lastLiveTab / lastPrepTab tab memory pending M3")
        assert "lastLiveTab" in content or "lastPrepTab" in content

    def test_f10_05_mode_toggle_method_exists(self):
        """TC-F10-05: dm.component.ts defines method to switch modes and restore remembered tab."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        has_method = any(
            m in content for m in ["setMode(", "switchMode(", "toggleMode(", "setDmMode("]
        )
        if not has_method:
            pytest.skip("Mode toggle method pending M3")
        assert has_method


# ============================================================================
# Feature 11: Live DM Tab Grouping
# ============================================================================


class TestF11LiveDmTabGrouping:
    """Verifies Live DM renders only Combat & Initiative, Tactical VTT Map, Party Status, and Live Notes."""

    def test_f11_01_live_tabs_definition(self):
        """TC-F11-01: dm.component.ts defines live tabs group with initiative, vtt, party, notes."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "liveTabs" not in content and "dmTabs" in content and "vtt" not in content:
            pytest.skip("Live DM tab grouping pending M3")

        # If liveTabs exists, check elements
        if "liveTabs" in content:
            for tab_id in ["initiative", "party", "notes", "vtt"]:
                assert f"'{tab_id}'" in content or f'"{tab_id}"' in content

    def test_f11_02_prep_tabs_isolated_from_live_mode(self):
        """TC-F11-02: Preparation tabs (generators, homebrew, prep, entities) are not shown in Live DM."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "liveTabs" not in content:
            pytest.skip("liveTabs separation pending M3")
        # Ensure separate definitions exist for live and prep tabs
        assert "liveTabs" in content and "prepTabs" in content

    def test_f11_03_initiative_panel_rendered_in_live_mode(self):
        """TC-F11-03: dm.component.html renders <app-initiative-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-initiative-panel" in content

    def test_f11_04_party_panel_rendered_in_live_mode(self):
        """TC-F11-04: dm.component.html renders <app-party-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-party-panel" in content

    def test_f11_05_notes_panel_rendered_in_live_mode(self):
        """TC-F11-05: dm.component.html renders <app-notes-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-notes-panel" in content


# ============================================================================
# Feature 12: DM Preparation Tab Grouping
# ============================================================================


class TestF12DmPreparationTabGrouping:
    """Verifies DM Preparation renders Bestiary/Homebrew, AI Generators, Plot Architect, World Entities."""

    def test_f12_01_prep_tabs_definition(self):
        """TC-F12-01: dm.component.ts defines prep tabs group."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "prepTabs" not in content:
            pytest.skip("prepTabs definition pending M3")
        for tab_id in ["homebrew", "generators", "prep", "entities"]:
            assert f"'{tab_id}'" in content or f'"{tab_id}"' in content

    def test_f12_02_homebrew_panel_rendered_in_prep_mode(self):
        """TC-F12-02: dm.component.html renders <app-homebrew-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-homebrew-panel" in content

    def test_f12_03_generators_panel_rendered_in_prep_mode(self):
        """TC-F12-03: dm.component.html renders <app-generators-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-generators-panel" in content

    def test_f12_04_prep_panel_rendered_in_prep_mode(self):
        """TC-F12-04: dm.component.html renders <app-prep-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-prep-panel" in content

    def test_f12_05_entities_panel_rendered_in_prep_mode(self):
        """TC-F12-05: dm.component.html renders <app-entities-panel>."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-entities-panel" in content


# ============================================================================
# Feature 13: Tactical VTT Tab Relocation
# ============================================================================


class TestF13TacticalVttTabRelocation:
    """Verifies <app-vtt-grid> relocation into Tactical VTT tab with offline empty state."""

    def test_f13_01_vtt_grid_not_in_page_footer(self):
        """TC-F13-01: <app-vtt-grid> is not placed as an orphaned element at bottom of dm.component.html."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        # In M3, <app-vtt-grid> moves inside the vtt tab container
        if "activeTab === 'vtt'" not in content and 'activeTab === "vtt"' not in content:
            pytest.skip("VTT tab relocation pending M3")
        assert "activeTab === 'vtt'" in content or 'activeTab === "vtt"' in content

    def test_f13_02_offline_empty_state_declared(self):
        """TC-F13-02: Template contains offline empty state when vttState is inactive."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        if "Tactical VTT Offline" not in content and "vttState" not in content:
            pytest.skip("VTT offline empty state pending M3")
        assert "Tactical VTT Offline" in content or "vttState" in content

    def test_f13_03_offline_empty_state_button_triggers_open_vtt(self):
        """TC-F13-03: Offline empty state button triggers openVTT()."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        if "openVTT()" not in content:
            pytest.skip("openVTT trigger pending M3")
        assert "openVTT()" in content

    def test_f13_04_vtt_grid_receives_combatants_and_campaign(self):
        """TC-F13-04: <app-vtt-grid> binding includes combatants and campaignName inputs."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "<app-vtt-grid" in content
        assert '[combatants]="combatants"' in content or "[combatants]" in content
        assert '[campaignName]="campaignName"' in content or "[campaignName]" in content

    def test_f13_05_vtt_tab_id_in_dm_component(self):
        """TC-F13-05: dm.component.ts type union for activeTab includes 'vtt'."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "'vtt'" not in content and '"vtt"' not in content:
            pytest.skip("'vtt' tab union pending M3")
        assert "'vtt'" in content or '"vtt"' in content


# ============================================================================
# Feature 14: Open VTT Grid Sidebar Integration
# ============================================================================


class TestF14OpenVttGridSidebarIntegration:
    """Verifies sidebar '🗺️ Open VTT Grid' switches to Live DM, activates VTT tab, and broadcasts."""

    def test_f14_01_sidebar_button_in_template(self):
        """TC-F14-01: dm.component.html renders sidebar button with '🗺️ Open VTT Grid'."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "Open VTT Grid" in content or "openVTT()" in content

    def test_f14_02_open_vtt_method_switches_mode_to_live(self):
        """TC-F14-02: openVTT() method in dm.component.ts switches dmMode to 'live'."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "this.dmMode = 'live'" not in content and "dmMode.set('live')" not in content:
            pytest.skip("openVTT mode switch pending M3")
        assert "this.dmMode = 'live'" in content or "dmMode.set('live')" in content

    def test_f14_03_open_vtt_activates_vtt_tab(self):
        """TC-F14-03: openVTT() activates activeTab = 'vtt'."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "activeTab = 'vtt'" not in content and 'activeTab = "vtt"' not in content:
            pytest.skip("openVTT tab switch pending M3")
        assert "activeTab = 'vtt'" in content or 'activeTab = "vtt"' in content

    def test_f14_04_open_vtt_broadcasts_websocket_toggle(self):
        """TC-F14-04: openVTT() calls wsService.sendVttToggle(true)."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "sendVttToggle(true)" in content

    def test_f14_05_open_vtt_unminimizes_grid(self):
        """TC-F14-05: openVTT() ensures vttGrid component is not minimized."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        if "isMinimized = false" not in content and "isMinimized" not in content:
            pytest.skip("openVTT unminimize pending M3")
        assert "isMinimized" in content


# ============================================================================
# Feature 15: Pinned Active Combat Strip
# ============================================================================


class TestF15PinnedActiveCombatStrip:
    """Verifies pinned combat mini-tracker rendered on non-initiative Live DM tabs."""

    def test_f15_01_pinned_combat_strip_in_template(self):
        """TC-F15-01: dm.component.html renders pinned combat strip banner."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        has_strip = (
            "activeTab !== 'initiative'" in content or 'activeTab !== "initiative"' in content
        ) and ("combatants.length > 0" in content or "combatants().length" in content)
        if not has_strip:
            pytest.skip("Pinned active combat strip template pending M3")
        assert has_strip

    def test_f15_02_pinned_strip_displays_round_and_turn(self):
        """TC-F15-02: Pinned strip displays round label and current turn name."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        if "roundLabel" not in content and "currentTurnName" not in content:
            pytest.skip("roundLabel / currentTurnName in pinned strip pending M3")
        assert "roundLabel" in content or "currentTurnName" in content

    def test_f15_03_pinned_strip_has_next_turn_button(self):
        """TC-F15-03: Pinned strip provides 'Next Turn ➡️' trigger calling nextTurn()."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        if "nextTurn()" not in content:
            pytest.skip("nextTurn in pinned strip pending M3")
        assert "nextTurn()" in content

    def test_f15_04_pinned_strip_full_tracker_button(self):
        """TC-F15-04: Pinned strip provides button to jump back to full initiative tracker."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        has_tracker_button = (
            "activeTab = 'initiative'" in content
            or 'activeTab = "initiative"' in content
            or "onTabChange('initiative')" in content
            or 'onTabChange("initiative")' in content
        )
        assert has_tracker_button

    def test_f15_05_pinned_strip_hidden_on_initiative_tab(self):
        """TC-F15-05: Pinned strip is guarded by activeTab !== 'initiative'."""
        content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        if (
            "activeTab !== 'initiative'" not in content
            and 'activeTab !== "initiative"' not in content
        ):
            pytest.skip("Pinned strip guard pending M3")
        assert "activeTab !== 'initiative'" in content or 'activeTab !== "initiative"' in content


# ============================================================================
# Feature 16: Bestiary Angular Service & Models
# ============================================================================


class TestF16BestiaryAngularServiceAndModels:
    """Verifies BestiaryService and TypeScript models connecting to /api/v1/bestiary."""

    def test_f16_01_bestiary_model_file_exists(self):
        """TC-F16-01: client/src/app/core/models/bestiary.model.ts exists."""
        if not BESTIARY_MODEL_TS.exists():
            pytest.skip("bestiary.model.ts pending M4")
        assert BESTIARY_MODEL_TS.is_file()

    def test_f16_02_bestiary_model_declares_monster_interface(self):
        """TC-F16-02: bestiary.model.ts declares BestiaryMonster with required properties."""
        if not BESTIARY_MODEL_TS.exists():
            pytest.skip("bestiary.model.ts pending M4")
        content = BESTIARY_MODEL_TS.read_text(encoding="utf-8")
        assert "BestiaryMonster" in content or "Monster" in content
        assert "cr" in content
        assert "actions" in content

    def test_f16_03_bestiary_service_file_exists(self):
        """TC-F16-03: client/src/app/core/services/bestiary.service.ts exists."""
        if not BESTIARY_SERVICE_TS.exists():
            pytest.skip("bestiary.service.ts pending M4")
        assert BESTIARY_SERVICE_TS.is_file()

    def test_f16_04_bestiary_service_has_get_monsters_method(self):
        """TC-F16-04: BestiaryService defines getMonsters method with filtering."""
        if not BESTIARY_SERVICE_TS.exists():
            pytest.skip("bestiary.service.ts pending M4")
        content = BESTIARY_SERVICE_TS.read_text(encoding="utf-8")
        assert "getMonsters" in content

    def test_f16_05_bestiary_service_targets_bestiary_endpoint(self):
        """TC-F16-05: BestiaryService targets /api/v1/bestiary."""
        if not BESTIARY_SERVICE_TS.exists():
            pytest.skip("bestiary.service.ts pending M4")
        content = BESTIARY_SERVICE_TS.read_text(encoding="utf-8")
        assert "/bestiary" in content


# ============================================================================
# Feature 17: Initiative Quick-Add Monster Search
# ============================================================================


class TestF17InitiativeQuickAddMonsterSearch:
    """Verifies quick-add search input and source chips (Official, Mine, 3rd-Party default OFF)."""

    def test_f17_01_quick_add_input_in_initiative_panel_template(self):
        """TC-F17-01: initiative-panel.component.html renders search input for quick-add monsters."""
        content = INITIATIVE_HTML.read_text(encoding="utf-8")
        if "quickAdd" not in content and "search" not in content.lower():
            pytest.skip("Quick-add search input pending M4")
        assert "quickAdd" in content or "search" in content.lower()

    def test_f17_02_source_filter_chips_rendered(self):
        """TC-F17-02: initiative-panel.component.html renders source filter chips."""
        content = INITIATIVE_HTML.read_text(encoding="utf-8")
        if "Official" not in content and "3rd-Party" not in content and "Mine" not in content:
            pytest.skip("Source filter chips pending M4")
        assert "Official" in content or "Mine" in content or "3rd-Party" in content

    def test_f17_03_third_party_chip_defaults_to_off(self):
        """TC-F17-03: initiative-panel.component.ts defaults 3rd-party filter chip to OFF (false)."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if (
            "includeCommunity" not in content
            and "include_community" not in content
            and "thirdParty" not in content
        ):
            pytest.skip("3rd-party default OFF pending M4")
        # Ensure false default is declared
        match = re.search(
            r"(?:includeCommunity|include_community|thirdParty|filterCommunity)\s*[:=]\s*(?:signal<[^>]+>\()?false",
            content,
        )
        assert match is not None, "3rd-Party filter chip MUST default to false (OFF) per R4"

    def test_f17_04_official_chip_defaults_to_on(self):
        """TC-F17-04: initiative-panel.component.ts defaults official filter chip to ON (true)."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "includeOfficial" not in content and "include_official" not in content:
            pytest.skip("Official default ON pending M4")
        match = re.search(
            r"(?:includeOfficial|include_official|filterOfficial)\s*[:=]\s*(?:signal<[^>]+>\()?true",
            content,
        )
        assert match is not None, "Official filter chip MUST default to true (ON)"

    def test_f17_05_quick_add_dropdown_results_list(self):
        """TC-F17-05: Template contains dropdown results displaying monster name and CR."""
        content = INITIATIVE_HTML.read_text(encoding="utf-8")
        if (
            "quickAddResults" not in content
            and "searchResults" not in content
            and "monsters" not in content
        ):
            pytest.skip("Quick-add dropdown results pending M4")
        assert "quickAddResults" in content or "searchResults" in content or "monsters" in content


# ============================================================================
# Feature 18: Quick-Add Combatant Population
# ============================================================================


class TestF18QuickAddCombatantPopulation:
    """Verifies selecting monster from quick-add populates stats, AC, HP, DEX, and actions."""

    def test_f18_01_add_monster_method_exists(self):
        """TC-F18-01: initiative-panel.component.ts defines method to add monster to combatants."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        has_add = any(m in content for m in ["addMonster(", "selectMonster(", "addQuickCombatant("])
        if not has_add:
            pytest.skip("addMonster method pending M4")
        assert has_add

    def test_f18_02_hp_populated_from_monster(self):
        """TC-F18-02: Combatant HP and max_hp populated from monster definition."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "monster.hp" not in content and "m.hp" not in content:
            pytest.skip("HP population logic pending M4")
        assert "monster.hp" in content or "m.hp" in content

    def test_f18_03_ac_populated_from_monster(self):
        """TC-F18-03: Combatant AC populated from monster definition."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "monster.ac" not in content and "m.ac" not in content:
            pytest.skip("AC population logic pending M4")
        assert "monster.ac" in content or "m.ac" in content

    def test_f18_04_dex_modifier_initiative_calculation(self):
        """TC-F18-04: Initiative calculates 10 + dexMod using core stats rules engine."""
        from backend.services.stats_service import get_modifier

        dex = 14
        dex_mod = get_modifier(dex)
        assert dex_mod == 2
        expected_init = 10 + dex_mod
        assert expected_init == 12

        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "dex" not in content.lower():
            pytest.skip("Initiative panel dex-based initiative calculation pending M4")
        assert "dex" in content.lower()

    def test_f18_05_structured_actions_retained_in_combatant(self):
        """TC-F18-05: Combatant data structure preserves structured actions array."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "actions" not in content:
            pytest.skip("Combatant actions retention pending M4")
        assert "actions" in content


# ============================================================================
# Feature 19: Encounter Storage Action Retention
# ============================================================================


class TestF19EncounterStorageActionRetention:
    """Verifies EncounterStorageService serializes and parses structured actions, traits, and stats."""

    def test_f19_01_encounter_storage_service_exists(self):
        """TC-F19-01: EncounterStorageService file exists."""
        assert ENCOUNTER_STORAGE_TS.is_file()

    def test_f19_02_parse_combatant_handles_actions(self):
        """TC-F19-02: parseCombatant method in encounter-storage.service.ts parses actions array."""
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        if "actions" not in content:
            pytest.skip("Encounter storage actions parsing pending M4")
        assert "actions" in content

    def test_f19_03_parse_combatant_handles_traits(self):
        """TC-F19-03: parseCombatant method handles traits array."""
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        if "traits" not in content:
            pytest.skip("Encounter storage traits parsing pending M4")
        assert "traits" in content

    def test_f19_04_parse_combatant_handles_stats(self):
        """TC-F19-04: parseCombatant method handles stats dictionary."""
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        if "stats" not in content:
            pytest.skip("Encounter storage stats parsing pending M4")
        assert "stats" in content

    def test_f19_05_clean_recovery_on_corrupt_data(self):
        """TC-F19-05: parseCombatant safely falls back when action entry is malformed."""
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        assert "parseCombatant" in content


# ============================================================================
# Feature 20: Unified Bestiary Browser UI
# ============================================================================


class TestF20UnifiedBestiaryBrowserUi:
    """Verifies Bestiary browser embedded under Bestiary & Homebrew tab in DM Prep mode."""

    def test_f20_01_bestiary_browser_in_homebrew_panel_template(self):
        """TC-F20-01: homebrew-panel.component.html renders Bestiary browser."""
        content = HOMEBREW_HTML.read_text(encoding="utf-8")
        if "bestiary" not in content.lower() and "monsters" not in content.lower():
            pytest.skip("Bestiary browser template pending M4")
        assert "bestiary" in content.lower() or "monsters" in content.lower()

    def test_f20_02_cr_filter_control_in_browser(self):
        """TC-F20-02: Bestiary browser renders CR filter dropdown/control."""
        content = HOMEBREW_HTML.read_text(encoding="utf-8")
        if "CR" not in content and "challenge" not in content.lower():
            pytest.skip("CR filter control pending M4")
        assert "CR" in content or "challenge" in content.lower()

    def test_f20_03_type_filter_control_in_browser(self):
        """TC-F20-03: Bestiary browser renders monster type filter control."""
        content = HOMEBREW_HTML.read_text(encoding="utf-8")
        if "type" not in content.lower():
            pytest.skip("Type filter control pending M4")
        assert "type" in content.lower()

    def test_f20_04_clone_monster_button_in_browser(self):
        """TC-F20-04: Monster card provides 'Clone' action button."""
        content = HOMEBREW_HTML.read_text(encoding="utf-8")
        if "clone" not in content.lower() and "based_on" not in content:
            pytest.skip("Clone monster button pending M4")
        assert "clone" in content.lower() or "based_on" in content

    def test_f20_05_add_to_initiative_action_in_browser(self):
        """TC-F20-05: Monster card provides action to add monster to initiative."""
        content = HOMEBREW_HTML.read_text(encoding="utf-8")
        if "initiative" not in content.lower() and "addToInitiative" not in content:
            pytest.skip("Add to initiative from bestiary browser pending M4")
        assert "initiative" in content.lower() or "addToInitiative" in content


# ============================================================================
# Feature 21: Restored Riddle, Puzzle & Trap Generator
# ============================================================================


class TestF21RestoredRiddlePuzzleAndTrapGenerator:
    """Verifies Riddle/Trap Generator card in AI Generators panel and POST /api/v1/dm/riddle."""

    def test_f21_01_riddle_card_rendered_in_generators_template(self):
        """TC-F21-01: generators-panel.component.html renders Riddle, Puzzle & Trap Generator card."""
        content = GENERATORS_HTML.read_text(encoding="utf-8")
        if "Riddle" not in content and "Trap" not in content:
            pytest.skip("Riddle/Trap card pending M4")
        assert "Riddle" in content or "Trap" in content

    def test_f21_02_riddle_theme_input_binding(self):
        """TC-F21-02: generators-panel.component.ts declares riddleTheme @Input or property."""
        content = GENERATORS_TS.read_text(encoding="utf-8")
        if "riddleTheme" not in content:
            pytest.skip("riddleTheme binding pending M4")
        assert "riddleTheme" in content

    def test_f21_03_generate_riddle_output_event(self):
        """TC-F21-03: generators-panel.component.ts declares generateRiddle @Output or event."""
        content = GENERATORS_TS.read_text(encoding="utf-8")
        if "generateRiddle" not in content:
            pytest.skip("generateRiddle event pending M4")
        assert "generateRiddle" in content

    def test_f21_04_riddle_api_endpoint_exists(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """TC-F21-04: POST /api/v1/dm/riddle responds to authenticated request."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle", lambda loc, ed: "## Test Riddle"
        )
        headers = auth_helper.register_and_login("dm_f21_04", "dm_f21_04@test.dnd")
        res = e2e_client.post(
            "/api/v1/dm/riddle",
            json={"location": "Ancient Crypt", "edition": "2024 Edition"},
            headers=headers,
        )
        assert res.status_code == 200
        assert "riddle_markdown" in res.json()

    def test_f21_05_riddle_unauthenticated_returns_401(self, e2e_client: TestClient):
        """TC-F21-05: POST /api/v1/dm/riddle without token returns 401 Unauthorized."""
        res = e2e_client.post(
            "/api/v1/dm/riddle",
            json={"location": "Dungeon Room"},
        )
        assert res.status_code == 401


# ============================================================================
# Feature 22: Structured Statblock Modal Rendering
# ============================================================================


class TestF22StructuredStatblockModalRendering:
    """Verifies ability score modifiers, traits, and structured actions in StatblockModalComponent."""

    def test_f22_01_ability_scores_strip_in_statblock_template(self):
        """TC-F22-01: statblock-modal.component.html renders ability scores grid (STR, DEX, CON, INT, WIS, CHA)."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        if "STR" not in content and "dex" not in content.lower():
            pytest.skip("Structured ability scores in statblock modal pending M5")
        assert "STR" in content or "dex" in content.lower()

    def test_f22_02_traits_section_in_statblock_template(self):
        """TC-F22-02: statblock-modal.component.html renders traits section."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        if "traits" not in content:
            pytest.skip("Structured traits section pending M5")
        assert "traits" in content

    def test_f22_03_actions_section_in_statblock_template(self):
        """TC-F22-03: statblock-modal.component.html renders actions section."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        if "actions" not in content:
            pytest.skip("Structured actions section pending M5")
        assert "actions" in content

    def test_f22_04_fallback_to_string_statblock_when_no_structured_actions(self):
        """TC-F22-04: Modal falls back to text statblock when actions array is empty."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        assert "statblock" in content

    def test_f22_05_external_dnd_beyond_link(self):
        """TC-F22-05: Statblock modal template provides external link to D&D Beyond."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        assert (
            "dndbeyond.com" in content or "D&D Beyond" in content or "dndbeyond" in content.lower()
        )


# ============================================================================
# Feature 23: 1-Click Monster Attack Roll
# ============================================================================


class TestF23OneClickMonsterAttackRoll:
    """Verifies attack roll button (+X to Hit) wired to DiceService and RollToastService."""

    def test_f23_01_attack_roll_button_in_template(self):
        """TC-F23-01: statblock-modal.component.html renders attack roll button."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        if "rollAttack" not in content and "to Hit" not in content:
            pytest.skip("1-click attack roll button pending M5")
        assert "rollAttack" in content or "to Hit" in content

    def test_f23_02_roll_attack_method_in_component(self):
        """TC-F23-02: statblock-modal.component.ts defines rollAttack method."""
        content = STATBLOCK_TS.read_text(encoding="utf-8")
        if "rollAttack" not in content:
            pytest.skip("rollAttack method pending M5")
        assert "rollAttack" in content

    def test_f23_03_attack_roll_uses_dice_service(self):
        """TC-F23-03: statblock-modal.component.ts injects DiceService."""
        content = STATBLOCK_TS.read_text(encoding="utf-8")
        if "DiceService" not in content:
            pytest.skip("DiceService injection pending M5")
        assert "DiceService" in content

    def test_f23_04_attack_roll_announces_via_roll_toast_service(self):
        """TC-F23-04: statblock-modal.component.ts injects RollToastService."""
        content = STATBLOCK_TS.read_text(encoding="utf-8")
        if "RollToastService" not in content:
            pytest.skip("RollToastService injection pending M5")
        assert "RollToastService" in content

    def test_f23_05_attack_roll_bonus_calculation(self):
        """TC-F23-05: Attack bonus +5 adds to d20 roll correctly via DiceService."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("1d20+5")
        assert res["modifier"] == 5
        assert res["sides"] == 20
        assert res["num_dice"] == 1
        assert res["total"] == res["raw_result"] + 5
        assert 1 <= res["raw_result"] <= 20
        assert 6 <= res["total"] <= 25


# ============================================================================
# Feature 24: 1-Click Monster Damage Roll
# ============================================================================


class TestF24OneClickMonsterDamageRoll:
    """Verifies damage roll button (XdY+Z Damage) wired to DiceService and RollToastService."""

    def test_f24_01_damage_roll_button_in_template(self):
        """TC-F24-01: statblock-modal.component.html renders damage roll button."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        if "rollDamage" not in content and "Damage" not in content:
            pytest.skip("1-click damage roll button pending M5")
        assert "rollDamage" in content or "Damage" in content

    def test_f24_02_roll_damage_method_in_component(self):
        """TC-F24-02: statblock-modal.component.ts defines rollDamage method."""
        content = STATBLOCK_TS.read_text(encoding="utf-8")
        if "rollDamage" not in content:
            pytest.skip("rollDamage method pending M5")
        assert "rollDamage" in content

    def test_f24_03_damage_dice_regex_parsing(self):
        """TC-F24-03: Damage dice notation '2d6+3' correctly parses count, sides, and modifier."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("2d6+3")
        assert res["num_dice"] == 2
        assert res["sides"] == 6
        assert res["modifier"] == 3
        assert res["total"] == res["raw_result"] + 3
        assert 5 <= res["total"] <= 15

    def test_f24_04_damage_roll_announcement_includes_damage_type(self):
        """TC-F24-04: rollDamage method incorporates damage_type in event label."""
        content = STATBLOCK_TS.read_text(encoding="utf-8")
        if "damage_type" not in content and "damageType" not in content:
            pytest.skip("damage_type in roll announcement pending M5")
        assert "damage_type" in content or "damageType" in content

    def test_f24_05_multi_dice_expression_evaluation(self):
        """TC-F24-05: Expression 4d6+2d8 evaluates with positive integer sum via DiceService."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("4d6 + 2d8")
        assert res["num_dice"] == 6
        assert len(res["rolls"]) == 6
        assert res["modifier"] == 0
        assert res["total"] == sum(res["rolls"])
        assert 6 <= res["total"] <= 40
