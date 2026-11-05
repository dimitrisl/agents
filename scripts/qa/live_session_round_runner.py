#!/usr/bin/env python3
"""Live Multi-Client Session Round Runner for Agentic Visual QA.

Simulates a 5-beat live D&D encounter across 3 Google Chrome browser viewports:
1. DM Workspace (1920x1080)
2. Mobile Companion Player (390x844 - iPhone 14)
3. Desktop VTT Player (1440x900)

Captures high-resolution visual screenshots at every beat directly into the artifact directory.
"""

import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(
    "/home/dimitrisl/.gemini/antigravity-cli/brain/201cd528-d8e5-4da2-ba06-24863609231e"
)
BASE_URL = "http://localhost:4200"
API_URL = "http://localhost:8000/api/v1"
CHROME_BIN = "/usr/bin/google-chrome"


def setup_campaign_and_users():
    ts = int(time.time())
    users_info = [
        ("dm_live", "dm_live@forge.dnd", "Password123!", "1", "dm"),
        ("elena_live", "elena@forge.dnd", "Password123!", "2", "player"),
        ("kostas_live", "kostas@forge.dnd", "Password123!", "3", "player"),
    ]
    tokens = {}

    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        for uname, email, pwd, actor_id, role in users_info:
            full_user = f"{uname}_{ts}"
            ip_header = {"X-Forwarded-For": f"10.201.{actor_id}.1"}
            # Register
            client.post(
                "/auth/register",
                headers=ip_header,
                json={"username": full_user, "email": f"{actor_id}_{ts}_{email}", "password": pwd},
            )
            # Login
            r_login = client.post(
                "/auth/login",
                headers=ip_header,
                data={"username": full_user, "password": pwd},
            )
            assert r_login.status_code == 200, f"Login failed for {full_user}: {r_login.text}"
            tokens[uname] = {
                "username": full_user,
                "token": r_login.json()["access_token"],
                "ip": f"10.201.{actor_id}.1",
            }

        dm_auth = {
            "Authorization": f"Bearer {tokens['dm_live']['token']}",
            "X-Forwarded-For": tokens["dm_live"]["ip"],
        }
        p1_auth = {
            "Authorization": f"Bearer {tokens['elena_live']['token']}",
            "X-Forwarded-For": tokens["elena_live"]["ip"],
        }
        p2_auth = {
            "Authorization": f"Bearer {tokens['kostas_live']['token']}",
            "X-Forwarded-For": tokens["kostas_live"]["ip"],
        }

        c_name = f"Crypt of Gargoyle {ts}"

        # Create Campaign
        r_camp = client.post(
            "/campaigns/",
            headers=dm_auth,
            json={"campaign_name": c_name, "dnd_edition": "2024 Revision"},
        )
        assert r_camp.status_code == 200, f"Campaign create failed: {r_camp.text}"

        code_res = client.post(f"/campaigns/{c_name}/invite-code", headers=dm_auth)
        assert code_res.status_code == 200, f"Invite code failed: {code_res.text}"
        invite_code = code_res.json()["invite_code"]

        # Create Hero 1: Seraphina Vale (2024 Sorcerer)
        p1_char = client.post(
            "/characters",
            headers=p1_auth,
            json={
                "char_name": "Seraphina Vale",
                "char_class": "Sorcerer",
                "char_level": 2,
                "classes": [{"class_name": "Sorcerer", "level": 2}],
                "race": "Tiefling",
                "background": "Sage",
                "dnd_edition": "2024 Revision",
                "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 17},
                "currency": {"gp": 25, "sp": 0, "cp": 0},
                "weapons": [{"name": "Quarterstaff", "damage_dice": "1d6"}],
            },
        ).json()

        # Join campaign P1
        client.post(
            "/campaigns/join",
            headers=p1_auth,
            json={"invite_code": invite_code, "character_id": p1_char["char_id"]},
        )

        # Create Hero 2: Kaelen Vane (2024 Paladin)
        p2_char = client.post(
            "/characters",
            headers=p2_auth,
            json={
                "char_name": "Kaelen Vane",
                "char_class": "Paladin",
                "char_level": 2,
                "classes": [{"class_name": "Paladin", "level": 2}],
                "race": "Human",
                "background": "Soldier",
                "dnd_edition": "2024 Revision",
                "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 16},
                "currency": {"gp": 30, "sp": 0, "cp": 0},
                "weapons": [{"name": "Longsword", "damage_dice": "1d8"}],
            },
        ).json()

        # Join campaign P2
        client.post(
            "/campaigns/join",
            headers=p2_auth,
            json={"invite_code": invite_code, "character_id": p2_char["char_id"]},
        )

    return {
        "dm": tokens["dm_live"],
        "p1": tokens["elena_live"],
        "p2": tokens["kostas_live"],
        "campaign": c_name,
    }


def init_browser_session(context, token, username, target_path="/"):
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    page.evaluate(
        f"""() => {{
        localStorage.setItem('token', '{token}');
        localStorage.setItem('auth_token', '{token}');
        localStorage.setItem('currentUser', JSON.stringify({{ username: '{username}', role: 'player' }}));
    }}"""
    )
    page.goto(f"{BASE_URL}{target_path}")
    page.wait_for_load_state("networkidle")
    time.sleep(1.5)
    return page


def run_session_encounter():
    print("=== [1/5] Setting up live session data in MongoDB... ===")
    setup_data = setup_campaign_and_users()
    print(f"✓ Campaign: '{setup_data['campaign']}' ready with DM and 2 players.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_BIN,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        # 1. DM Context (1920x1080)
        dm_context = browser.new_context(viewport={"width": 1920, "height": 1080})
        # 2. Mobile Companion Context (390x844 iPhone 14)
        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        )
        # 3. Desktop VTT Context (1440x900)
        desktop_context = browser.new_context(viewport={"width": 1440, "height": 900})

        print("=== [2/5] Initializing live pages for DM, Mobile, and Desktop... ===")
        dm_page = init_browser_session(
            dm_context, setup_data["dm"]["token"], setup_data["dm"]["username"], "/dm"
        )
        mobile_page = init_browser_session(
            mobile_context, setup_data["p1"]["token"], setup_data["p1"]["username"], "/player"
        )
        desktop_page = init_browser_session(
            desktop_context, setup_data["p2"]["token"], setup_data["p2"]["username"], "/player"
        )

        # Switch Edition on players if needed to show 2024 heroes
        for pg, name in [(mobile_page, "Elena Mobile"), (desktop_page, "Kostas Desktop")]:
            switch_btn = pg.locator("button:has-text('Switch Edition')")
            if switch_btn.is_visible():
                print(f"[{name}] Clicking 'Switch Edition' to 2024...")
                switch_btn.click()
                pg.wait_for_load_state("networkidle")
                time.sleep(1.0)

        # BEAT 1: DM Workspace & Roll Request
        print("=== [BEAT 1] DM Workspace & Roll Request ===")
        dm_page.wait_for_selector("text=Active Party Roster", timeout=10000)
        snap_dm1 = ARTIFACT_DIR / "session_beat1_dm_roster.png"
        dm_page.screenshot(path=str(snap_dm1), full_page=False)
        print(f"📸 Saved: {snap_dm1.name}")

        # DM clicks 'Request Roll' for Seraphina
        req_buttons = dm_page.locator("button:has-text('Request Roll')")
        if req_buttons.count() > 0:
            req_buttons.first.click()
            time.sleep(1.0)
            snap_dm_modal = ARTIFACT_DIR / "session_beat1_dm_roll_modal.png"
            dm_page.screenshot(path=str(snap_dm_modal), full_page=False)
            print(f"📸 Saved: {snap_dm_modal.name}")

            close_btn = dm_page.locator("button:has-text('Cancel')")
            if close_btn.is_visible():
                close_btn.click()
                time.sleep(0.5)

        # BEAT 2: Mobile Companion - Elena (Seraphina Vale on iPhone 14)
        print("=== [BEAT 2] Mobile Companion Navigation (Elena) ===")
        mobile_page.wait_for_selector("text=Seraphina Vale", timeout=10000)
        snap_mob_hero = ARTIFACT_DIR / "session_beat2a_mobile_hero_overview.png"
        mobile_page.screenshot(path=str(snap_mob_hero), full_page=False)
        print(f"📸 Saved: {snap_mob_hero.name}")

        # Elena taps 'SKILLS' on bottom nav
        skills_btn = mobile_page.locator("nav button:has-text('Skills')")
        if skills_btn.is_visible():
            print("Elena taps 'Skills' on bottom nav...")
            skills_btn.click()
            time.sleep(1.0)
            snap_mob_skills = ARTIFACT_DIR / "session_beat2b_mobile_skills_tab.png"
            mobile_page.screenshot(path=str(snap_mob_skills), full_page=False)
            print(f"📸 Saved: {snap_mob_skills.name}")

        # Elena taps 'SPELLS' on bottom nav
        spells_btn = mobile_page.locator("nav button:has-text('Spells')")
        if spells_btn.is_visible():
            print("Elena taps 'Spells' on bottom nav...")
            spells_btn.click()
            time.sleep(1.0)
            snap_mob_spells = ARTIFACT_DIR / "session_beat2c_mobile_spells_tab.png"
            mobile_page.screenshot(path=str(snap_mob_spells), full_page=False)
            print(f"📸 Saved: {snap_mob_spells.name}")

        # Elena taps 'TABLE' on bottom nav
        table_btn = mobile_page.locator("nav button:has-text('Table')")
        if table_btn.is_visible():
            print("Elena taps 'Table' on bottom nav...")
            table_btn.click()
            time.sleep(1.0)
            snap_mob_table = ARTIFACT_DIR / "session_beat2d_mobile_table_tab.png"
            mobile_page.screenshot(path=str(snap_mob_table), full_page=False)
            print(f"📸 Saved: {snap_mob_table.name}")

        # BEAT 3: Desktop VTT Player - Kostas (Kaelen Vane on Desktop)
        print("=== [BEAT 3] Desktop Player Experience (Kostas) ===")
        desktop_page.wait_for_selector("text=Kaelen Vane", timeout=10000)

        # Kostas clicks Skills & Checks
        skills_desk_btn = desktop_page.locator("button:has-text('Skills & Checks')")
        if skills_desk_btn.is_visible():
            skills_desk_btn.click()
            time.sleep(1.0)
        snap_desk_skills = ARTIFACT_DIR / "session_beat3a_desktop_skills.png"
        desktop_page.screenshot(path=str(snap_desk_skills), full_page=False)
        print(f"📸 Saved: {snap_desk_skills.name}")

        # Kostas switches to Combat & Inventory
        combat_tab = desktop_page.locator("button:has-text('Combat & Inventory')")
        if combat_tab.is_visible():
            print("Kostas clicks 'Combat & Inventory'...")
            combat_tab.click()
            time.sleep(1.0)
            snap_desk_combat = ARTIFACT_DIR / "session_beat3b_desktop_combat_inventory.png"
            desktop_page.screenshot(path=str(snap_desk_combat), full_page=False)
            print(f"📸 Saved: {snap_desk_combat.name}")

        # BEAT 4: DM Workspace Initiative & Damage Sync
        print("=== [BEAT 4] DM Initiative & Combat Damage ===")
        # DM switches to Initiative Tracker tab
        init_tab = dm_page.locator("button:has-text('Initiative Tracker')")
        if init_tab.is_visible():
            print("DM clicks 'Initiative Tracker' tab...")
            init_tab.click()
            time.sleep(1.0)
            snap_dm_init = ARTIFACT_DIR / "session_beat4a_dm_initiative_tracker.png"
            dm_page.screenshot(path=str(snap_dm_init), full_page=False)
            print(f"📸 Saved: {snap_dm_init.name}")

        # DM switches back to Live Party Tracker and applies damage to Kaelen
        party_tab = dm_page.locator("button:has-text('Live Party Tracker')")
        if party_tab.is_visible():
            party_tab.click()
            time.sleep(0.8)

        # DM opens Distribute Loot modal
        loot_btn = dm_page.locator("button:has-text('Distribute Loot')")
        if loot_btn.is_visible():
            print("DM opens 'Distribute Loot' modal...")
            loot_btn.click()
            time.sleep(1.0)
            snap_dm_loot = ARTIFACT_DIR / "session_beat4b_dm_distribute_loot_modal.png"
            dm_page.screenshot(path=str(snap_dm_loot), full_page=False)
            print(f"📸 Saved: {snap_dm_loot.name}")

            # Close modal
            cancel_loot = dm_page.locator("button:has-text('Cancel')")
            if cancel_loot.is_visible():
                cancel_loot.click()
                time.sleep(0.5)

        print("=== [5/5] Live Session Playtest Finished! ===")
        browser.close()


if __name__ == "__main__":
    run_session_encounter()
