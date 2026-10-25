import datetime
import hashlib
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext
from pydantic import BaseModel

from server.config import settings
from server.db_async import get_database

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


class TokenData(BaseModel):
    user_id: str
    username: str


def legacy_sha256_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    # Check legacy sha256 hash first
    if hashed_password == legacy_sha256_hash(plain_password):
        return True
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now.timestamp()})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user_from_token(
    token: str, db: Optional[AsyncIOMotorDatabase] = None
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    if db is None:
        db = await get_database()

    user = await db["users"].find_one({"id": user_id})
    if user is None:
        user = await db["users"].find_one({"username": username})
    if user is None:
        raise credentials_exception

    # Reject tokens issued before user's created_at (prevents deleted user's JWT from authenticating re-registered username)
    token_iat = payload.get("iat")
    user_created_raw = user.get("created_at")
    if token_iat is not None and user_created_raw:
        try:
            if isinstance(user_created_raw, str):
                created_dt = datetime.datetime.fromisoformat(
                    user_created_raw.replace("Z", "+00:00")
                )
            elif isinstance(user_created_raw, datetime.datetime):
                created_dt = user_created_raw
            else:
                created_dt = None
            if created_dt is not None:
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=datetime.timezone.utc)
                if float(token_iat) + 1.0 < created_dt.timestamp():
                    raise credentials_exception
        except HTTPException:
            raise
        except Exception:
            pass

    user.pop("password_hash", None)
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncIOMotorDatabase = Depends(get_database)
) -> dict:
    return await get_current_user_from_token(token, db)


async def require_admin(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    """Verify admin status directly from the database (never from JWT claims)."""
    user_doc = await db["users"].find_one({"id": current_user["id"]})
    if not user_doc or not bool(user_doc.get("is_admin", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    user_doc.pop("password_hash", None)
    return user_doc
