"""Tier 4 E2E Test Suite: Real-World Tabletop & VTT Application Scenarios.

Verifies complete multi-client end-to-end tabletop workflows adhering strictly
to the tabletop-qa playtesting methodology across both gameplay modes:
1. In-Person Tabletop (Desktop DM >= 1024px + 2 Mobile Companion Players < 1024px)
2. Online Tactical VTT (Desktop DM >= 1024px + Desktop Online Player >= 1024px)
3. End-to-End DM Prep-to-Live Master Mode Transition Workflow
4. TabletopQASimulator Project Oracle Execution (scripts/qa/simulate_session.py)
5. Multi-Client Encounter Continuity & Mid-Combat Disconnect Recovery

Requirement: Comprehensive Tier 4 real-world game session simulations.
"""

import uuid

from fastapi.testclient import TestClient

from backend.repositories.rules_repository import RulesRepository
from scripts.qa.simulate_session import TabletopQASimulator
from tests.e2e.conftest import E2EAuthHelper


class TestTier4RealWorldSessionScenarios:
    """Simulates realistic tabletop and online VTT multi-client game sessions."""

    def test_t4_01_tabletop_qa_simulator_oracle_full_pass(self):
        """TC-T4-01: Direct invocation of TabletopQASimulator oracle in 'both' mode."""
        sim = TabletopQASimulator()
        sim.setup()
        try:
            # 1. Run In-Person Tabletop scenario
            t_res = sim.run_tabletop_scenario()
            assert t_res.get("status") == "PASSED", (
                f"Tabletop scenario failed: {t_res.get('error')}"
            )

            # 2. Run Online VTT scenario
            v_res = sim.run_online_vtt_scenario()
            assert v_res.get("status") == "PASSED", f"VTT scenario failed: {v_res.get('error')}"
        finally:
            sim.teardown()

    def test_t4_02_in_person_tabletop_hybrid_session_simulation(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-T4-02: In-Person Hybrid Tabletop Flow with 1 DM and 2 Mobile Players."""
        # 1. DM registers and creates 2024 campaign
        dm_headers = auth_helper.register_and_login("dm_hybrid_t4", "dm_hybrid_t4@test.dnd")
        c_name = f"Campaign_Hybrid_{uuid.uuid4().hex[:6]}"
        camp_res = e2e_client.post(
            "/api/v1/campaigns/",
            json={"campaign_name": c_name, "dnd_edition": "2024 Revision"},
            headers=dm_headers,
        )
        assert camp_res.status_code == 200

        invite_res = e2e_client.post(f"/api/v1/campaigns/{c_name}/invite-code", headers=dm_headers)
        invite_code = invite_res.json()["invite_code"]

        # 2. Two mobile companion players register and join
        p1_headers = auth_helper.register_and_login("p1_sorc_t4", "p1_sorc_t4@test.dnd")
        p2_headers = auth_helper.register_and_login("p2_pal_t4", "p2_pal_t4@test.dnd")

        char1 = e2e_client.post(
            "/api/v1/characters",
            json={
                "char_name": "Valen",
                "char_class": "Sorcerer",
                "char_level": 2,
                "classes": [{"class_name": "Sorcerer", "level": 2}],
                "race": "Tiefling",
                "background": "Sage",
                "dnd_edition": "2024 Revision",
                "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 17},
            },
            headers=p1_headers,
        ).json()
        char2 = e2e_client.post(
            "/api/v1/characters",
            json={
                "char_name": "Thorne",
                "char_class": "Paladin",
                "char_level": 2,
                "classes": [{"class_name": "Paladin", "level": 2}],
                "race": "Human",
                "background": "Soldier",
                "dnd_edition": "2024 Revision",
                "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 16},
            },
            headers=p2_headers,
        ).json()

        char1_id = char1["char_id"]
        char2_id = char2["char_id"]

        e2e_client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": invite_code, "character_id": char1_id},
            headers=p1_headers,
        )
        e2e_client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": invite_code, "character_id": char2_id},
            headers=p2_headers,
        )

        # 3. DM issues group Initiative Roll Request
        req_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/roll-request",
            json={
                "char_filename": "all.json",
                "char_name": "ALL",
                "roll_type": "initiative",
                "stat": "DEX",
                "reason": "Goblin Ambush Initiative!",
                "is_secret": False,
            },
            headers=dm_headers,
        )
        assert req_res.status_code == 200
        roll_requests = req_res.json().get("requests", [])
        assert len(roll_requests) == 2

        # 4. Mobile players submit physical dice values (P1=18, P2=14)
        e2e_client.post(
            f"/api/v1/campaigns/{c_name}/roll-request/{roll_requests[0]['id']}/result",
            json={
                "total": 18,
                "expression": "1d20 + 2",
                "raw": 16,
                "modifier": 2,
                "mode": "normal",
            },
            headers=p1_headers,
        )
        e2e_client.post(
            f"/api/v1/campaigns/{c_name}/roll-request/{roll_requests[1]['id']}/result",
            json={
                "total": 14,
                "expression": "1d20 + 1",
                "raw": 13,
                "modifier": 1,
                "mode": "normal",
            },
            headers=p2_headers,
        )

        # 5. DM damages P1 (HP 14 -> 6) and applies 'Poisoned' condition
        patch_res = e2e_client.patch(
            f"/api/v1/campaigns/{c_name}/party/{char1_id}/state",
            json={"hp_current": 6, "conditions": ["Poisoned"]},
            headers=dm_headers,
        )
        assert patch_res.status_code == 200

        # 6. Verify P1 state reflects damage and condition
        updated_p1 = e2e_client.get(f"/api/v1/characters/{char1_id}", headers=p1_headers).json()
        assert updated_p1["hp_current"] == 6
        assert "Poisoned" in updated_p1["conditions"]

    def test_t4_03_online_vtt_tactical_combat_session_simulation(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-T4-03: Online VTT session simulation with tactical map, secret rolls, and notes."""
        dm_headers = auth_helper.register_and_login("dm_vtt_t4", "dm_vtt_t4@test.dnd")
        c_name = f"Campaign_VTT_{uuid.uuid4().hex[:6]}"
        e2e_client.post(
            "/api/v1/campaigns/",
            json={"campaign_name": c_name, "dnd_edition": "2024 Revision"},
            headers=dm_headers,
        )

        player_headers = auth_helper.register_and_login("player_vtt_t4", "player_vtt_t4@test.dnd")
        inv_res = e2e_client.post(f"/api/v1/campaigns/{c_name}/invite-code", headers=dm_headers)
        code = inv_res.json()["invite_code"]

        rogue = e2e_client.post(
            "/api/v1/characters",
            json={
                "char_name": "Shadow",
                "char_class": "Rogue",
                "subclass": "Thief",
                "char_level": 3,
                "classes": [{"class_name": "Rogue", "level": 3, "subclass": "Thief"}],
                "race": "Elf",
                "background": "Criminal",
                "dnd_edition": "2024 Revision",
                "stats": {"STR": 10, "DEX": 18, "CON": 14, "INT": 12, "WIS": 14, "CHA": 10},
                "skills": {"Stealth": 8, "Perception": 4},
            },
            headers=player_headers,
        ).json()
        rogue_id = rogue["char_id"]
        join_res = e2e_client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": code, "character_id": rogue_id},
            headers=player_headers,
        )
        assert join_res.status_code == 200

        # 1. DM executes secret Stealth check on rogue's behalf
        secret_roll = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/roll-request",
            json={
                "char_filename": f"{rogue_id}.json",
                "char_name": rogue["char_name"],
                "roll_type": "skill_check",
                "stat": "Stealth",
                "reason": "Scouting ahead in dungeon shadows",
                "is_secret": True,
            },
            headers=dm_headers,
        )
        assert secret_roll.status_code == 200
        res_data = secret_roll.json()
        assert res_data.get("request", {}).get("is_secret") is True

        # 2. DM publishes session recap note to timeline
        note_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/notes",
            json={"notes": "The rogue slipped past the sleeping guards without raising the alarm."},
            headers=dm_headers,
        )
        assert note_res.status_code == 200

        # 3. Fetch party state reflecting the joined player
        party_res = e2e_client.get(f"/api/v1/campaigns/{c_name}/party", headers=dm_headers)
        assert party_res.status_code == 200
        party = party_res.json()
        assert len(party) == 1
        assert party[0]["char_name"] == "Shadow"

    def test_t4_04_dm_prep_to_live_encounter_workflow(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """TC-T4-04: Full DM preparation to live encounter workflow across master modes."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle",
            lambda loc, ed: "## The Riddle of the Obsidian Gate",
        )
        dm_headers = auth_helper.register_and_login("dm_workflow_t4", "dm_workflow_t4@test.dnd")
        c_name = f"Campaign_Workflow_{uuid.uuid4().hex[:6]}"
        e2e_client.post("/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers)

        # Step 1: DM in Preparation Mode generates room riddle
        riddle_res = e2e_client.post(
            "/api/v1/dm/riddle",
            json={"location": "Obsidian Gate", "edition": "2024 Revision"},
            headers=dm_headers,
        )
        assert riddle_res.status_code == 200
        riddle_text = riddle_res.json()["riddle_markdown"]
        assert "Obsidian" in riddle_text

        # Step 2: DM inspects SRD monsters via RulesRepository
        repo = RulesRepository()
        dragons = repo.search_monsters(query="dragon", edition="2014")
        assert len(dragons) > 0
        boss_dragon = dragons[0]

        # Step 3: Transition to Live DM mode: Initialize combat encounter
        combatants = [
            {
                "id": str(uuid.uuid4()),
                "name": boss_dragon["name"],
                "ac": boss_dragon["ac"],
                "hp": boss_dragon["hp"],
                "max_hp": boss_dragon["hp"],
                "initiative": 15,
                "dex": boss_dragon.get("stats", {}).get("dex", 10),
                "is_player": False,
                "actions": boss_dragon.get("actions", []),
            }
        ]
        enc_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/encounter",
            json={
                "round": 1,
                "activeCombatantId": combatants[0]["id"],
                "combatants": combatants,
            },
            headers=dm_headers,
        )
        assert enc_res.status_code == 200

        # Verify active encounter is available on live reload
        live_enc = e2e_client.get(
            f"/api/v1/campaigns/{c_name}/encounter", headers=dm_headers
        ).json()
        assert live_enc["round"] == 1
        assert len(live_enc["combatants"]) == 1
        assert live_enc["combatants"][0]["name"] == boss_dragon["name"]

        # Step 4: Execute 1-click attack roll for monster action using DiceService
        from backend.services.dice_service import roll_dice

        assert len(boss_dragon.get("actions", [])) > 0, "Boss dragon must have structured actions"
        attack_actions = [
            a for a in boss_dragon.get("actions", []) if a.get("attack_bonus") is not None
        ]
        action = attack_actions[0] if attack_actions else boss_dragon["actions"][0]
        bonus = action.get("attack_bonus", 5)
        attack_roll = roll_dice(f"1d20+{bonus}")
        assert attack_roll["sides"] == 20
        assert attack_roll["num_dice"] == 1
        assert attack_roll["modifier"] == bonus
        assert attack_roll["total"] == attack_roll["raw_result"] + bonus
        assert 1 <= attack_roll["raw_result"] <= 20
        assert 1 + bonus <= attack_roll["total"] <= 20 + bonus

        if action.get("damage_dice"):
            damage_roll = roll_dice(action["damage_dice"])
            assert damage_roll["total"] == damage_roll["raw_result"] + damage_roll["modifier"]

    def test_t4_05_mid_combat_reconnect_continuity(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-T4-05: Multi-client combat encounter state survives client reconnect and page reload."""
        dm_headers = auth_helper.register_and_login("dm_recon_t4", "dm_recon_t4@test.dnd")
        c_name = f"Campaign_Recon_{uuid.uuid4().hex[:6]}"
        e2e_client.post("/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers)

        # Initialize combat encounter
        put_res = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/encounter",
            json={
                "round": 2,
                "activeCombatantId": "goblin_1",
                "combatants": [
                    {
                        "id": "goblin_1",
                        "name": "Goblin Sneak",
                        "initiative": 18,
                        "hp": 7,
                        "max_hp": 7,
                        "ac": 15,
                        "dex": 14,
                        "is_player": False,
                    }
                ],
            },
            headers=dm_headers,
        )
        assert put_res.status_code == 200

        # GET encounter state on reconnect / page refresh
        enc_res = e2e_client.get(f"/api/v1/campaigns/{c_name}/encounter", headers=dm_headers)
        assert enc_res.status_code == 200
        state = enc_res.json()
        assert state is not None
        assert state["round"] == 2
        assert len(state["combatants"]) == 1
        assert state["combatants"][0]["name"] == "Goblin Sneak"
