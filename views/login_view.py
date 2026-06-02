import streamlit as st
import os
import urllib.parse
import httpx
from typing import Optional
from backend.core.db import get_db
from backend.utils.auth_utils import hash_password


def get_google_auth_url() -> str:
    """Mock URL for OAuth if credentials are not fully set"""
    return "?code=mock_google_oauth_code"


def get_discord_auth_url() -> str:
    """Construct URL for Discord OAuth"""
    client_id = os.environ.get("DISCORD_CLIENT_ID")
    if not client_id:
        return "?code=mock_discord_oauth_code"

    redirect_uri = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:8501/")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify email",
    }
    return f"https://discord.com/api/oauth2/authorize?{urllib.parse.urlencode(params)}"


def process_oauth_callback() -> Optional[dict]:
    """Check if we have an OAuth code in the URL and process it"""
    if "code" in st.query_params:
        code = st.query_params["code"]

        if code == "mock_google_oauth_code":
            user_data = {
                "id": "google_mock_user_123",
                "email": "player@example.com",
                "name": "D&D Player (Google)",
            }
            st.query_params.clear()
            return user_data
        elif code == "mock_discord_oauth_code":
            user_data = {
                "id": "discord_mock_user_456",
                "email": "discord_user@example.com",
                "name": "D&D Player (Discord)",
            }
            st.query_params.clear()
            return user_data

        # Real OAuth execution
        client_id = os.environ.get("DISCORD_CLIENT_ID")
        client_secret = os.environ.get("DISCORD_CLIENT_SECRET")
        redirect_uri = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:8501/")

        if client_id and client_secret:
            try:
                # 1. Exchange code for token
                data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                }
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                resp = httpx.post(
                    "https://discord.com/api/oauth2/token",
                    data=data,
                    headers=headers,
                    timeout=10,
                )
                resp.raise_for_status()
                token_data = resp.json()

                # 2. Get User Info
                access_token = token_data.get("access_token")
                user_resp = httpx.get(
                    "https://discord.com/api/users/@me",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                user_resp.raise_for_status()
                discord_user = user_resp.json()

                user_data = {
                    "id": str(discord_user.get("id")),
                    "email": discord_user.get("email"),
                    "name": discord_user.get("username"),
                }
                st.query_params.clear()
                return user_data
            except Exception as e:
                st.error(f"Discord OAuth failed: {e}")
                st.query_params.clear()
                return None

        # Fallback accept unknown code (for Google mock if needed)
        user_data = {
            "id": "oauth_mock_user_789",
            "email": "player@example.com",
            "name": "D&D Player",
        }
        st.query_params.clear()
        return user_data
    return None


def verify_user(username: str, password: str) -> Optional[dict]:
    db = get_db()
    if db is None:
        return None
    users_col = db["users"]
    user = users_col.find_one({"username": username.strip().lower()})
    if user and user.get("password_hash") == hash_password(password):
        return {
            "id": f"local_user_{user['username']}",
            "email": user.get("email"),
            "name": user.get("name"),
        }
    return None


def create_user(username: str, password: str) -> str:
    db = get_db()
    if db is None:
        return "Database connection error."
    users_col = db["users"]
    username_clean = username.strip().lower()
    if not username_clean:
        return "Username cannot be empty."
    if len(password) < 4:
        return "Password must be at least 4 characters long."

    if users_col.find_one({"username": username_clean}):
        return "Username already exists."

    # Protected Administrative Names
    if username_clean in ["admin", "mitsos", "phyrexian"]:
        return "Username is reserved for the Machine Orthodoxy."

    user_doc = {
        "username": username_clean,
        "password_hash": hash_password(password),
        "email": f"{username_clean}@phyrexian.forge",
        "name": username.strip(),
    }
    users_col.insert_one(user_doc)
    return "success"


def list_users() -> list[dict]:
    """Return all registered local users (username + name), for DM use."""
    db = get_db()
    if db is None:
        return []
    try:
        users = db["users"].find({}, {"username": 1, "name": 1, "_id": 0})
        return [
            {"username": u["username"], "name": u.get("name", u["username"])}
            for u in users
        ]
    except Exception:
        return []


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Reconstruct user dict from a stored user_id string."""
    db = get_db()
    if db is None:
        return None
    # user_id format: "local_user_{username}"
    if user_id.startswith("local_user_"):
        username = user_id[len("local_user_") :]
        user = db["users"].find_one({"username": username})
        if user:
            return {
                "id": user_id,
                "email": user.get("email"),
                "name": user.get("name", username),
            }
    return None


def render_login_view():
    st.markdown(
        "<h1 style='text-align: center; margin-top: 50px;'>🎲 Phyrexian Forge</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h3 style='text-align: center; color: #888;'>Authentication Required</h3>",
        unsafe_allow_html=True,
    )

    # Process callback if returning from OAuth
    user = process_oauth_callback()
    if user:
        st.session_state.user = user
        st.rerun()

    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        st.write("")

        tab_login, tab_register = st.tabs(["🔑 Login", "🆕 Create Account"])

        with tab_login:
            login_username = st.text_input("Username", key="login_username_input")
            login_password = st.text_input(
                "Password", type="password", key="login_password_input"
            )
            if st.button(
                "Log In",
                type="primary",
                use_container_width=True,
                key="login_submit_btn",
            ):
                user = verify_user(login_username, login_password)
                if user:
                    st.session_state.user = user
                    st.toast("✅ Logged in successfully!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password.")

        with tab_register:
            reg_username = st.text_input("Username", key="reg_username_input")
            reg_password = st.text_input(
                "Password", type="password", key="reg_password_input"
            )
            reg_confirm = st.text_input(
                "Confirm Password", type="password", key="reg_confirm_input"
            )
            if st.button(
                "Create Account",
                type="primary",
                use_container_width=True,
                key="reg_submit_btn",
            ):
                if reg_password != reg_confirm:
                    st.error("❌ Passwords do not match.")
                else:
                    result = create_user(reg_username, reg_password)
                    if result == "success":
                        st.success(
                            "✅ Account created successfully! You can now log in."
                        )
                    else:
                        st.error(f"❌ {result}")

        st.markdown("---")
        st.markdown("##### ⚡ Quick Access (Mock OAuth)")
        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            if st.button(
                "🚀 Google (Mock)", use_container_width=True, key="btn_mock_google"
            ):
                st.session_state.user = {
                    "id": "mock_google_123",
                    "email": "demo_google@phyrexian.forge",
                    "name": "Demo Google",
                }
                st.rerun()
        with col_mock2:
            if st.button(
                "🎮 Discord (Mock)", use_container_width=True, key="btn_mock_discord"
            ):
                st.session_state.user = {
                    "id": "mock_discord_123",
                    "email": "demo_discord@phyrexian.forge",
                    "name": "Demo Discord",
                }
                st.rerun()

        st.markdown("---")
        st.markdown("##### Production OAuth Login")
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        discord_client_id = os.environ.get("DISCORD_CLIENT_ID")

        if client_id:
            st.link_button(
                "Login with Google", get_google_auth_url(), use_container_width=True
            )
        else:
            st.caption("ℹ️ Google login not configured (missing CLIENT_ID).")

        if discord_client_id:
            st.link_button(
                "Login with Discord", get_discord_auth_url(), use_container_width=True
            )
        else:
            st.caption("ℹ️ Discord login not configured (missing CLIENT_ID).")
