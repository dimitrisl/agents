import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.db_async import get_database


async def migrate():
    db = await get_database()

    print("Starting campaign_members migration...")

    campaigns_cursor = db["campaigns"].find({})
    campaigns = await campaigns_cursor.to_list(length=None)

    members_to_insert = []

    for camp in campaigns:
        campaign_id = camp["campaign_name"]
        owner_id = camp.get("owner_id")

        if owner_id:
            print(f"Adding owner {owner_id} as DM for {campaign_id}")
            members_to_insert.append(
                {
                    "campaign_id": campaign_id,
                    "user_id": owner_id,
                    "role": "dm",
                    "character_id": None,
                    "joined_at": datetime.now(timezone.utc),
                }
            )

        # Find characters in this campaign
        chars_cursor = db["characters"].find({"active_campaign": campaign_id})
        chars = await chars_cursor.to_list(length=None)

        for char in chars:
            if char.get("owner_id"):
                print(
                    f"Adding player {char['owner_id']} (char: {char['char_id']}) to {campaign_id}"
                )
                members_to_insert.append(
                    {
                        "campaign_id": campaign_id,
                        "user_id": char["owner_id"],
                        "role": "player",
                        "character_id": char["char_id"],
                        "joined_at": datetime.now(timezone.utc),
                    }
                )

    if members_to_insert:
        # Avoid duplicate inserts if run multiple times
        await db["campaign_members"].delete_many({})
        await db["campaign_members"].insert_many(members_to_insert)

        # Create unique index
        from pymongo import ASCENDING

        await db["campaign_members"].create_index(
            [("campaign_id", ASCENDING), ("user_id", ASCENDING)], unique=True
        )
        print(f"Migration completed. Inserted {len(members_to_insert)} members.")
    else:
        print("No members to migrate.")


if __name__ == "__main__":
    asyncio.run(migrate())
