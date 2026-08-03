from typing import Callable

from fastapi import Depends, HTTPException, Path, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from server.db_async import get_database
from server.dependencies.auth import get_current_user


def require_campaign_role(*allowed_roles: str) -> Callable:
    """
    Dependency generator that checks if the current user is a member of the campaign
    and optionally if they have a specific role (e.g. "dm", "player").
    Returns the campaign member document from the database.
    """

    async def role_checker(
        name: str = Path(..., description="The name of the campaign"),
        current_user: dict = Depends(get_current_user),
        db: AsyncIOMotorDatabase = Depends(get_database),
    ) -> dict:
        member = await db["campaign_members"].find_one(
            {"campaign_id": name, "user_id": current_user["id"]}
        )
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this campaign.",
            )

        if allowed_roles and member.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{member.get('role')}' is not authorized. Required: {', '.join(allowed_roles)}",
            )

        return member

    return role_checker


def require_campaign_member() -> Callable:
    """Convenience dependency for when any member role (DM or Player) is acceptable."""
    return require_campaign_role("dm", "player")
