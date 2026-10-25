#!/usr/bin/env python3
"""CLI utility and async helper to promote or revoke admin role on users."""

import argparse
import asyncio
import sys
from typing import Any

from server.db_async import close_mongo_connection, connect_to_mongo, get_database


async def promote_user(db: Any, username: str, is_admin: bool = True) -> bool:
    """Promote or demote a user to/from admin. Returns True if user was found and updated."""
    username_clean = username.lower().strip()
    result = await db["users"].update_one(
        {"username": username_clean},
        {"$set": {"is_admin": is_admin}},
    )
    return result.matched_count > 0


async def main_async(username: str, is_admin: bool) -> int:
    await connect_to_mongo()
    db = await get_database()
    try:
        success = await promote_user(db, username, is_admin=is_admin)
        if success:
            action = "Promoted" if is_admin else "Revoked admin from"
            print(f"Successfully {action} user '{username.lower()}'.")
            return 0
        else:
            print(f"Error: User '{username.lower()}' not found in database.", file=sys.stderr)
            return 1
    finally:
        await close_mongo_connection()


def main():
    parser = argparse.ArgumentParser(description="Promote or revoke admin privileges for a user.")
    parser.add_argument("username", help="Username of the user")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Revoke admin privileges instead of granting them",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(main_async(args.username, is_admin=not args.revoke)))


if __name__ == "__main__":
    main()
