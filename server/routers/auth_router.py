import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from server.db_async import get_database
from server.dependencies.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class UserRegisterSchema(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None


class UserResponseSchema(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    name: Optional[str] = None
    has_completed_tutorial: bool = False


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str
    user: UserResponseSchema


class DemoLoginSchema(BaseModel):
    demo_type: str  # 'mitsos', 'google', 'discord', 'guest'


class TutorialUpdateSchema(BaseModel):
    has_completed_tutorial: bool


@router.post("/register", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegisterSchema, db: AsyncIOMotorDatabase = Depends(get_database)):
    username_clean = user_in.username.lower().strip()
    existing = await db["users"].find_one({"username": username_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered.",
        )

    user_id = f"local_user_{username_clean}"
    hashed_pwd = get_password_hash(user_in.password)

    user_doc = {
        "id": user_id,
        "username": username_clean,
        "password_hash": hashed_pwd,
        "email": user_in.email or f"{user_in.username}@phyrexian.forge",
        "name": user_in.name or user_in.username,
        "has_completed_tutorial": False,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    await db["users"].insert_one(user_doc)
    return UserResponseSchema(**user_doc)


@router.post("/login", response_model=TokenResponseSchema)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db["users"].find_one({"username": form_data.username.lower()})

    # Allow direct login if password matches legacy or passlib
    if not user or not verify_password(form_data.password, user.get("password_hash", "")):
        # Fallback for dev mode / demo accounts — only when DEBUG_MODE is enabled
        from server.config import settings as auth_settings

        if auth_settings.DEBUG_MODE and form_data.username.lower() in [
            "mitsos",
            "admin",
            "demo",
            "player",
        ]:
            user = {
                "id": f"local_user_{form_data.username.lower()}",
                "username": form_data.username,
                "name": form_data.username.title(),
                "email": f"{form_data.username}@phyrexian.forge",
                "has_completed_tutorial": True,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user_id = user.get("id") or f"local_user_{user['username']}"
    access_token = create_access_token(data={"sub": user_id, "username": user["username"]})
    user_res = UserResponseSchema(
        id=user_id,
        username=user["username"],
        email=user.get("email"),
        name=user.get("name") or user["username"],
        has_completed_tutorial=user.get("has_completed_tutorial", True),
    )
    return TokenResponseSchema(access_token=access_token, token_type="bearer", user=user_res)


@router.post("/demo", response_model=TokenResponseSchema)
async def demo_login(payload: DemoLoginSchema):
    dt = payload.demo_type.lower()
    if dt == "mitsos":
        user_id = "local_user_mitsos"
        name = "Mitsos (DM)"
        username = "mitsos"
    elif dt == "google":
        user_id = "mock_google_123"
        name = "Demo Google"
        username = "google_user"
    elif dt == "discord":
        user_id = "mock_discord_123"
        name = "Demo Discord"
        username = "discord_user"
    else:
        user_id = "local_user_adventurer"
        name = "Guest Adventurer"
        username = "adventurer"

    access_token = create_access_token(data={"sub": user_id, "username": username})
    user_res = UserResponseSchema(
        id=user_id,
        username=username,
        email=f"{username}@phyrexian.forge",
        name=name,
        has_completed_tutorial=True,
    )
    return TokenResponseSchema(access_token=access_token, token_type="bearer", user=user_res)


@router.get("/me", response_model=UserResponseSchema)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponseSchema(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user.get("email"),
        name=current_user.get("name"),
        has_completed_tutorial=current_user.get("has_completed_tutorial", False),
    )


@router.put("/tutorial", response_model=UserResponseSchema)
async def update_tutorial(
    payload: TutorialUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    await db["users"].update_one(
        {"id": current_user["id"]},
        {"$set": {"has_completed_tutorial": payload.has_completed_tutorial}},
    )
    current_user["has_completed_tutorial"] = payload.has_completed_tutorial
    return UserResponseSchema(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user.get("email"),
        name=current_user.get("name"),
        has_completed_tutorial=current_user["has_completed_tutorial"],
    )
