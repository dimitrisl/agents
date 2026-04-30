import streamlit as st
import logging
from dotenv import load_dotenv
from backend.state_manager import init_session_state
from backend.ui_utils import inject_custom_css
from views.player_dashboard import render_player_dashboard
from views.dm_workspace import render_dm_workspace
from backend.constants import EDITION_2014, EDITION_2024

# Load environment variables once at the entry point
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app_debug.log")],
)
logger = logging.getLogger("DnDAssistant")

# ==========================================
# Page Configuration
# ==========================================
st.set_page_config(
    page_title="D&D AI Assistant",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
init_session_state(st.session_state)

# ==========================================
# Sidebar Navigation & Themes
# ==========================================
with st.sidebar:
    # App Logo
    st.image("assets/logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align: center; margin-top: -20px; color: #ff4b4b;'>Phyrexian Forge</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; font-style: italic; margin-top: -15px; color: #888;'>\"All will be one.\"</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    player_label = "🗡️ Player Dashboard"

    is_2024 = st.toggle(
        "Use 2024 Revision (5.5e)",
        value=("2024" in st.session_state.dnd_edition),
    )
    st.session_state.dnd_edition = EDITION_2024 if is_2024 else EDITION_2014
    st.info(f"Currently using: **{st.session_state.dnd_edition}**")

    st.markdown("---")

    st.markdown("**🎮 Application Mode:**")
    view_mode = st.radio(
        "Application Mode",
        [player_label, "🏰 Dungeon Master View"],
        index=0,
        label_visibility="collapsed",
    )

    # Theme configuration
    primary_color = "#ff4b4b"
    accent_color = "#d4af37"

    # Inject custom CSS
    inject_custom_css(primary_color, accent_color)

    st.markdown("---")
    if st.button("🏠 Return to Main Menu", width="stretch"):
        logger.warning("User returned to main menu (Resetting state).")
        st.session_state.clear()
        st.rerun()

# ==========================================
# Main Content Router
# ==========================================
if view_mode == "🏰 Dungeon Master View":
    render_dm_workspace()
else:
    render_player_dashboard(accent_color)
