import datetime
import hashlib
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
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
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
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

    # Allow mock / demo users without database lookup
    if user_id.startswith("local_user_") or user_id.startswith("mock_"):
        return {
            "id": user_id,
            "username": username or "Adventurer",
            "name": username or "Adventurer",
            "email": f"{username}@phyrexian.forge",
            "has_completed_tutorial": True,
        }

    db = get_database()
    user = await db["users"].find_one({"id": user_id})
    if user is None:
        user = await db["users"].find_one({"username": username})
    if user is None:
        # Fallback return minimal dict
        return {
            "id": user_id,
            "username": username or "Adventurer",
            "name": username or "Adventurer",
            "email": f"{username}@phyrexian.forge",
            "has_completed_tutorial": True,
        }

    user.pop("password_hash", None)
    return user
