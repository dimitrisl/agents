import streamlit as st
import os
from typing import Optional


def get_google_auth_url() -> str:
    """Mock URL for OAuth if credentials are not fully set"""
    return "?code=mock_google_oauth_code"


def get_discord_auth_url() -> str:
    """Mock URL for Discord OAuth"""
    return "?code=mock_discord_oauth_code"


def process_oauth_callback() -> Optional[dict]:
    """Check if we have an OAuth code in the URL and process it"""
    if "code" in st.query_params:
        # In a real app, we would exchange this code for a token via httpx
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
        elif True:  # Accept any code for now
            # Mock user data
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
