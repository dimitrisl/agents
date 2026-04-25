import streamlit as st
import logging
from dotenv import load_dotenv
from backend.state_manager import init_session_state
from backend.ui_utils import inject_custom_css
from views.player_dashboard import render_player_dashboard
from views.dm_workspace import render_dm_workspace

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
    st.title("🎲 D&D AI Assistant")
    st.markdown("---")

    # Dynamic labels based on state
    player_label = "🗡️ Player Dashboard"
    if st.session_state.get("character_active") and st.session_state.get("char_name"):
        player_label = f"🗡️ Hero: {st.session_state.char_name}"

    view_mode = st.radio(
        "Select Mode:", [player_label, "🏰 Dungeon Master View"], index=0
    )

    # Theme configuration
    primary_color = "#ff4b4b"
    accent_color = "#d4af37"

    # Inject custom CSS
    inject_custom_css(primary_color, accent_color)

    st.markdown("---")
    if st.button("✨ Reset App State", width="stretch"):
        logger.warning("User initiated App State Reset.")
        st.session_state.clear()
        st.rerun()

# ==========================================
# Main Content Router
# ==========================================
if view_mode == "🏰 Dungeon Master View":
    render_dm_workspace()
else:
    render_player_dashboard(accent_color)
