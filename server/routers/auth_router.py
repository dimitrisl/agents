import datetime
import hmac
import logging
import re
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError
from slowapi.util import get_remote_address

from backend.services.campaign_service import _maybe_await
from server.config import settings
from server.db_async import get_database
from server.dependencies.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    legacy_sha256_hash,
    verify_password,
)
from server.rate_limiter import get_auth_key, is_trusted_proxy, limiter
from server.routers.websocket_router import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

_DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
_DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
_DISCORD_USER_URL = "https://discord.com/api/users/@me"
_OAUTH_NONCE_COOKIE = "pf_discord_oauth_nonce"
_USED_OAUTH_HANDOFF_JTIS: dict[str, float] = {}


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
    is_admin: bool = False
    role: Optional[str] = "player"
    must_change_password: bool = False
    has_password: bool = True
    is_demo: bool = False
    auth_providers: list[str] = Field(default_factory=list)


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str
    user: UserResponseSchema


class DemoLoginSchema(BaseModel):
    demo_type: str  # 'mitsos', 'google', 'discord', 'guest'


class TutorialUpdateSchema(BaseModel):
    has_completed_tutorial: bool


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthProvidersSchema(BaseModel):
    local: bool = True
    discord: bool = False


class DiscordExchangeSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048)


def _is_demo_account(user: dict) -> bool:
    return bool(user.get("is_demo", False)) or user.get("password_hash") == "demo"


def _build_user_response(user: dict) -> UserResponseSchema:
    user_id = user.get("id") or f"local_user_{user['username']}"
    is_demo = _is_demo_account(user)
    if "has_password" in user:
        has_password = bool(user["has_password"])
    else:
        has_password = False if is_demo else bool(user.get("password_hash"))

    if "auth_providers" in user:
        providers = list(user["auth_providers"])
    else:
        providers = []
        if has_password:
            providers.append("local")
        if user.get("discord_id"):
            providers.append("discord")

    return UserResponseSchema(
        id=user_id,
        username=user["username"],
        email=user.get("email"),
        name=user.get("name") or user["username"],
        has_completed_tutorial=user.get("has_completed_tutorial", False),
        is_admin=bool(user.get("is_admin", False)),
        role=user.get("role", "player"),
        must_change_password=bool(user.get("must_change_password", False)),
        has_password=has_password,
        is_demo=is_demo,
        auth_providers=providers,
    )


def _issue_token_for_user(user: dict) -> TokenResponseSchema:
    user_id = user.get("id") or f"local_user_{user['username']}"
    token_version = int(user.get("token_version") or 0)
    access_token = create_access_token(
        data={"sub": user_id, "username": user["username"], "tv": token_version}
    )
    return TokenResponseSchema(
        access_token=access_token,
        token_type="bearer",
        user=_build_user_response(user),
    )


def _verify_discord_configured() -> None:
    if not settings.discord_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord login is not configured on this server.",
        )


def _resolve_frontend_base_url() -> str:
    configured = (settings.FRONTEND_URL or "").strip()
    if configured:
        return configured.rstrip("/")
    if settings.cors_origin_list:
        return settings.cors_origin_list[0].rstrip("/")
    return "http://localhost:4200"


def _resolve_discord_redirect_uri(request: Request) -> str:
    configured = (settings.DISCORD_REDIRECT_URI or "").strip()
    if configured:
        return configured
    return str(request.url_for("discord_callback"))


async def _exchange_discord_code_and_fetch_profile(
    code: str,
    redirect_uri: str,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> dict:
    client_kwargs = {"transport": transport} if transport is not None else {}
    async with AsyncOAuth2Client(
        client_id=settings.DISCORD_CLIENT_ID.strip(),
        client_secret=settings.DISCORD_CLIENT_SECRET.strip(),
        redirect_uri=redirect_uri,
        timeout=10.0,
        **client_kwargs,
    ) as client:
        await client.fetch_token(_DISCORD_TOKEN_URL, code=code)
        resp = await client.get(_DISCORD_USER_URL)
        resp.raise_for_status()
        return resp.json()


def _is_https_request(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    remote_ip = get_remote_address(request)
    if is_trusted_proxy(remote_ip):
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        return forwarded_proto == "https"
    return False


async def _consume_oauth_handoff_jti(db: AsyncIOMotorDatabase, jti: str, exp_ts: float) -> bool:
    now = time.time()
    stale = [k for k, exp in _USED_OAUTH_HANDOFF_JTIS.items() if exp <= now]
    for k in stale:
        _USED_OAUTH_HANDOFF_JTIS.pop(k, None)
    if not jti or jti in _USED_OAUTH_HANDOFF_JTIS:
        return False
    _USED_OAUTH_HANDOFF_JTIS[jti] = exp_ts

    # Persist consumed JTI in MongoDB as well so multi-worker deployments reject replays (fail closed)
    try:
        expires_at = datetime.datetime.fromtimestamp(exp_ts, tz=datetime.timezone.utc)
        await _maybe_await(db["oauth_handoffs"].insert_one({"jti": jti, "expires_at": expires_at}))
    except DuplicateKeyError:
        return False
    except Exception as exc:
        _USED_OAUTH_HANDOFF_JTIS.pop(jti, None)
        logger.warning("Failed persisting oauth_handoffs JTI cleanly: %s", exc)
        return False
    return True


def _sanitize_discord_username(raw_name: str, discord_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]", "_", (raw_name or "").lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)[:24]
    if not cleaned:
        cleaned = f"discord_{discord_id[-6:]}"
    return cleaned


@router.post("/register", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.AUTH_REGISTER_RATE_LIMIT, key_func=get_auth_key)
async def register(
    request: Request,
    user_in: UserRegisterSchema,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
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
        "is_admin": False,
        "role": "player",  # never client-controlled; campaign authority lives in campaign_members
        "is_demo": False,
        "must_change_password": False,
        "token_version": 0,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        await db["users"].insert_one(user_doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered.",
        )
    return _build_user_response(user_doc)


@router.post("/login", response_model=TokenResponseSchema)
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT, key_func=get_auth_key)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user = await db["users"].find_one({"username": form_data.username.lower()})

    # Allow direct login if password matches legacy or passlib
    if user is None:
        # Fallback for dev mode / demo accounts when user does not exist yet
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
                "is_admin": False,
                "is_demo": True,
                "token_version": 0,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif not user.get("password_hash") or not verify_password(
        form_data.password, user.get("password_hash", "")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        # Transparently upgrade legacy SHA-256 hashes to secure pbkdf2
        if user.get("password_hash") and legacy_sha256_hash(form_data.password) == user.get(
            "password_hash"
        ):
            new_hash = get_password_hash(form_data.password)
            user_filter = {"_id": user["_id"]} if "_id" in user else {"username": user["username"]}
            await db["users"].update_one(user_filter, {"$set": {"password_hash": new_hash}})
            logger.info(f"Upgraded legacy SHA-256 hash to pbkdf2 for user {user.get('username')}")

    if "has_completed_tutorial" not in user:
        user = {**user, "has_completed_tutorial": True}
    return _issue_token_for_user(user)


@router.post("/demo", response_model=TokenResponseSchema)
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT, key_func=get_auth_key)
async def demo_login(
    request: Request,
    payload: DemoLoginSchema,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    from server.config import settings as demo_settings

    if not demo_settings.DEBUG_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo login is disabled",
        )

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

    # Ensure demo user exists in DB so auth doesn't fail
    existing = await db["users"].find_one({"id": user_id})
    if not existing:
        demo_doc = {
            "id": user_id,
            "username": username,
            "name": name,
            "email": f"{username}@phyrexian.forge",
            "has_completed_tutorial": True,
            "is_admin": False,
            "role": "dm" if dt == "mitsos" else "player",
            "password_hash": "demo",
            "is_demo": True,
            "must_change_password": False,
            "token_version": 0,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            await db["users"].insert_one(demo_doc)
        except DuplicateKeyError:
            pass
        existing = demo_doc
    else:
        existing = {**existing, "is_demo": True}

    return _issue_token_for_user(existing)


@router.get("/me", response_model=UserResponseSchema)
async def get_me(current_user: dict = Depends(get_current_user)):
    return _build_user_response(current_user)


@router.put("/tutorial", response_model=UserResponseSchema)
async def update_tutorial(
    payload: TutorialUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    uid = current_user.get("id")
    res = (
        await _maybe_await(
            db["users"].update_one(
                {"id": uid},
                {"$set": {"has_completed_tutorial": payload.has_completed_tutorial}},
            )
        )
        if uid
        else None
    )
    if (res is None or getattr(res, "matched_count", 0) == 0) and current_user.get("username"):
        await _maybe_await(
            db["users"].update_one(
                {"username": current_user["username"]},
                {"$set": {"has_completed_tutorial": payload.has_completed_tutorial}},
            )
        )
    current_user["has_completed_tutorial"] = payload.has_completed_tutorial
    return _build_user_response(current_user)


@router.post("/change-password", response_model=TokenResponseSchema)
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT, key_func=get_auth_key)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    uid = current_user.get("id")
    user_doc = await _maybe_await(db["users"].find_one({"id": uid})) if uid else None
    if not user_doc and current_user.get("username"):
        user_doc = await _maybe_await(db["users"].find_one({"username": current_user["username"]}))
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if _is_demo_account(user_doc) or bool(current_user.get("is_demo", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo accounts cannot change passwords.",
        )

    existing_hash = user_doc.get("password_hash")
    if existing_hash:
        if not payload.current_password or not verify_password(
            payload.current_password, existing_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )
        if payload.new_password == payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from your current password.",
            )

    new_hash = get_password_hash(payload.new_password)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    expected_tv = int(user_doc.get("token_version") or 0) + 1
    if "_id" in user_doc:
        user_filter = {"_id": user_doc["_id"]}
    elif user_doc.get("id"):
        user_filter = {"id": user_doc["id"]}
    else:
        user_filter = {"username": user_doc["username"]}

    await _maybe_await(
        db["users"].update_one(
            user_filter,
            {
                "$set": {
                    "password_hash": new_hash,
                    "must_change_password": False,
                    "password_changed_at": now_iso,
                },
                "$inc": {"token_version": 1},
            },
        )
    )
    target_uid = (
        user_doc.get("id")
        or uid
        or (f"local_user_{user_doc['username']}" if user_doc.get("username") else None)
    )
    if target_uid:
        await _maybe_await(manager.disconnect_user(target_uid))

    refreshed = await _maybe_await(db["users"].find_one(user_filter))
    merged = dict(refreshed or user_doc)
    merged["password_hash"] = new_hash
    merged["must_change_password"] = False
    merged["has_password"] = True
    merged["token_version"] = max(expected_tv, int(merged.get("token_version") or 0))
    return _issue_token_for_user(merged)


@router.get("/providers", response_model=AuthProvidersSchema)
async def get_auth_providers():
    return AuthProvidersSchema(local=True, discord=settings.discord_oauth_enabled)


@router.get("/discord/login", name="discord_login")
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT, key_func=get_auth_key)
async def discord_login(request: Request):
    _verify_discord_configured()
    redirect_uri = _resolve_discord_redirect_uri(request)
    nonce = secrets.token_urlsafe(16)
    now = datetime.datetime.now(datetime.timezone.utc)
    state_jwt = jwt.encode(
        {
            "purpose": "discord_oauth_state",
            "nonce": nonce,
            "iat": now.timestamp(),
            "exp": now + datetime.timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    async with AsyncOAuth2Client(
        client_id=settings.DISCORD_CLIENT_ID.strip(),
        client_secret=settings.DISCORD_CLIENT_SECRET.strip(),
        redirect_uri=redirect_uri,
        scope="identify email",
    ) as oauth_client:
        authorize_url, _ = oauth_client.create_authorization_url(
            _DISCORD_AUTHORIZE_URL, state=state_jwt
        )

    response = RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=_OAUTH_NONCE_COOKIE,
        value=nonce,
        max_age=300,
        httponly=True,
        samesite="lax",
        secure=_is_https_request(request),
        path="/",
    )
    return response


@router.get("/discord/callback", name="discord_callback")
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT, key_func=get_auth_key)
async def discord_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    _verify_discord_configured()
    frontend_base = _resolve_frontend_base_url()

    def _error_redirect(reason: str) -> RedirectResponse:
        params = urlencode({"oauth_error": reason})
        resp = RedirectResponse(
            url=f"{frontend_base}/login?{params}", status_code=status.HTTP_302_FOUND
        )
        resp.delete_cookie(key=_OAUTH_NONCE_COOKIE, path="/")
        return resp

    if error:
        return _error_redirect("Discord authorization was cancelled.")

    cookie_nonce = request.cookies.get(_OAUTH_NONCE_COOKIE)
    if not code or not state or not cookie_nonce:
        return _error_redirect("Invalid or expired Discord login session.")

    try:
        decoded_state = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return _error_redirect("Invalid or expired Discord login state.")

    if decoded_state.get("purpose") != "discord_oauth_state":
        return _error_redirect("Invalid Discord login state.")

    state_nonce = str(decoded_state.get("nonce") or "")
    if not state_nonce or not hmac.compare_digest(cookie_nonce, state_nonce):
        return _error_redirect("Discord CSRF verification failed.")

    redirect_uri = _resolve_discord_redirect_uri(request)
    try:
        profile = await _exchange_discord_code_and_fetch_profile(code, redirect_uri)
    except Exception as exc:
        logger.warning("Discord OAuth2 code exchange failed: %s", exc)
        return _error_redirect("Could not complete Discord sign-in.")

    discord_id = str(profile.get("id") or "").strip()
    if not discord_id:
        return _error_redirect("Discord profile did not return a user ID.")

    email = (profile.get("email") or "").strip()
    email_verified = bool(profile.get("verified", False))
    display_name = profile.get("global_name") or profile.get("username") or "Adventurer"

    # Match strictly by verified discord_id; never auto-link onto unverified local email registrations
    user = await _maybe_await(db["users"].find_one({"discord_id": discord_id}))

    if user is None:
        base_username = _sanitize_discord_username(
            str(profile.get("username") or display_name), discord_id
        )
        candidate = base_username
        if await _maybe_await(db["users"].find_one({"username": candidate})):
            candidate = f"{base_username[:19]}_{discord_id[-4:]}"
        while await _maybe_await(db["users"].find_one({"username": candidate})):
            candidate = f"{base_username[:17]}_{secrets.token_hex(2)}"

        user_doc = {
            "id": f"discord_user_{discord_id}",
            "username": candidate,
            "password_hash": None,
            "email": email if (email and email_verified) else None,
            "name": str(display_name),
            "discord_id": discord_id,
            "has_completed_tutorial": False,
            "is_admin": False,
            "role": "player",
            "is_demo": False,
            "must_change_password": False,
            "token_version": 0,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            await _maybe_await(db["users"].insert_one(user_doc))
            user = user_doc
        except DuplicateKeyError:
            user = await _maybe_await(db["users"].find_one({"discord_id": discord_id}))
            if user is None:
                return _error_redirect("Account creation conflict. Please try again.")

    now = datetime.datetime.now(datetime.timezone.utc)
    handoff_jti = secrets.token_urlsafe(16)
    handoff_jwt = jwt.encode(
        {
            "purpose": "discord_oauth_handoff",
            "sub": user.get("id") or f"discord_user_{discord_id}",
            "tv": int(user.get("token_version") or 0),
            "jti": handoff_jti,
            "iat": now.timestamp(),
            "exp": now + datetime.timedelta(seconds=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    resp = RedirectResponse(
        url=f"{frontend_base}/auth/callback#code={handoff_jwt}",
        status_code=status.HTTP_302_FOUND,
    )
    resp.delete_cookie(key=_OAUTH_NONCE_COOKIE, path="/")
    return resp


@router.post("/discord/exchange", response_model=TokenResponseSchema)
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT, key_func=get_auth_key)
async def discord_exchange(
    request: Request,
    payload: DiscordExchangeSchema,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    _verify_discord_configured()
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired Discord login code.",
    )
    try:
        decoded = jwt.decode(payload.code, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        raise invalid_exc

    if decoded.get("purpose") != "discord_oauth_handoff":
        raise invalid_exc

    jti = str(decoded.get("jti") or "")
    exp_ts = float(decoded.get("exp") or 0)
    if not await _consume_oauth_handoff_jti(db, jti, exp_ts):
        raise invalid_exc

    user_id = decoded.get("sub")
    if not user_id:
        raise invalid_exc

    user = await _maybe_await(db["users"].find_one({"id": user_id}))
    if not user:
        raise invalid_exc

    token_tv = int(decoded.get("tv") or 0)
    user_tv = int(user.get("token_version") or 0)
    if token_tv < user_tv:
        raise invalid_exc

    return _issue_token_for_user(user)
