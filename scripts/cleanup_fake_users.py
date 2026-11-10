#!/usr/bin/env python3
"""Cleanup Fake QA & Visual Playtest Users, Campaigns, and Characters from MongoDB."""

import asyncio
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


async def run_cleanup(dry_run: bool = True):
    db = await get_database()

    print("=" * 60)
    print(f"🧹 PHYREXIAN FORGE DB CLEANUP ({'DRY RUN' if dry_run else 'EXECUTING'})")
    print("=" * 60)

    # 1. Identify fake users
    fake_users = await db.users.find({"username": {"$nin": list(REAL_USERS)}}).to_list(1000)
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
    fake_campaigns = await db.campaigns.find(
        {
            "$or": [
                {
                    "campaign_name": {
                        "$regex": r"^(Visual QA Realm|Crypt of Gargoyle|UI Verifier|Test Live Realm)"
                    }
                },
                {"dm_id": {"$in": list(fake_user_ids) + list(fake_usernames)}},
                {"created_by": {"$in": list(fake_user_ids) + list(fake_usernames)}},
            ]
        }
    ).to_list(1000)
    fake_campaign_names = [c["campaign_name"] for c in fake_campaigns]
    print(f"\n2. Found {len(fake_campaigns)} fake test campaigns:")
    for c in fake_campaigns:
        print(f"   - {c.get('campaign_name')} (dm: {c.get('dm_id')})")

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

    if dry_run:
        print("\n" + "=" * 60)
        print("💡 Dry run complete. No records were deleted.")
        print("   Run with --apply to execute the deletion.")
        print("=" * 60)
        return

    # Execute deletion
    print("\n🗑️ Executing deletion...")
    if fake_users:
        res = await db.users.delete_many({"username": {"$nin": list(REAL_USERS)}})
        print(f"   ✓ Deleted {res.deleted_count} fake users.")

    if fake_campaign_names:
        res = await db.campaigns.delete_many({"campaign_name": {"$in": fake_campaign_names}})
        print(f"   ✓ Deleted {res.deleted_count} fake campaigns.")

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
        print(f"   ✓ Deleted {res.deleted_count} campaign memberships.")

    if fake_whispers:
        res = await db.campaign_whispers.delete_many(
            {"campaign_name": {"$in": fake_campaign_names}}
        )
        print(f"   ✓ Deleted {res.deleted_count} whispers.")

    if fake_rolls:
        res = await db.campaign_roll_requests.delete_many(
            {"campaign_name": {"$in": fake_campaign_names}}
        )
        print(f"   ✓ Deleted {res.deleted_count} roll requests.")

    if fake_scenes:
        res = await db.campaign_scenes.delete_many({"campaign_name": {"$in": fake_campaign_names}})
        print(f"   ✓ Deleted {res.deleted_count} scenes.")

    print("\n✅ Database cleanup finished successfully!")


if __name__ == "__main__":
    import sys

    dry = "--apply" not in sys.argv
    asyncio.run(run_cleanup(dry_run=dry))
