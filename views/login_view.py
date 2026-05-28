import streamlit as st
import os
import urllib.parse
import httpx
from typing import Optional


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


def render_login_view():
    st.markdown(
        "<h1 style='text-align: center; margin-top: 100px;'>🎲 Phyrexian Forge</h1>",
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

    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        st.write("")
        st.write("")
        st.info("Log in to access your characters and campaigns.")

        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        discord_client_id = os.environ.get("DISCORD_CLIENT_ID")

        st.markdown("##### Quick Access (Mock)")
        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            if st.button("🚀 Google (Mock)", use_container_width=True, type="primary"):
                st.session_state.user = {
                    "id": "mock_google_123",
                    "email": "demo_google@phyrexian.forge",
                    "name": "Demo Google",
                }
                st.rerun()
        with col_mock2:
            if st.button("🎮 Discord (Mock)", use_container_width=True, type="primary"):
                st.session_state.user = {
                    "id": "mock_discord_123",
                    "email": "demo_discord@phyrexian.forge",
                    "name": "Demo Discord",
                }
                st.rerun()

        st.markdown("---")
        st.markdown("##### Production Login")
        if client_id:
            st.link_button(
                "Login with Google", get_google_auth_url(), use_container_width=True
            )
        else:
            st.warning("⚠️ GOOGLE_CLIENT_ID not found in .env.")

        if discord_client_id:
            st.link_button(
                "Login with Discord", get_discord_auth_url(), use_container_width=True
            )
        else:
            st.warning("⚠️ DISCORD_CLIENT_ID not found in .env.")
