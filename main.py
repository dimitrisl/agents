import streamlit as st
import logging
from dotenv import load_dotenv
from backend.core.state_manager import init_session_state
from backend.utils.ui_utils import inject_custom_css
from views.player_dashboard import render_player_dashboard
from views.dm_workspace import render_dm_workspace
from views.settings_view import render_settings_view
from views.library_view import render_library_view
from views.login_view import render_login_view
from backend.core.constants import EDITION_2014, EDITION_2024

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

# Sync query params with session state
if "edition" in st.query_params:
    query_ed = st.query_params["edition"]
    if query_ed == "2024" and not st.session_state.get("dnd_edition_toggle", False):
        st.session_state.dnd_edition_toggle = True
        st.session_state.dnd_edition = EDITION_2024
    elif query_ed == "2014" and st.session_state.get("dnd_edition_toggle", False):
        st.session_state.dnd_edition_toggle = False
        st.session_state.dnd_edition = EDITION_2014
else:
    st.query_params["edition"] = (
        "2024" if st.session_state.get("dnd_edition_toggle", False) else "2014"
    )

# ==========================================
# Authentication Gate
# ==========================================
if not st.session_state.get("user"):
    render_login_view()
    st.stop()

# ==========================================
# Sidebar Navigation & Themes
# ==========================================
with st.sidebar:
    # App Logo
    st.image("assets/logo.png", width="stretch")

    if st.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

    # Determine theme/logo/title colors based on the toggle state
    is_2024 = st.session_state.get("dnd_edition_toggle", False)
    logo_color = "#bf5af2" if is_2024 else "#ff4b4b"
    edition_label_sub = "5.5e Edition" if is_2024 else "5e Legacy"

    st.markdown(
        f"<h2 style='text-align: center; margin-top: -20px; color: {logo_color};'>Phyrexian Forge</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align: center; font-style: italic; margin-top: -15px; color: #888;'>\"All will be one • {edition_label_sub}\"</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    player_label = "🗡️ Player Dashboard"
    dm_label = "🏰 Dungeon Master View"
    library_label = "📚 Rules Library"
    settings_label = "⚙️ Settings"

    toggle_val = st.toggle(
        "Use 2024 Revision (5.5e)",
        value=is_2024,
        key="dnd_edition_toggle_widget",
    )
    if toggle_val != is_2024:
        st.session_state.dnd_edition_toggle = toggle_val
        st.session_state.dnd_edition = EDITION_2024 if toggle_val else EDITION_2014
        st.query_params["edition"] = "2024" if toggle_val else "2014"
        st.rerun()

    st.session_state.dnd_edition_toggle = toggle_val
    st.session_state.dnd_edition = EDITION_2024 if toggle_val else EDITION_2014
    st.info(f"Currently using: **{st.session_state.dnd_edition}**")

    st.markdown("---")

    st.markdown("**🎮 Application Mode:**")
    view_mode = st.radio(
        "Application Mode",
        [player_label, dm_label, library_label, settings_label],
        key="app_view_mode",
        label_visibility="collapsed",
    )

    # Theme configuration
    if is_2024:
        primary_color = "#bf5af2"  # Modern Violet
        accent_color = "#0a84ff"  # Modern Cobalt Blue
    else:
        primary_color = "#ff4b4b"  # Classic Red
        accent_color = "#d4af37"  # Vintage Gold

    # Inject custom CSS
    inject_custom_css(primary_color, accent_color)

    st.markdown("---")
    if st.button("🏠 Return to Main Menu", width="stretch"):
        logger.warning("User returned to main menu (Resetting state).")
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    # --- Recent Rolls Log ---
    st.markdown("### 🎲 Recent Rolls")
    if st.session_state.get("roll_history"):
        # Show last roll prominently
        last_roll = st.session_state.roll_history[0]
        st.success(f"**Latest:** {last_roll}")

        if len(st.session_state.roll_history) > 1:
            with st.expander("History Log", expanded=False):
                for roll in st.session_state.roll_history[1:10]:
                    st.write(f"_{roll}_")

        if st.button("🗑️ Clear Log", key="clear_roll_history", width="stretch"):
            st.session_state.roll_history = []
            st.rerun()
    else:
        st.caption("No rolls recorded yet.")

# Clear active roll when switching view modes
if "last_view_mode" not in st.session_state:
    st.session_state.last_view_mode = view_mode
elif st.session_state.last_view_mode != view_mode:
    st.session_state.last_view_mode = view_mode
    st.session_state.active_roll = None

# ==========================================
# Main Content Router
# ==========================================
if view_mode == dm_label:
    render_dm_workspace()
elif view_mode == library_label:
    render_library_view()
elif view_mode == settings_label:
    render_settings_view()
else:
    render_player_dashboard(accent_color)
