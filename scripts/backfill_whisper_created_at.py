#!/usr/bin/env python3
"""CLI utility and async helper to backfill BSON datetime created_at on legacy whisper documents."""

import asyncio
import datetime
import logging
import sys
from typing import Any

from server.db_async import close_mongo_connection, connect_to_mongo, get_database

logger = logging.getLogger("PhyrexianForge.BackfillWhispers")


async def backfill_whispers(db: Any) -> int:
    """Finds whispers with missing created_at, parses timestamp, and sets created_at/archived_at/has_open_report."""
    cursor = db["campaign_whispers"].find(
        {"$or": [{"created_at": None}, {"created_at": {"$exists": False}}]}
    )
    count = 0
    if hasattr(cursor, "__aiter__"):
        async for doc in cursor:
            ts_str = doc.get("timestamp")
            dt = None
            if ts_str:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        dt = datetime.datetime.strptime(ts_str.split(".")[0], fmt).replace(
                            tzinfo=datetime.timezone.utc
                        )
                        break
                    except ValueError:
                        pass
            if dt is None:
                dt = datetime.datetime.now(datetime.timezone.utc)

            await db["campaign_whispers"].update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "created_at": dt,
                        "archived_at": doc.get("archived_at", None),
                        "has_open_report": doc.get("has_open_report", False),
                    }
                },
            )
            count += 1
    return count


async def main_async() -> int:
    await connect_to_mongo()
    db = await get_database()
    try:
        updated = await backfill_whispers(db)
        print(f"Successfully backfilled {updated} whisper document(s).")
        return 0
    finally:
        await close_mongo_connection()


def main():
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
