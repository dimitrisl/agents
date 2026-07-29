import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional

from server.db_async import get_database
from server.dependencies.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
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


class TutorialUpdateSchema(BaseModel):
    has_completed_tutorial: bool


@router.post(
    "/register", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED
)
async def register(user_in: UserRegisterSchema):
    db = get_database()
    existing = await db["users"].find_one({"username": user_in.username})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered.",
        )

    user_id = f"local_user_{uuid.uuid4().hex[:8]}"
    hashed_pwd = get_password_hash(user_in.password)

    user_doc = {
        "id": user_id,
        "username": user_in.username,
        "password_hash": hashed_pwd,
        "email": user_in.email,
        "name": user_in.name or user_in.username,
        "has_completed_tutorial": False,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    await db["users"].insert_one(user_doc)
    return UserResponseSchema(**user_doc)


@router.post("/login", response_model=TokenResponseSchema)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = get_database()
    user = await db["users"].find_one({"username": form_data.username})
    if not user or not verify_password(
        form_data.password, user.get("password_hash", "")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user["id"], "username": user["username"]}
    )
    user_res = UserResponseSchema(
        id=user["id"],
        username=user["username"],
        email=user.get("email"),
        name=user.get("name"),
        has_completed_tutorial=user.get("has_completed_tutorial", False),
    )
    return TokenResponseSchema(
        access_token=access_token, token_type="bearer", user=user_res
    )


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
    payload: TutorialUpdateSchema, current_user: dict = Depends(get_current_user)
):
    db = get_database()
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
