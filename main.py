import streamlit as st
import logging
from dotenv import load_dotenv
from backend.core.state_manager import init_session_state
from backend.utils.ui_utils import inject_custom_css
from views.player_dashboard import render_player_dashboard
from views.dm_workspace import render_dm_workspace
from views.settings_view import render_settings_view
from views.library_view import render_library_view
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

# ==========================================
# Sidebar Navigation & Themes
# ==========================================
with st.sidebar:
    # App Logo
    st.image("assets/logo.png", width="stretch")
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
    dm_label = "🏰 Dungeon Master View"
    library_label = "📚 Rules Library"
    settings_label = "⚙️ Settings"

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
        [player_label, dm_label, library_label, settings_label],
        key="app_view_mode",
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

    st.markdown("---")
    # --- AI Rules Oracle in a Popover ---
    with st.popover("📜 AI Rules Oracle", use_container_width=True):
        st.markdown("### Ask the Oracle")
        rule_query = st.text_input(
            "Ask about a rule or feature:",
            placeholder="e.g. How does Sneak Attack work?",
            key="rule_query_input",
        )

        if st.button("Query Oracle", key="rule_query_btn", use_container_width=True):
            if rule_query:
                from backend.services.rules_service import query_rules

                with st.spinner("Consulting the archives..."):
                    answer = query_rules(rule_query, st.session_state.dnd_edition)
                    st.session_state.last_rule_answer = answer
            else:
                st.warning("Please enter a question.")

        if st.session_state.get("last_rule_answer"):
            st.markdown("---")
            if (
                "⚠️" in st.session_state.last_rule_answer
                or "❌" in st.session_state.last_rule_answer
            ):
                st.error(st.session_state.last_rule_answer)
            else:
                st.info(st.session_state.last_rule_answer)

            if st.button("Clear Answer"):
                st.session_state.last_rule_answer = None
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
