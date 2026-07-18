import streamlit as st
import logging
import os
from backend.utils.ui_utils import (
    render_active_roll_visual,
)

from views.dm.campaign_manager import _render_campaign_selection, _render_campaign_notes
from views.dm.party_tracker import _render_party_tracker, _render_party_dashboard
from views.dm.ai_generators import _render_ai_generators
from views.dm.initiative_tracker import (
    _render_initiative_tracker,
    _render_roll_requests_section,
)
from views.dm.whisper_chat import _render_whisper_chat_section

logger = logging.getLogger("DnDAssistant.DMView")


def render_dm_workspace():
    """Renders the main Dungeon Master Workspace view."""
    st.title("Dungeon Master Workspace")
    render_active_roll_visual()

    if not st.session_state.get("active_campaign_name"):
        st.info(
            "👋 Welcome to the Dungeon Master Workspace! Please select or create a Campaign to begin."
        )
        _render_campaign_selection()
    else:
        col_title, col_close = st.columns([4, 1], vertical_alignment="center")
        col_title.markdown(
            f"### Active Campaign: **{st.session_state.active_campaign_name}**"
        )
        if col_close.button("🚪 Close Campaign", key="close_camp_btn", width="stretch"):
            st.session_state.active_campaign_name = None
            st.rerun()

        dm_tab1, dm_tab2, dm_tab3, dm_tab4, dm_tab5, dm_tab6 = st.tabs(
            [
                "📝 Campaign Notes",
                "👥 Party Manager",
                "📊 Party Dashboard",
                "🎲 AI Generators",
                "⚔️ Initiative Tracker",
                "💬 Whisper Chat",
            ]
        )

        with dm_tab1:
            _render_campaign_notes()

        with dm_tab2:
            _render_party_tracker()

        with dm_tab3:
            _render_party_dashboard()
            _render_roll_requests_section("dashboard")

        with dm_tab4:
            _render_ai_generators()

        with dm_tab5:
            _render_initiative_tracker()
            _render_roll_requests_section("tracker")

        with dm_tab6:
            _render_whisper_chat_section()


@st.dialog("NPC Stat Block", width="large")
def show_npc_stat_block(npc_data):
    st.markdown(f"## {npc_data.get('char_name', 'Unknown')}")
    st.caption(
        f"{npc_data.get('race', 'Unknown')} {npc_data.get('char_class', 'Monster')}"
    )
    st.markdown("---")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**Armor Class:** {npc_data.get('armor_class', 10)}")
        st.markdown(f"**Hit Points:** {npc_data.get('hp_max', 10)}")
        st.markdown(f"**Speed:** {npc_data.get('speed', 30)} ft.")
        st.markdown("---")

        stats = npc_data.get("stats", {})
        st_col = st.columns(6)
        st_col[0].metric("STR", stats.get("STR", 10))
        st_col[1].metric("DEX", stats.get("DEX", 10))
        st_col[2].metric("CON", stats.get("CON", 10))
        st_col[3].metric("INT", stats.get("INT", 10))
        st_col[4].metric("WIS", stats.get("WIS", 10))
        st_col[5].metric("CHA", stats.get("CHA", 10))

        st.markdown("---")
        st.markdown("### Traits")
        for trait in npc_data.get("features_traits", []):
            if isinstance(trait, dict):
                st.markdown(
                    f"**{trait.get('name', 'Feature')}.** {trait.get('description', '')}"
                )
            else:
                st.markdown(f"**Feature.** {trait}")

        st.markdown("### Actions")
        for weapon in npc_data.get("weapons", []):
            if isinstance(weapon, dict):
                st.markdown(
                    f"**{weapon.get('name', 'Attack')}.** *Attack:* {weapon.get('attack_bonus', '+0')} to hit. *Hit:* {weapon.get('damage_dice', '')} damage."
                )
            else:
                st.markdown(f"**Attack.** {weapon}")

    with col2:
        img_path = npc_data.get("char_portrait")
        if img_path and os.path.exists(img_path):
            st.image(img_path, use_container_width=True)
