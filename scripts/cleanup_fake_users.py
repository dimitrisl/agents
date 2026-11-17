#!/usr/bin/env python3
"""Cleanup Fake QA & Visual Playtest Users, Campaigns, and Characters from MongoDB."""

import asyncio
import os
import re

from server.db_async import get_database

# Legitimate registered users that must NEVER be touched
REAL_USERS = {
    "mitsos",
    "akis",
    "kazand",
    "thanarthejester",
    "comedyx",
    "nikospapas",
    "fubvr",
    "stavros",
    "mike",
}


TEST_USERNAME_PATTERN = r"^(qa_|test_|e2e_|visual_qa|playtest)|(_test|_qa)$"
TEST_EMAIL_PATTERN = r"@(example\.com|test\.com|phyrexian\.test)$"


def _build_fake_user_query(include_unknown: bool = False) -> dict:
    """Build an explicit QA/test user query while never matching allowlisted real users."""
    guard = {"username": {"$nin": list(REAL_USERS)}}
    if include_unknown:
        return guard
    return {
        "$and": [
            guard,
            {
                "$or": [
                    {"username": {"$regex": TEST_USERNAME_PATTERN, "$options": "i"}},
                    {"email": {"$regex": TEST_EMAIL_PATTERN, "$options": "i"}},
                ]
            },
        ]
    }


async def run_cleanup(dry_run: bool = True, include_unknown: bool = False):
    db = await get_database()

    print("=" * 60)
    print(f"🧹 PHYREXIAN FORGE DB CLEANUP ({'DRY RUN' if dry_run else 'EXECUTING'})")
    print("=" * 60)

    # 1. Identify fake users
    fake_user_query = _build_fake_user_query(include_unknown=include_unknown)
    fake_users = await db.users.find(fake_user_query).to_list(1000)
    print(f"\n1. Found {len(fake_users)} fake test users:")
    fake_usernames = set()
    fake_user_ids = set()
    fake_owner_ids = set()

    for u in fake_users:
        uname = u.get("username")
        uid = str(u.get("_id"))
        local_id = u.get("id", f"local_user_{uname}")
        fake_usernames.add(uname)
        fake_user_ids.add(uid)
        fake_user_ids.add(local_id)
        fake_owner_ids.add(local_id)
        fake_owner_ids.add(f"local_user_{uname}")
        fake_owner_ids.add(uid)
        print(f"   - {uname} (email: {u.get('email')}, id: {local_id})")

    # 2. Identify test campaigns
    all_fake_actor_refs = list(fake_user_ids | fake_owner_ids | fake_usernames)
    fake_campaigns = await db.campaigns.find(
        {
            "$or": [
                {
                    "campaign_name": {
                        "$regex": r"^(Visual QA Realm|Crypt of Gargoyle|UI Verifier|Test Live Realm|Shadowfell Keep|Shattered Vault)"
                    }
                },
                {"owner_id": {"$in": all_fake_actor_refs}},
                {"dm_id": {"$in": all_fake_actor_refs}},
                {"created_by": {"$in": all_fake_actor_refs}},
            ]
        }
    ).to_list(1000)
    fake_campaign_names = [c["campaign_name"] for c in fake_campaigns]
    print(f"\n2. Found {len(fake_campaigns)} fake test campaigns:")
    for c in fake_campaigns:
        print(f"   - {c.get('campaign_name')} (owner: {c.get('owner_id') or c.get('dm_id')})")

    # 3. Identify test characters
    fake_chars = await db.characters.find(
        {
            "$or": [
                {"owner_id": {"$in": list(fake_owner_ids)}},
                {"active_campaign": {"$in": fake_campaign_names}},
            ]
        }
    ).to_list(1000)
    print(f"\n3. Found {len(fake_chars)} fake test characters:")
    for ch in fake_chars:
        print(
            f"   - {ch.get('char_name')} (owner: {ch.get('owner_id')}, campaign: {ch.get('active_campaign')})"
        )

    # 4. Associated records (campaign_members, whispers, roll requests, etc.)
    fake_members = await db.campaign_members.find(
        {
            "$or": [
                {"campaign_name": {"$in": fake_campaign_names}},
                {"campaign_id": {"$in": fake_campaign_names}},
                {"username": {"$in": list(fake_usernames)}},
                {"user_id": {"$in": list(fake_user_ids)}},
            ]
        }
    ).to_list(5000)
    print(f"\n4. Found {len(fake_members)} fake campaign memberships.")

    fake_whispers = await db.campaign_whispers.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"5. Found {len(fake_whispers)} fake campaign whispers.")

    fake_rolls = await db.campaign_roll_requests.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"6. Found {len(fake_rolls)} fake roll requests.")

    fake_scenes = await db.campaign_scenes.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"7. Found {len(fake_scenes)} fake scenes.")

    fake_roll_logs = await db.campaign_roll_logs.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"8. Found {len(fake_roll_logs)} fake roll logs.")

    fake_encounters = await db.campaign_encounters.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"9. Found {len(fake_encounters)} fake encounters.")

    fake_entities = await db.campaign_entities.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"10. Found {len(fake_entities)} fake campaign entities.")

    fake_session_logs = await db.session_logs.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"11. Found {len(fake_session_logs)} fake session logs.")

    fake_skeletons = await db.campaign_skeletons.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"12. Found {len(fake_skeletons)} fake campaign skeletons.")

    fake_homebrew = await db.homebrew_content.find(
        {
            "$or": [
                {"campaign_name": {"$in": fake_campaign_names}},
                {"campaign_id": {"$in": fake_campaign_names}},
            ]
        }
    ).to_list(5000)
    print(f"13. Found {len(fake_homebrew)} fake homebrew entries.")

    from backend.utils.path_safety import safe_path

    fake_assets = await db.campaign_assets.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    disk_asset_count = 0
    for asset in fake_assets:
        fname = asset.get("filename")
        if not isinstance(fname, str) or not fname.strip():
            continue
        try:
            candidate = safe_path(os.path.join("data", "uploads", fname), scope="uploads")
            if os.path.isfile(candidate):
                disk_asset_count += 1
        except (ValueError, OSError):
            pass
    print(
        f"14. Found {len(fake_assets)} fake campaign assets "
        f"({disk_asset_count} file(s) on disk under data/uploads/)."
    )

    fake_scene_history = await db.campaign_scene_history.find(
        {"campaign_name": {"$in": fake_campaign_names}}
    ).to_list(5000)
    print(f"15. Found {len(fake_scene_history)} fake scene history records.")

    if dry_run:
        print("\n" + "=" * 60)
        print("💡 Dry run complete. No records were deleted.")
        print("   Run with --apply to execute the deletion.")
        print("=" * 60)
        return

    # Execute deletion
    print("\n🗑️ Executing deletion...")
    if fake_users:
        res = await db.users.delete_many(fake_user_query)
        print(f"   ✓ Deleted {res.deleted_count} fake users.")

    if fake_campaign_names:
        from backend.services.campaign_service import delete_campaign_cascade

        for cname in fake_campaign_names:
            await delete_campaign_cascade(db, cname, broadcast=False)
        res_wh = await db.campaign_whispers.delete_many(
            {"campaign_name": {"$in": fake_campaign_names}}
        )
        print(
            f"   ✓ Cascade-deleted {len(fake_campaign_names)} fake campaigns "
            f"(+ purged {res_wh.deleted_count} test whispers)."
        )

    if fake_chars:
        char_ids = [c.get("char_id") for c in fake_chars if c.get("char_id")]
        obj_ids = [c["_id"] for c in fake_chars]
        pull_targets = set()
        for c in fake_chars:
            cid = c.get("char_id")
            if cid:
                pull_targets.add(cid)
                pull_targets.add(f"{cid}.json")
                cname_raw = (c.get("char_name") or "").strip().lower()
                if cname_raw:
                    slug = re.sub(r"\s+", "_", cname_raw)
                    pull_targets.add(f"{slug}_{cid}.json")
                    pull_targets.add(f"{cname_raw}_{cid}.json")
        if pull_targets:
            await db.campaigns.update_many({}, {"$pull": {"party": {"$in": list(pull_targets)}}})
        if char_ids:
            await db.campaign_members.delete_many(
                {"role": {"$ne": "dm"}, "character_id": {"$in": char_ids}}
            )
        res = await db.characters.delete_many(
            {"$or": [{"_id": {"$in": obj_ids}}, {"char_id": {"$in": char_ids}}]}
        )
        print(f"   ✓ Deleted {res.deleted_count} fake characters.")

    if fake_members:
        res = await db.campaign_members.delete_many(
            {
                "$or": [
                    {"campaign_name": {"$in": fake_campaign_names}},
                    {"campaign_id": {"$in": fake_campaign_names}},
                    {"username": {"$in": list(fake_usernames)}},
                    {"user_id": {"$in": list(fake_user_ids)}},
                ]
            }
        )
        print(f"   ✓ Deleted {res.deleted_count} remaining campaign memberships.")

    print("\n✅ Database cleanup finished successfully!")


if __name__ == "__main__":
    import sys

    dry = "--apply" not in sys.argv
    include_unknown_users = "--include-unknown-users" in sys.argv
    asyncio.run(run_cleanup(dry_run=dry, include_unknown=include_unknown_users))
