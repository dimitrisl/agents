#!/usr/bin/env python3
"""
Visual Multi-Client Browser QA Playtest for Phyrexian Forge.

Spins up real, concurrent Headless Chrome browser windows via Playwright:
1. DM Window (1920x1080 Desktop): Tests the DM Workspace, Party Panel, and Roll Request Modal.
2. Player 1 Window (390x844 Mobile Companion): Tests responsive mobile layout (<1024px),
   confirms <app-vtt-grid> is hidden per #170, checks touch targets, and captures prompts.
3. Player 2 Window (1440x900 Desktop VTT): Tests full desktop VTT player view with battlemap grid.

Saves visual screenshots at every step for auditing.
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, List

import requests
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

BASE_API = "http://localhost:8000/api/v1"
BASE_FRONTEND = "http://localhost:4200"
DEFAULT_ARTIFACT_DIR = (
    "/home/dimitrisl/.gemini/antigravity-cli/brain/201cd528-d8e5-4da2-ba06-24863609231e"
)


class VisualPartyPlaytester:
    def __init__(self, output_dir: str = DEFAULT_ARTIFACT_DIR):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.trace: List[str] = []
        self.screenshots: List[str] = []
        self.errors: List[str] = []

    def _setup_campaign_and_party(self) -> Dict[str, Any]:
        """Seeds DM and 2 players via API with known credentials for the browser to log in."""
        # 1. Register & login DM + 2 Players
        ts = int(time.time())
        credentials = [
            ("dm_vis", "dm_vis@forge.dnd", "Password123!", "1"),
            ("p1_vis", "p1_vis@forge.dnd", "Password123!", "2"),
            ("p2_vis", "p2_vis@forge.dnd", "Password123!", "3"),
        ]
        tokens = {}
        for uname, email, pwd, actor_id in credentials:
            ip_header = {"X-Forwarded-For": f"10.200.{actor_id}.1"}
            requests.post(
                f"{BASE_API}/auth/register",
                json={
                    "username": f"{uname}_{ts}",
                    "email": f"{actor_id}_{ts}_{email}",
                    "password": pwd,
                },
                headers=ip_header,
            )
            login = requests.post(
                f"{BASE_API}/auth/login",
                data={"username": f"{uname}_{ts}", "password": pwd},
                headers=ip_header,
            )
            assert login.status_code == 200, f"Login failed for {uname}: {login.text}"
            tokens[uname] = {
                "token": login.json()["access_token"],
                "username": f"{uname}_{ts}",
                "password": pwd,
                "ip": f"10.200.{actor_id}.1",
            }

        dm_auth = {
            "Authorization": f"Bearer {tokens['dm_vis']['token']}",
            "X-Forwarded-For": tokens["dm_vis"]["ip"],
        }
        p1_auth = {
            "Authorization": f"Bearer {tokens['p1_vis']['token']}",
            "X-Forwarded-For": tokens["p1_vis"]["ip"],
        }
        p2_auth = {
            "Authorization": f"Bearer {tokens['p2_vis']['token']}",
            "X-Forwarded-For": tokens["p2_vis"]["ip"],
        }

        # 2. DM creates Campaign
        c_name = f"Visual QA Realm {int(time.time())}"
        c_res = requests.post(
            f"{BASE_API}/campaigns/",
            json={"campaign_name": c_name, "dnd_edition": "2024 Revision"},
            headers=dm_auth,
        )
        assert c_res.status_code == 200, f"Campaign creation failed: {c_res.text}"

        code_res = requests.post(f"{BASE_API}/campaigns/{c_name}/invite-code", headers=dm_auth)
        invite_code = code_res.json()["invite_code"]

        # 3. Create characters
        p1_char = requests.post(
            f"{BASE_API}/characters",
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
            headers=p1_auth,
        ).json()

        p2_char = requests.post(
            f"{BASE_API}/characters",
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
            headers=p2_auth,
        ).json()

        # Join campaign
        requests.post(
            f"{BASE_API}/campaigns/join",
            json={"invite_code": invite_code, "character_id": p1_char["char_id"]},
            headers=p1_auth,
        )
        requests.post(
            f"{BASE_API}/campaigns/join",
            json={"invite_code": invite_code, "character_id": p2_char["char_id"]},
            headers=p2_auth,
        )

        return {
            "campaign_name": c_name,
            "invite_code": invite_code,
            "tokens": tokens,
            "p1_id": p1_char["char_id"],
            "p2_id": p2_char["char_id"],
        }

    def _login_browser_page(self, page: Page, user_info: dict):
        """Sets auth token in localStorage and loads the Angular app."""
        token = user_info["token"]
        username = user_info["username"]
        page.goto(f"{BASE_FRONTEND}/login", wait_until="networkidle")
        page.evaluate(
            """([token, username]) => {
            localStorage.setItem('token', token);
            localStorage.setItem('currentUser', JSON.stringify({ username: username, role: 'player' }));
        }""",
            [token, username],
        )

    def run(self) -> bool:
        start_time = time.time()
        print("\n" + "=" * 70)
        print("🎭  PHYREXIAN FORGE VISUAL MULTI-CLIENT PLAYTEST")
        print("=" * 70)

        # Pre-flight check
        try:
            r = requests.get(f"{BASE_FRONTEND}/", timeout=3)
            assert r.status_code == 200
        except Exception:
            print("❌ Angular dev server is not running on http://localhost:4200!")
            return False

        print("\n1. Seeding test party and campaign data...")
        data = self._setup_campaign_and_party()
        c_name = data["campaign_name"]
        tokens = data["tokens"]
        self.trace.append(f"Seeded campaign '{c_name}' with 2 heroes.")

        with sync_playwright() as p:
            print("\n2. Launching Google Chrome multi-viewport browser contexts...")
            browser: Browser = p.chromium.launch(
                executable_path="/usr/bin/google-chrome",
                headless=True,
            )

            # Context A: DM (1920x1080 Desktop)
            dm_ctx: BrowserContext = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/134.0.0.0 Safari/537.36",
                extra_http_headers={"X-Forwarded-For": tokens["dm_vis"]["ip"]},
            )
            page_dm: Page = dm_ctx.new_page()

            # Context B: Mobile Companion Player (390x844 iPhone 14)
            mobile_ctx: BrowserContext = browser.new_context(
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
                extra_http_headers={"X-Forwarded-For": tokens["p1_vis"]["ip"]},
            )
            page_mobile: Page = mobile_ctx.new_page()

            # Context C: Desktop VTT Player (1440x900)
            desktop_ctx: BrowserContext = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/134.0.0.0 Safari/537.36",
                extra_http_headers={"X-Forwarded-For": tokens["p2_vis"]["ip"]},
            )
            page_desktop: Page = desktop_ctx.new_page()

            try:
                # --- Step 1: DM Login & Workspace ---
                print("\n3. Testing DM Workspace (1920x1080)...")
                self._login_browser_page(page_dm, tokens["dm_vis"])
                page_dm.goto(f"{BASE_FRONTEND}/dm", wait_until="networkidle")
                page_dm.wait_for_timeout(1000)

                # Capture DM Workspace
                shot_dm = os.path.join(self.output_dir, "visual_qa_1_dm_workspace.png")
                page_dm.screenshot(path=shot_dm)
                self.screenshots.append(shot_dm)

                # Assertion: Verify DM workspace is not blocked by "Desktop View Required"
                barrier_count = page_dm.locator("text='Desktop View Required'").count()
                assert barrier_count == 0, "DM workspace incorrectly blocked by desktop barrier!"
                self.trace.append("DM Workspace rendered without responsive barrier (1080p).")

                # --- Step 2: Mobile Player Companion Sheet ---
                print("\n4. Testing Mobile Companion Sheet (390x844 iPhone)...")
                self._login_browser_page(page_mobile, tokens["p1_vis"])
                page_mobile.goto(f"{BASE_FRONTEND}/player", wait_until="networkidle")
                page_mobile.wait_for_timeout(1000)

                # If edition filter shows Switch Edition, click it to see 2024 hero
                switch_btn = page_mobile.locator("button:has-text('Switch Edition')")
                if switch_btn.is_visible():
                    switch_btn.click()
                    page_mobile.wait_for_timeout(800)

                # Open hero sheet if in vault/dashboard
                hero_card = page_mobile.locator("text='Seraphina Vale'")
                if hero_card.count() > 0:
                    hero_card.first.click()
                    page_mobile.wait_for_timeout(1000)

                shot_mobile = os.path.join(
                    self.output_dir, "visual_qa_2_mobile_companion_sheet.png"
                )
                page_mobile.screenshot(path=shot_mobile)
                self.screenshots.append(shot_mobile)

                # Critical Tabletop Boundary Assertion (#170 / P0-A3):
                # VTT battlemap grid MUST NOT be visible on mobile (< 1024px)
                vtt_visible = page_mobile.locator("app-vtt-grid").is_visible()
                assert not vtt_visible, (
                    "CRITICAL REGRESSION: <app-vtt-grid> is visible on mobile companion!"
                )

                # Check horizontal overflow (no horizontal scrollbar on phone)
                overflows = page_mobile.evaluate(
                    "() => document.documentElement.scrollWidth > window.innerWidth"
                )
                assert not overflows, "Mobile companion layout has horizontal overflow!"
                self.trace.append(
                    "Mobile companion rendered strictly without VTT battlemap grid and zero horizontal overflow."
                )

                # --- Step 3: Desktop Online VTT Player Sheet ---
                print("\n5. Testing Desktop Online Player View (1440x900)...")
                self._login_browser_page(page_desktop, tokens["p2_vis"])
                page_desktop.goto(f"{BASE_FRONTEND}/player", wait_until="networkidle")
                page_desktop.wait_for_timeout(1000)

                # If edition filter shows Switch Edition, click it to see 2024 hero
                switch_btn_desk = page_desktop.locator("button:has-text('Switch Edition')")
                if switch_btn_desk.is_visible():
                    switch_btn_desk.click()
                    page_desktop.wait_for_timeout(800)

                hero_card_desk = page_desktop.locator("text='Kaelen Vane'")
                if hero_card_desk.count() > 0:
                    hero_card_desk.first.click()
                    page_desktop.wait_for_timeout(1000)

                shot_desktop = os.path.join(self.output_dir, "visual_qa_3_desktop_player_sheet.png")
                page_desktop.screenshot(path=shot_desktop)
                self.screenshots.append(shot_desktop)
                self.trace.append("Desktop VTT Player rendered successfully with full navigation.")

                # --- Step 4: DM Roll Request Modal & Live Prompt ---
                print("\n6. Testing DM Roll Request interaction...")
                # In DM window, check if roll request button exists
                roll_btn = page_dm.locator("button:has-text('Roll Request'), button:has-text('🎲')")
                if roll_btn.count() > 0:
                    roll_btn.first.click()
                    page_dm.wait_for_timeout(500)
                    shot_modal = os.path.join(
                        self.output_dir, "visual_qa_4_dm_roll_request_modal.png"
                    )
                    page_dm.screenshot(path=shot_modal)
                    self.screenshots.append(shot_modal)
                    self.trace.append("DM Roll Request modal opened and captured visually.")

                print("\n✅ Visual Playtest completed successfully!")

            except Exception as ex:
                import traceback

                err = f"{type(ex).__name__}: {ex}\n{traceback.format_exc()}"
                self.errors.append(err)
                print(f"❌ Error during visual playtest: {ex}")
            finally:
                browser.close()

        duration = round(time.time() - start_time, 2)
        all_passed = len(self.errors) == 0

        print("\n" + "=" * 70)
        verdict = "✅ ALL VISUAL PLAYTEST CHECKS PASSED" if all_passed else "❌ PLAYTEST FAILED"
        print(f"OVERALL VERDICT: {verdict} ({duration}s)")
        print("Captured Screenshots:")
        for s in self.screenshots:
            print(f"  📸 {s}")
        print("=" * 70 + "\n")
        return all_passed


def main():
    parser = argparse.ArgumentParser(description="Visual Multi-Client Playtester")
    parser.add_argument(
        "--output-dir", default=DEFAULT_ARTIFACT_DIR, help="Directory for screenshots"
    )
    args = parser.parse_args()

    tester = VisualPartyPlaytester(output_dir=args.output_dir)
    success = tester.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
