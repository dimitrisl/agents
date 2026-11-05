#!/usr/bin/env python3
"""
Tabletop & Online Multi-Client QA Session Simulator for Phyrexian Forge.

Simulates live tabletop game flows with 1 DM and 2 Players:
1. In-Person Tabletop Mode: Mobile Companion viewport, Physical Dice manual inputs,
   Monsters-only initiative, Targeted Loot distribution, and Party State synchronization.
2. Online VTT Mode: Desktop viewports, Secret Rolls, Reality Recap publishing,
   and Player Reconnect resilience.

Can be run standalone:
    poetry run python scripts/qa/simulate_session.py --mode both
Or imported as a fixture/test in pytest.
"""

import argparse
import sys
import time
from typing import Any, Dict, List, Optional

import mongomock
from fastapi.testclient import TestClient

from backend.services.class_resources_service import _load_rules
from server.db_async import get_database
from server.main import app
from server.rate_limiter import limiter


class _AsyncCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def __iter__(self):
        return iter(self._cursor)

    async def __aiter__(self):
        for doc in self._cursor:
            yield doc

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        docs = list(self._cursor)
        if length is not None:
            docs = docs[:length]
        return docs


class _AsyncColWrapper:
    def __init__(self, col):
        self._col = col

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def insert_many(self, *args, **kwargs):
        return self._col.insert_many(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._col.find_one_and_update(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._col.find(*args, **kwargs))


class _AsyncDBWrapper:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return _AsyncColWrapper(self._db[name])

    def __getattr__(self, name):
        return _AsyncColWrapper(getattr(self._db, name))


class TabletopQASimulator:
    """Orchestrates multi-client simulations for in-person tabletop and online VTT."""

    def __init__(self, live_base_url: Optional[str] = None):
        self.live_base_url = live_base_url
        self.client: Optional[TestClient] = None
        self.db = None
        self.results: List[Dict[str, Any]] = []

    def setup(self):
        """Prepares the database override and TestClient."""
        limiter.reset()
        _load_rules.cache_clear()
        mock_client = mongomock.MongoClient()
        self.db = _AsyncDBWrapper(mock_client["phyrexian_forge_qa_simulation"])
        app.dependency_overrides[get_database] = lambda: self.db
        self.client = TestClient(app)

    def teardown(self):
        """Cleans up dependency overrides."""
        app.dependency_overrides.pop(get_database, None)

    def _register_user(self, username: str, email: str, role: str = "player") -> Dict[str, str]:
        limiter.reset()
        reg = self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": "Password123!"},
        )
        assert reg.status_code in (201, 200), f"Failed to register {username}: {reg.text}"

        login = self.client.post(
            "/api/v1/auth/login", data={"username": username, "password": "Password123!"}
        )
        assert login.status_code == 200, f"Failed to login {username}: {login.text}"
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def run_tabletop_scenario(self) -> Dict[str, Any]:
        """
        Simulates an In-Person Tabletop game:
        - DM on Desktop Laptop screen
        - 2 Players on Mobile Companion Viewport
        - Physical d20 roll submissions (manual input)
        - Targeted Loot distribution to single recipient
        - Party State synchronization (Damage & Conditions)
        """
        start_time = time.time()
        trace = []
        errors = []

        try:
            # 1. Setup DM & 2 Mobile Players
            dm_headers = self._register_user("dm_tabletop", "dm_tt@forge.dnd")
            p1_headers = self._register_user("p1_seraphina", "p1_tt@forge.dnd")
            p2_headers = self._register_user("p2_kaelen", "p2_tt@forge.dnd")
            trace.append("Registered DM and 2 Tabletop Players.")

            # 2. DM creates 2024 Campaign
            c_name = "Phyrexian In-Person Tabletop"
            c_res = self.client.post(
                "/api/v1/campaigns/",
                json={"campaign_name": c_name, "dnd_edition": "2024 Revision"},
                headers=dm_headers,
            )
            assert c_res.status_code == 200, f"Campaign creation failed: {c_res.text}"
            trace.append("DM created 2024 Campaign 'Phyrexian In-Person Tabletop'.")

            # 3. Get Invite Code and Join Party
            code_res = self.client.post(
                f"/api/v1/campaigns/{c_name}/invite-code", headers=dm_headers
            )
            invite_code = code_res.json()["invite_code"]

            # Create P1 character (2024 Sorcerer)
            p1_char = self.client.post(
                "/api/v1/characters",
                json={
                    "char_name": "Seraphina Vale",
                    "char_class": "Sorcerer",
                    "subclass": "Draconic Sorcery",
                    "char_level": 2,
                    "classes": [
                        {"class_name": "Sorcerer", "level": 2, "subclass": "Draconic Sorcery"}
                    ],
                    "race": "Tiefling",
                    "background": "Sage",
                    "dnd_edition": "2024 Revision",
                    "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 17},
                    "currency": {"gp": 15, "sp": 0, "cp": 0},
                    "weapons": [{"name": "Quarterstaff", "damage_dice": "1d6"}],
                    "equipment": [{"name": "Arcane Focus", "equipped": True}],
                },
                headers=p1_headers,
            ).json()
            p1_id = p1_char["char_id"]

            # Create P2 character (2024 Paladin)
            p2_char = self.client.post(
                "/api/v1/characters",
                json={
                    "char_name": "Kaelen Vane",
                    "char_class": "Paladin",
                    "char_level": 2,
                    "classes": [{"class_name": "Paladin", "level": 2}],
                    "race": "Human",
                    "background": "Soldier",
                    "dnd_edition": "2024 Revision",
                    "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 16},
                    "currency": {"gp": 20, "sp": 0, "cp": 0},
                    "weapons": [{"name": "Longsword", "damage_dice": "1d8"}],
                    "equipment": [{"name": "Chain Mail", "equipped": True, "ac_bonus": 16}],
                },
                headers=p2_headers,
            ).json()
            p2_id = p2_char["char_id"]

            # Both join party
            assert (
                self.client.post(
                    "/api/v1/campaigns/join",
                    json={"invite_code": invite_code, "character_id": p1_id},
                    headers=p1_headers,
                ).status_code
                == 200
            )
            assert (
                self.client.post(
                    "/api/v1/campaigns/join",
                    json={"invite_code": invite_code, "character_id": p2_id},
                    headers=p2_headers,
                ).status_code
                == 200
            )
            trace.append("Both mobile companion players joined the party.")

            # 4. DM sends a Group Roll Request ("ALL")
            roll_req = self.client.post(
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
            assert roll_req.status_code == 200, f"Roll request failed: {roll_req.text}"
            requests_created = roll_req.json().get("requests", [])
            assert len(requests_created) == 2
            p1_req = requests_created[0]
            p2_req = requests_created[1]
            trace.append("DM sent group Initiative Roll Request to both players.")

            # 5. Mobile Companion Players submit Physical Dice input (Manual entry: raw 16 -> total 18, raw 13 -> total 14)
            p1_roll = self.client.post(
                f"/api/v1/campaigns/{c_name}/roll-request/{p1_req['id']}/result",
                json={
                    "total": 18,
                    "expression": "1d20 + 2",
                    "raw": 16,
                    "modifier": 2,
                    "mode": "normal",
                },
                headers=p1_headers,
            )
            assert p1_roll.status_code == 200, f"P1 physical roll failed: {p1_roll.text}"

            p2_roll = self.client.post(
                f"/api/v1/campaigns/{c_name}/roll-request/{p2_req['id']}/result",
                json={
                    "total": 14,
                    "expression": "1d20 + 1",
                    "raw": 13,
                    "modifier": 1,
                    "mode": "normal",
                },
                headers=p2_headers,
            )
            assert p2_roll.status_code == 200, f"P2 physical roll failed: {p2_roll.text}"
            trace.append(
                "Mobile companion players successfully submitted physical dice rolls (P1=18, P2=14)."
            )

            # 6. Combat State: DM deals damage to Player 1 & applies Poisoned condition
            p1_sheet = self.client.get(f"/api/v1/characters/{p1_id}", headers=p1_headers).json()
            dm_patch = self.client.patch(
                f"/api/v1/campaigns/{c_name}/party/{p1_id}/state",
                json={"hp_current": 6, "conditions": ["Poisoned"]},
                headers=dm_headers,
            )
            assert dm_patch.status_code == 200
            patch_data = dm_patch.json()
            assert patch_data["hp_current"] == 6
            assert "Poisoned" in patch_data["conditions"]
            assert patch_data["version"] == p1_sheet["version"] + 1
            trace.append(
                "DM applied damage (HP -> 6) and 'Poisoned' condition to P1 with optimistic version increment."
            )

            # 7. DM distributes loot: 50 GP split evenly (25 each) + Wand of Magic Missiles strictly to P1
            loot_res = self.client.post(
                f"/api/v1/campaigns/{c_name}/loot/distribute",
                json={
                    "character_ids": [p1_id, p2_id],
                    "currency": {"gp": 50, "pp": 0, "ep": 0, "sp": 0, "cp": 0},
                    "split_currency": True,
                    "item_recipient_id": p1_id,
                    "items": [
                        {
                            "name": "Wand of Magic Missiles",
                            "type": "item",
                            "requires_attunement": False,
                        }
                    ],
                    "reason": "Boss goblin chest loot",
                },
                headers=dm_headers,
            )
            assert loot_res.status_code == 200, f"Loot distribution failed: {loot_res.text}"
            assert loot_res.json()["currency_awarded"]["gp"] == 25
            assert "Seraphina Vale" in loot_res.json()["recipients"]

            # Verify P1 got the wand and 25 GP (15 -> 40)
            p1_after = self.client.get(f"/api/v1/characters/{p1_id}", headers=p1_headers).json()
            assert p1_after["currency"]["gp"] == 40
            assert any(e["name"] == "Wand of Magic Missiles" for e in p1_after["equipment"])

            # Verify P2 got ONLY 25 GP (20 -> 45) and NO wand!
            p2_after = self.client.get(f"/api/v1/characters/{p2_id}", headers=p2_headers).json()
            assert p2_after["currency"]["gp"] == 45
            assert not any(e["name"] == "Wand of Magic Missiles" for e in p2_after["equipment"])
            trace.append("Targeted loot distributed: 25 GP each, Wand exclusively to P1.")

        except Exception as ex:
            import traceback

            errors.append(f"{type(ex).__name__}: {ex}\n{traceback.format_exc()}")

        duration = round(time.time() - start_time, 3)
        status = "PASSED" if not errors else "FAILED"
        return {
            "mode": "In-Person Tabletop",
            "status": status,
            "duration_s": duration,
            "trace": trace,
            "errors": errors,
        }

    def run_online_vtt_scenario(self) -> Dict[str, Any]:
        """
        Simulates an Online VTT game:
        - DM & Players on Desktop screens
        - Secret Roll by DM on player's behalf
        - Character Sheet and Inventory live state retrieval
        - Campaign presence and event log continuity
        """
        start_time = time.time()
        trace = []
        errors = []

        try:
            # 1. Setup DM & Online Player
            dm_headers = self._register_user("dm_online_vtt", "dm_vtt@forge.dnd")
            p1_headers = self._register_user("p1_elaria", "p1_vtt@forge.dnd")
            trace.append("Registered DM and Online Desktop Player.")

            # 2. DM creates Campaign
            c_name = "The Obsidian Citadel Online"
            c_res = self.client.post(
                "/api/v1/campaigns/",
                json={"campaign_name": c_name, "dnd_edition": "2024 Revision"},
                headers=dm_headers,
            )
            assert c_res.status_code == 200

            code_res = self.client.post(
                f"/api/v1/campaigns/{c_name}/invite-code", headers=dm_headers
            )
            invite_code = code_res.json()["invite_code"]

            # Create P1 Rogue
            p1_char = self.client.post(
                "/api/v1/characters",
                json={
                    "char_name": "Elaria Nightbreeze",
                    "char_class": "Rogue",
                    "subclass": "Thief",
                    "char_level": 3,
                    "classes": [{"class_name": "Rogue", "level": 3, "subclass": "Thief"}],
                    "race": "Elf",
                    "background": "Criminal",
                    "dnd_edition": "2024 Revision",
                    "stats": {
                        "STR": 10,
                        "DEX": 18,
                        "CON": 14,
                        "INT": 12,
                        "WIS": 14,
                        "CHA": 10,
                    },
                    "skills": {"Stealth": 8, "Perception": 4},
                },
                headers=p1_headers,
            ).json()
            p1_id = p1_char["char_id"]

            assert (
                self.client.post(
                    "/api/v1/campaigns/join",
                    json={"invite_code": invite_code, "character_id": p1_id},
                    headers=p1_headers,
                ).status_code
                == 200
            )
            trace.append("Online player joined campaign with Level 3 Thief.")

            # 3. DM performs Secret Stealth Roll on player's behalf (Ticket #26 / #153)
            secret_roll = self.client.post(
                f"/api/v1/campaigns/{c_name}/roll-request",
                json={
                    "char_filename": f"{p1_id}.json",
                    "char_name": p1_char["char_name"],
                    "roll_type": "skill_check",
                    "stat": "Stealth",
                    "reason": "Scouting ahead in dungeon shadows",
                    "is_secret": True,
                },
                headers=dm_headers,
            )
            assert secret_roll.status_code == 200, f"Secret roll failed: {secret_roll.text}"
            res_data = secret_roll.json()
            assert res_data.get("request", {}).get("is_secret") is True
            secret_result = res_data["request"]["result"]
            assert secret_result["total"] >= 1
            trace.append(f"DM executed Secret Stealth Roll (Total: {secret_result['total']}).")

            # 4. DM updates Party Notes / Reality Recap
            notes_res = self.client.post(
                f"/api/v1/campaigns/{c_name}/notes",
                json={
                    "notes": "The party infiltrated the Obsidian Gate without alerting the guards."
                },
                headers=dm_headers,
            )
            assert notes_res.status_code == 200
            trace.append("DM published live session recap notes to campaign timeline.")

            # 5. Player checks party and message stream (Simulating reconnect fetch)
            party_get = self.client.get(f"/api/v1/campaigns/{c_name}/party", headers=p1_headers)
            assert party_get.status_code == 200
            assert len(party_get.json()) >= 1

            msgs_get = self.client.get(f"/api/v1/campaigns/{c_name}/messages", headers=p1_headers)
            assert msgs_get.status_code == 200
            trace.append("Player reconnected and fetched active party & messages without desync.")

        except Exception as ex:
            import traceback

            errors.append(f"{type(ex).__name__}: {ex}\n{traceback.format_exc()}")

        duration = round(time.time() - start_time, 3)
        status = "PASSED" if not errors else "FAILED"
        return {
            "mode": "Online VTT",
            "status": status,
            "duration_s": duration,
            "trace": trace,
            "errors": errors,
        }

    def run_all(self, mode: str = "both") -> bool:
        """Executes selected modes and prints formatted report."""
        print("\n" + "=" * 70)
        print("⚔️  PHYREXIAN FORGE TABLETOP & ONLINE QA SIMULATION")
        print("=" * 70)

        self.setup()
        all_passed = True

        try:
            if mode in ("tabletop", "both"):
                print("\n🎲 Running Mode: In-Person Tabletop (Mobile Companion + Desktop DM)...")
                res_tt = self.run_tabletop_scenario()
                self._print_scenario_result(res_tt)
                if res_tt["status"] != "PASSED":
                    all_passed = False

            if mode in ("online", "both"):
                print("\n💻 Running Mode: Online VTT (Desktop Battlemap + Roll Sync)...")
                res_vtt = self.run_online_vtt_scenario()
                self._print_scenario_result(res_vtt)
                if res_vtt["status"] != "PASSED":
                    all_passed = False

        finally:
            self.teardown()

        print("\n" + "=" * 70)
        overall = "✅ ALL QA PLAYTEST SCENARIOS PASSED" if all_passed else "❌ QA PLAYTEST FAILED"
        print(f"OVERALL VERDICT: {overall}")
        print("=" * 70 + "\n")
        return all_passed

    def _print_scenario_result(self, res: Dict[str, Any]):
        color = "\033[92m" if res["status"] == "PASSED" else "\033[91m"
        reset = "\033[0m"
        print(f"Status: {color}{res['status']}{reset} ({res['duration_s']}s)")
        print("Interactions:")
        for t in res["trace"]:
            print(f"  • {t}")
        if res["errors"]:
            print("Errors:")
            for e in res["errors"]:
                print(f"  ❌ {e}")


def main():
    parser = argparse.ArgumentParser(description="Tabletop & Online QA Simulator")
    parser.add_argument(
        "--mode",
        choices=["tabletop", "online", "both"],
        default="both",
        help="Simulation mode to run",
    )
    args = parser.parse_args()

    simulator = TabletopQASimulator()
    success = simulator.run_all(mode=args.mode)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
