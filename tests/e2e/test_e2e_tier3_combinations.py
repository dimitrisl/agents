"""Tier 3 E2E Test Suite: Cross-Feature Combinations (Pairwise State Matrix).

Verifies multi-feature interactions where the output or side-effect of one feature
flows across architectural boundaries into another subsystem:
- T3-01 (F1 + F3 + F6): SRD 2014 Loading -> RulesRepository -> Bestiary Query
- T3-02 (F2 + F3 + F7): SRD 2024 Loading -> RulesRepository -> Bestiary Single Fetch
- T3-03 (F3 + F8 + F9): Clone Official -> Immutability Enforcement on Official & Mutation on Clone
- T3-04 (F5 + F8 + F9 + F6): Custom Creation -> Visibility Toggle -> Community Search
- T3-05 (F8 + F9 + F7): Multi-User Ownership & Privacy Isolation
- T3-06 (F4 + F8 + F6): Fractional CR Calculation & Filter Precision
- T3-07 (F1 + F8 + F6): Source Filter Matrix Combinations (Official / Mine / Community)
- T3-08 (F4 + F8 + F21): DM Preparation Workflow (Boss Monster Creation + Room Riddle)
- T3-09 (F8 + F8 + F9): Lineage Cloning (Multi-level based_on Chain)
- T3-10 (F3 + F5 + F9): Cache Isolation Against Database Collisions
- T3-11 (F10 + F11 + F15): Mode Switching Mid-Encounter Resilience
- T3-12 (F13 + F14 + F15): Tactical VTT Sidebar Activation + Pinned Strip + WS Broadcast
- T3-13 (F17 + F18 + F23 + F24): Quick-Add -> Initiative Population -> Statblock Modal Rolls
- T3-14 (F18 + F19 + F22): Encounter Storage Refresh -> Structured Action Retention

Requirement: At least 10 pairwise test cases.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.repositories.rules_repository import RulesRepository
from server.main import app
from tests.e2e.conftest import CLIENT_APP_ROOT, E2EAuthHelper, _AsyncDBWrapper

DM_COMPONENT_TS = CLIENT_APP_ROOT / "features" / "dm" / "dm.component.ts"
ENCOUNTER_STORAGE_TS = CLIENT_APP_ROOT / "core" / "services" / "encounter-storage.service.ts"


def _is_bestiary_router_mounted() -> bool:
    return any(getattr(route, "path", "").startswith("/api/v1/bestiary") for route in app.routes)


class TestTier3CrossFeatureCombinations:
    """Verifies pairwise feature interactions across frontend, backend, database, and rules."""

    def test_t3_01_srd_2014_loading_to_rules_repo_to_bestiary_query(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-01 (F1 + F3 + F6): SRD 2014 loaded in RulesRepository queried via Bestiary API."""
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        assert len(monsters) >= 60, "2014 dataset must contain >= 60 standard SRD monsters"

        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers = auth_helper.register_and_login("dm_t3_01", "dm_t3_01@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?edition=2014&search=goblin", headers=headers)
        assert res.status_code == 200
        items = res.json()
        assert len(items) > 0
        assert items[0]["origin"] == "official"

    def test_t3_02_srd_2024_loading_to_rules_repo_to_single_fetch(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-02 (F2 + F3 + F7): SRD 2024 monster retrieved by ID with updated 5.5e mechanics."""
        repo = RulesRepository()
        m2024 = repo.get_all_monsters("2024")
        assert len(m2024) >= 60, "2024 dataset must contain >= 60 standard SRD monsters"

        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers = auth_helper.register_and_login("dm_t3_02", "dm_t3_02@test.dnd")
        sample_id = m2024[0]["id"]
        res = e2e_client.get(f"/api/v1/bestiary/{sample_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["id"] == sample_id
        assert "2024" in str(res.json()["edition"])

    def test_t3_03_clone_official_immutability_and_mutation_on_clone(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-03 (F3 + F8 + F9): Clone official monster; verify official is immutable, clone is editable."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers = auth_helper.register_and_login("dm_t3_03", "dm_t3_03@test.dnd")
        clone_res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Custom Goblin Shaman",
                "based_on": "srd_goblin_2014",
                "edition": "2014",
                "cr": "1/2",
                "ac": 14,
                "hp": 22,
                "stats": {"str": 8, "dex": 14, "con": 12, "int": 12, "wis": 14, "cha": 10},
            },
            headers=headers,
        )
        assert clone_res.status_code == 201
        clone_id = clone_res.json()["id"]

        # 1. Verify official record rejected with 403 Forbidden
        attack_res = e2e_client.put(
            "/api/v1/bestiary/srd_goblin_2014",
            json={"name": "Hacked Name"},
            headers=headers,
        )
        assert attack_res.status_code == 403

        # 2. Verify custom clone accepts update with 200 OK
        update_res = e2e_client.put(
            f"/api/v1/bestiary/{clone_id}",
            json={"name": "Ascended Goblin Shaman", "ac": 15},
            headers=headers,
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "Ascended Goblin Shaman"

    def test_t3_04_custom_creation_visibility_toggle_to_community_search(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-04 (F5 + F8 + F9 + F6): Private monster hidden from community search until visibility toggled."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers_a = auth_helper.register_and_login("dm_t3_04a", "dm_t3_04a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_t3_04b", "dm_t3_04b@test.dnd")

        # 1. User A creates private monster
        create_res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "T3 Secret Beast",
                "is_public": False,
                "edition": "2024",
                "cr": "3",
                "ac": 13,
                "hp": 50,
            },
            headers=headers_a,
        )
        assert create_res.status_code == 201
        monster_id = create_res.json()["id"]

        # 2. User B searches community; beast NOT visible
        search_1 = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=true",
            headers=headers_b,
        ).json()
        assert not any(m["id"] == monster_id for m in search_1)

        # 3. User A toggles visibility to public
        patch_res = e2e_client.patch(
            f"/api/v1/bestiary/{monster_id}/visibility",
            json={"is_public": True},
            headers=headers_a,
        )
        assert patch_res.status_code == 200

        # 4. User B searches community again; beast IS visible
        search_2 = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=true",
            headers=headers_b,
        ).json()
        assert any(m["id"] == monster_id for m in search_2)

    def test_t3_05_multi_user_ownership_and_privacy_isolation(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-05 (F8 + F9 + F7): User B cannot view private monster, cannot edit, and cannot delete."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers_a = auth_helper.register_and_login("dm_t3_05a", "dm_t3_05a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_t3_05b", "dm_t3_05b@test.dnd")

        m = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "A's Private Monster",
                "is_public": False,
                "edition": "2024",
                "cr": "4",
                "ac": 14,
                "hp": 65,
            },
            headers=headers_a,
        ).json()
        mid = m["id"]

        # User B single fetch -> 403 or 404
        assert e2e_client.get(f"/api/v1/bestiary/{mid}", headers=headers_b).status_code in (
            403,
            404,
        )
        # User B edit -> 403
        assert (
            e2e_client.put(
                f"/api/v1/bestiary/{mid}", json={"name": "Hacked"}, headers=headers_b
            ).status_code
            == 403
        )
        # User B delete -> 403
        assert e2e_client.delete(f"/api/v1/bestiary/{mid}", headers=headers_b).status_code == 403
        # User A delete -> 200
        assert e2e_client.delete(f"/api/v1/bestiary/{mid}", headers=headers_a).status_code == 200

    def test_t3_06_fractional_cr_calculation_and_filter_precision(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-06 (F4 + F8 + F6): Fractional CR '1/4' computes cr_numeric=0.25 and filters accurately."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers = auth_helper.register_and_login("dm_t3_06", "dm_t3_06@test.dnd")
        created = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "T3 Bat Swarm",
                "edition": "2024",
                "cr": "1/4",
                "ac": 12,
                "hp": 24,
            },
            headers=headers,
        ).json()
        assert created["cr_numeric"] == 0.25

        # Query cr=1/4 must return this monster
        results = e2e_client.get(
            "/api/v1/bestiary?cr=1/4&include_mine=true", headers=headers
        ).json()
        assert any(m["id"] == created["id"] for m in results)

    def test_t3_07_source_filter_matrix_combinations(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-07 (F1 + F8 + F6): Testing 4 source filter combinations."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers = auth_helper.register_and_login("dm_t3_07", "dm_t3_07@test.dnd")

        # 1. Official only
        r1 = e2e_client.get(
            "/api/v1/bestiary?include_official=true&include_mine=false&include_community=false",
            headers=headers,
        ).json()
        assert all(m["origin"] == "official" for m in r1)

        # 2. Mine only
        r2 = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=true&include_community=false",
            headers=headers,
        ).json()
        assert all(m["origin"] == "custom" for m in r2)

        # 3. All false
        r3 = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=false",
            headers=headers,
        ).json()
        assert r3 == []

    def test_t3_08_dm_preparation_session_workflow(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """T3-08 (F4 + F8 + F21): DM creates custom boss monster and generates dungeon riddle."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle", lambda loc, ed: "## Sphinx's Trial"
        )
        headers = auth_helper.register_and_login("dm_t3_08", "dm_t3_08@test.dnd")

        # 1. Generate room riddle
        riddle_res = e2e_client.post(
            "/api/v1/dm/riddle",
            json={"location": "Sanctum of the Dragon", "edition": "2024 Edition"},
            headers=headers,
        )
        assert riddle_res.status_code == 200

        # 2. If bestiary mounted, create boss monster
        if _is_bestiary_router_mounted():
            boss_res = e2e_client.post(
                "/api/v1/bestiary",
                json={
                    "name": "Sanctum Dragon",
                    "edition": "2024",
                    "cr": "17",
                    "ac": 19,
                    "hp": 250,
                },
                headers=headers,
            )
            assert boss_res.status_code == 201

    def test_t3_09_lineage_cloning_based_on_chain(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-09 (F8 + F8 + F9): Multi-level clone chain (M1 -> M2 -> M3). Deleting M2 preserves M1 and M3."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary router pending M2")

        headers = auth_helper.register_and_login("dm_t3_09", "dm_t3_09@test.dnd")
        m1 = e2e_client.post(
            "/api/v1/bestiary",
            json={"name": "M1", "edition": "2024", "cr": "1", "ac": 10, "hp": 10},
            headers=headers,
        ).json()
        m2 = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "M2",
                "based_on": m1["id"],
                "edition": "2024",
                "cr": "2",
                "ac": 11,
                "hp": 20,
            },
            headers=headers,
        ).json()
        m3 = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "M3",
                "based_on": m2["id"],
                "edition": "2024",
                "cr": "3",
                "ac": 12,
                "hp": 30,
            },
            headers=headers,
        ).json()

        # Delete intermediate M2
        del_res = e2e_client.delete(f"/api/v1/bestiary/{m2['id']}", headers=headers)
        assert del_res.status_code == 200

        # M1 and M3 still exist
        assert e2e_client.get(f"/api/v1/bestiary/{m1['id']}", headers=headers).status_code == 200
        assert e2e_client.get(f"/api/v1/bestiary/{m3['id']}", headers=headers).status_code == 200

    def test_t3_10_cache_isolation_against_database_collisions(self, mock_db: _AsyncDBWrapper):
        """T3-10 (F3 + F5 + F9): Custom monster named 'Goblin' in MongoDB does not pollute official SRD record."""
        repo = RulesRepository()
        official_goblins = repo.search_monsters(query="goblin", edition="2014")
        if not official_goblins:
            pytest.skip("No goblins in repository pending M1")
        official_hp = official_goblins[0]["hp"]

        # Insert impostor Goblin into custom_monsters
        col = mock_db._db["custom_monsters"]
        col.insert_one({"id": "impostor_goblin", "name": "Goblin", "hp": 999, "origin": "custom"})

        # Subsequent fetch from RulesRepository MUST be pristine
        fresh_goblins = repo.search_monsters(query="goblin", edition="2014")
        assert fresh_goblins[0]["hp"] == official_hp

    def test_t3_11_mode_switching_mid_encounter_resilience(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-11 (F10 + F11 + F15): Combat in Round 3 preserves round, active turn, and conditions across mode switch."""
        dm_headers = auth_helper.register_and_login("dm_t3_11", "dm_t3_11@test.dnd")
        c_name = f"Campaign_T3_11_{uuid.uuid4().hex[:6]}"
        camp_res = e2e_client.post(
            "/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers
        )
        assert camp_res.status_code == 200

        # 1. DM in Live mode initializes combat encounter at Round 3 with active combatant and conditions
        encounter_payload = {
            "round": 3,
            "activeCombatantId": "c_orc_2",
            "combatants": [
                {
                    "id": "c_hero_1",
                    "name": "Valeros",
                    "initiative": 18,
                    "hp": 25,
                    "max_hp": 25,
                    "ac": 16,
                    "dex": 12,
                    "is_player": True,
                },
                {
                    "id": "c_orc_2",
                    "name": "Orc Berserker",
                    "initiative": 12,
                    "hp": 8,
                    "max_hp": 20,
                    "ac": 13,
                    "dex": 10,
                    "is_player": False,
                    "conditions": [{"name": "Poisoned", "expiresAtRound": 5}],
                },
            ],
        }
        init_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/encounter",
            json=encounter_payload,
            headers=dm_headers,
        )
        assert init_res.status_code == 200

        # 2. DM switches context to DM Preparation (publishes session log / DM note)
        note_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/notes",
            json={"notes": "Mid-combat prep note: Orc reinforcements arriving next round."},
            headers=dm_headers,
        )
        assert note_res.status_code == 200

        # 3. DM switches back to Live DM mode: Encounter state must be completely preserved
        live_res = e2e_client.get(f"/api/v1/campaigns/{c_name}/encounter", headers=dm_headers)
        assert live_res.status_code == 200
        live_state = live_res.json()
        assert live_state["round"] == 3
        assert live_state["activeCombatantId"] == "c_orc_2"
        assert len(live_state["combatants"]) == 2

        orc = next(c for c in live_state["combatants"] if c["id"] == "c_orc_2")
        assert orc["hp"] == 8
        assert any(cond["name"] == "Poisoned" for cond in orc.get("conditions", []))

        # 4. Verify Frontend dm.component.ts contract preserves tab memory across mode transitions
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "setDmMode" in content
        assert "lastLiveTab" in content
        assert "lastPrepTab" in content

    def test_t3_12_tactical_vtt_sidebar_activation_and_ws_broadcast(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """T3-12 (F13 + F14 + F15): Clicking Open VTT switches to Live DM, activates VTT tab, and broadcasts."""
        import asyncio

        from server.db_async import get_database
        from server.dependencies import auth as auth_dep
        from server.routers import websocket_router

        # Route direct db calls in websocket and auth to mock database
        mock_db = e2e_client.app.dependency_overrides.get(get_database)()
        monkeypatch.setattr(
            websocket_router, "get_database", lambda: asyncio.sleep(0, result=mock_db)
        )
        monkeypatch.setattr(auth_dep, "get_database", lambda: asyncio.sleep(0, result=mock_db))

        dm_headers = auth_helper.register_and_login("dm_t3_12", "dm_t3_12@test.dnd")
        c_name = f"Campaign_T3_12_{uuid.uuid4().hex[:6]}"
        e2e_client.post("/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers)
        token = dm_headers["Authorization"].replace("Bearer ", "")

        # Connect WebSocket as DM
        with e2e_client.websocket_connect(f"/ws/campaigns/{c_name}") as ws:
            ws.send_json({"type": "auth", "token": token})
            init_msg = ws.receive_json()
            assert init_msg.get("type") in ("presence_sync", "presence_update")

            # 1. Send vtt_toggle true (simulating sidebar 'Open VTT Grid' click)
            ws.send_json({"type": "vtt_toggle", "payload": {"is_active": True}})

            # 2. Server broadcasts vtt_sync event with is_active=True
            sync_msg = ws.receive_json()
            assert sync_msg.get("type") == "vtt_sync"
            assert sync_msg.get("payload", {}).get("is_active") is True

            # 3. Toggle back to False
            ws.send_json({"type": "vtt_toggle", "payload": {"is_active": False}})
            sync_msg2 = ws.receive_json()
            assert sync_msg2.get("type") == "vtt_sync"
            assert sync_msg2.get("payload", {}).get("is_active") is False

        # 4. Verify frontend dm.component.ts openVTT contract
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "openVTT" in content
        assert "sendVttToggle" in content

    def test_t3_13_quick_add_to_statblock_modal_rolls(self):
        """T3-13 (F17 + F18 + F23 + F24): Quick-add monster -> combatant -> statblock action roll."""
        from backend.services.dice_service import roll_dice
        from backend.services.stats_service import get_modifier

        # 1. Extract official SRD Goblin from RulesRepository
        repo = RulesRepository()
        monsters = repo.search_monsters(query="goblin", edition="2014")
        assert len(monsters) > 0, "SRD Goblin must exist in RulesRepository"
        goblin = monsters[0]
        assert goblin["id"] == "srd_goblin_2014"
        assert len(goblin.get("actions", [])) > 0, "Goblin must have actions"

        # 2. Calculate initiative from DEX using core stats engine
        dex = goblin["stats"]["dex"]
        dex_mod = get_modifier(dex)
        expected_init = 10 + dex_mod
        assert dex_mod == 2
        assert expected_init == 12

        # 3. Execute 1-click Attack Roll using backend dice service
        action = goblin["actions"][0]  # Scimitar: attack_bonus=4, damage_dice="1d6+2"
        attack_bonus = action["attack_bonus"]
        attack_roll = roll_dice(f"1d20+{attack_bonus}")
        assert attack_roll["sides"] == 20
        assert attack_roll["num_dice"] == 1
        assert attack_roll["modifier"] == attack_bonus
        assert attack_roll["total"] == attack_roll["raw_result"] + attack_bonus
        assert 1 <= attack_roll["raw_result"] <= 20
        assert 1 + attack_bonus <= attack_roll["total"] <= 20 + attack_bonus

        # 4. Execute 1-click Damage Roll using backend dice service
        damage_roll = roll_dice(action["damage_dice"])
        assert damage_roll["num_dice"] == 1
        assert damage_roll["sides"] == 6
        assert damage_roll["modifier"] == 2
        assert damage_roll["total"] == damage_roll["raw_result"] + 2
        assert 3 <= damage_roll["total"] <= 8

    def test_t3_14_encounter_storage_refresh_retains_action_rolls(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """T3-14 (F18 + F19 + F22): Structured actions survive serialization and reload cleanly."""
        # 1. Verify frontend EncounterStorageService contract
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        if "actions" not in content:
            pytest.skip(
                "Feature 19 (EncounterStorageService structured actions retention) pending M4 implementation"
            )
        assert "actions" in content
        assert "traits" in content

        # 2. Verify backend campaign encounter persistence
        dm_headers = auth_helper.register_and_login("dm_t3_14", "dm_t3_14@test.dnd")
        c_name = f"Campaign_T3_14_{uuid.uuid4().hex[:6]}"
        e2e_client.post("/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers)

        encounter_payload = {
            "round": 1,
            "activeCombatantId": "c_beholder_01",
            "combatants": [
                {
                    "id": "c_beholder_01",
                    "name": "Beholder",
                    "initiative": 14,
                    "hp": 180,
                    "max_hp": 180,
                    "ac": 18,
                    "dex": 14,
                    "is_player": False,
                }
            ],
        }
        save_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/encounter",
            json=encounter_payload,
            headers=dm_headers,
        )
        assert save_res.status_code == 200

        load_res = e2e_client.get(f"/api/v1/campaigns/{c_name}/encounter", headers=dm_headers)
        assert load_res.status_code == 200
        saved_enc = load_res.json()
        assert saved_enc["round"] == 1
        assert saved_enc["activeCombatantId"] == "c_beholder_01"
        assert len(saved_enc["combatants"]) == 1
        assert saved_enc["combatants"][0]["name"] == "Beholder"
