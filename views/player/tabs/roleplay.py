import streamlit as st
import logging

from backend.services.forge_service import (
    generate_playstyle_guide,
)
from backend.core.storage import (
    save_character,
)
from backend.core.state_manager import (
    get_character_dict,
)
from backend.utils.ui_utils import (
    render_themed_markdown,
)


logger = logging.getLogger(__name__)


def _render_roleplay(edit_mode: bool):
    """Renders backstory, personality traits, ideals, bonds, and flaws."""
    st.markdown("#### Backstory")
    if edit_mode:
        st.session_state.backstory = st.text_area(
            "Backstory", value=st.session_state.backstory, height=100
        )
    else:
        st.write(
            st.session_state.backstory
            if st.session_state.backstory
            else "No backstory provided."
        )

    st.markdown("---")
    st.markdown("#### Personality & Roleplay")
    if edit_mode:
        st.session_state.personality_traits = st.text_area(
            "Personality Traits", st.session_state.personality_traits, height=68
        )
        st.session_state.ideals = st.text_area(
            "Ideals", st.session_state.ideals, height=68
        )
        st.session_state.bonds = st.text_area(
            "Bonds", st.session_state.bonds, height=68
        )
        st.session_state.flaws = st.text_area(
            "Flaws", st.session_state.flaws, height=68
        )
    else:
        col_p1, col_p2 = st.columns(2)
        col_p1.write(f"**Personality:** {st.session_state.personality_traits}")
        col_p1.write(f"**Ideals:** {st.session_state.ideals}")
        col_p2.write(f"**Bonds:** {st.session_state.bonds}")
        col_p2.write(f"**Flaws:** {st.session_state.flaws}")

    st.markdown("---")
    st.markdown("#### Languages & Tools")
    if edit_mode:
        st.session_state.languages = st.text_input(
            "Languages (comma-separated)", ", ".join(st.session_state.languages)
        ).split(", ")
        st.session_state.tool_proficiencies = st.text_input(
            "Tool Proficiencies (comma-separated)",
            ", ".join(st.session_state.tool_proficiencies),
        ).split(", ")
    else:
        st.write(f"**Languages:** {', '.join(st.session_state.languages)}")
        st.write(
            f"**Tool Proficiencies:** {', '.join(st.session_state.tool_proficiencies)}"
        )


def _render_campaign_chronicle():
    """Renders campaign session logs/chronicles in a beautiful parchment layout."""
    char_id = st.session_state.get("char_id", "")
    char_name = st.session_state.get("char_name", "")
    char_filename = f"{char_name.replace(' ', '_').lower()}_{char_id}.json"

    from backend.core.db import get_db

    db = get_db()
    if db is None:
        st.error("Database connection missing.")
        return

    # Find campaign this character is active in
    campaign = db["campaigns"].find_one({"party": char_filename})
    if not campaign:
        st.info("Your character is not assigned to any campaign chronicle.")
        return

    sessions = campaign.get("sessions", [])
    if not sessions:
        st.info("No chronicles have been recorded for this campaign yet.")
        return

    st.markdown(
        "<h2 style='text-align: center; font-family: \"Georgia\", serif;'>📜 The Campaign Chronicle</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; font-style: italic; color: #888; margin-bottom: 30px;'>A historic archive of your party's deeds and trials.</p>",
        unsafe_allow_html=True,
    )

    # Let's style the chronicle logs to look like premium parchment pages
    for s in sorted(sessions, key=lambda x: x.get("session_number", 0)):
        session_num = s.get("session_number", 1)
        recap = s.get("actual_recap", "")

        if not recap.strip():
            continue

        st.markdown(
            f"""
            <div style='
                background: linear-gradient(180deg, #1c1512 0%, #120c0a 100%);
                border: 1px solid #3d2a20;
                border-left: 5px solid #a87f60;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            '>
                <h3 style='color: #a87f60; font-family: "Georgia", serif; margin-top: 0; margin-bottom: 12px; border-bottom: 1px solid rgba(168, 127, 96, 0.2); padding-bottom: 8px;'>
                    Chapter {session_num}: The Story So Far
                </h3>
                <div style='
                    color: #dcd6cd;
                    font-family: "Georgia", serif;
                    font-size: 1.05rem;
                    line-height: 1.8;
                    white-space: pre-line;
                '>
                    {recap}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_playstyle_guide(edit_mode: bool):
    """Renders the AI-generated strategy and roleplay guide."""
    st.markdown("### 📖 Strategic Playstyle Guide")
    st.info(
        "This guide helps you master your character's mechanics and roleplay. It is generated via a separate AI analysis."
    )

    if not st.session_state.playstyle_guide:
        if st.button("✨ Generate Playstyle Guide", width="stretch", type="primary"):
            with st.spinner("Analyzing character build and strategy..."):
                char_data = get_character_dict(st.session_state)
                st.session_state.playstyle_guide = generate_playstyle_guide(char_data)
                # Re-get dict to include the new guide
                updated_char_data = get_character_dict(st.session_state)
                save_character(updated_char_data)
                st.rerun()
    else:
        if edit_mode:
            st.session_state.playstyle_guide = st.text_area(
                "Playstyle Guide (Markdown supported)",
                st.session_state.playstyle_guide,
                height=500,
            )
        else:
            render_themed_markdown(st.session_state.playstyle_guide)
            if st.button("🔄 Regenerate Guide", width="stretch"):
                st.session_state.playstyle_guide = ""
                st.rerun()
