import streamlit as st
import logging

from backend.core.state_manager import (
    get_character_dict,
    update_session_from_dict,
)
from backend.core.constants import (
    EDITION_2014,
    EDITION_2024,
)

from views.player.selection_screen import render_selection_screen
from views.player.character_sheet import render_active_character
from views.player.character_creator import render_character_creator
from views.player._helpers import trigger_sync, show_pdf_export_preview

logger = logging.getLogger(__name__)


def render_player_dashboard(accent_color: str):
    """Renders the main Player Dashboard view."""
    # Auto-restore character from URL ?cid= on refresh
    if not st.session_state.get("character_active"):
        cid_param = st.query_params.get("cid")
        if cid_param:
            from backend.repositories.character_repository import (
                CharacterRepository as _CRep,
            )

            _cr = _CRep()
            owner_id = st.session_state.get("user", {}).get("id")
            char_files = _cr.list_all(owner_id=owner_id)
            for cf in char_files:
                if cid_param in cf:
                    cdata = _cr.load(cf)
                    if cdata:
                        try:
                            update_session_from_dict(st.session_state, cdata)
                        except Exception as e:
                            logger.error(
                                f"Failed to load character state for {cid_param}: {e}"
                            )
                            st.error(f"Failed to load hero state: {cid_param}")
                            st.stop()
                        st.session_state.character_active = True
                        st.session_state.player_view = "sheet"
                        is_char_2024 = "2024" in cdata.get("dnd_edition", "")
                        st.session_state.dnd_edition_toggle = is_char_2024
                        st.session_state.dnd_edition = (
                            EDITION_2024 if is_char_2024 else EDITION_2014
                        )
                        st.query_params["edition"] = "2024" if is_char_2024 else "2014"
                        break

    # Sidebar navigation for the Player Dashboard
    has_active_hero = bool(
        st.session_state.get("char_name")
        and st.session_state.get("char_name") != "New Hero"
    )

    with st.sidebar:
        st.markdown("### ⚙️ Hero Controls")

        panel_options = ["📂 Character Vault"]
        if has_active_hero:
            panel_options.insert(0, "🛡️ Active Character Sheet")

        default_index = (
            0
            if (st.session_state.get("character_active", False) and has_active_hero)
            else (len(panel_options) - 1)
        )

        selected_panel = st.radio(
            "Navigation",
            panel_options,
            index=default_index,
            label_visibility="collapsed",
        )

        if (
            selected_panel == "📂 Character Vault"
            and st.session_state.get("character_active", False)
            and st.session_state.get("player_view") != "forge"
        ):
            st.session_state.character_active = False
            st.query_params.pop("cid", None)
            st.query_params.pop("edition", None)
            st.rerun()
        elif selected_panel == "🛡️ Active Character Sheet" and not st.session_state.get(
            "character_active", False
        ):
            st.session_state.character_active = True
            st.rerun()

        if (
            st.session_state.character_active
            and st.session_state.player_view == "sheet"
        ):
            if st.button(
                "🔄 Sync & Refresh Sheet",
                type="primary",
                width="stretch",
                key="side_sync",
            ):
                trigger_sync()
                st.rerun()
            if st.button("💾 Save to File", width="stretch", key="side_save"):
                if st.session_state.char_name.strip():
                    trigger_sync()
                    st.success("Character Saved!")
                else:
                    st.warning("⚠️ Please name your character before saving.")

            if st.button("🚪 Exit Hero", width="stretch", key="side_exit_hero"):
                from backend.core.state_manager import init_session_state

                st.session_state.character_active = False
                st.query_params.pop("cid", None)
                st.query_params.pop("edition", None)
                init_session_state(st.session_state, force=True)
                st.rerun()

            if st.button(
                "📥 Reload from Vault",
                width="stretch",
                key="side_reload_vault",
                help="Discard local changes and reload from DB",
            ):
                from backend.core.storage import load_character

                char_id = st.session_state.get("char_id")
                char_name = st.session_state.get("char_name")
                filename = f"{char_name.replace(' ', '_').lower()}_{char_id}.json"

                # Clear cache to force fresh load
                if "char_cache" in st.session_state:
                    if filename in st.session_state.char_cache:
                        del st.session_state.char_cache[filename]

                char_data = load_character(filename)
                if char_data:
                    try:
                        update_session_from_dict(st.session_state, char_data)
                    except Exception as e:
                        logger.error(f"Reload failed for {filename}: {e}")
                        st.error("Reload failed.")
                        st.stop()
                    st.toast("✅ Character reloaded from vault!")
                    st.rerun()
                else:
                    st.error("Failed to reload character.")

        st.markdown("---")

        # ── Active Campaign status ─────────────────────────────────────────────
        active_camp = st.session_state.get("active_campaign")
        if active_camp:
            st.markdown("##### 🗺️ Campaign")
            st.success(f"📍 **{active_camp}**")

    if not st.session_state.character_active:
        render_selection_screen()
    else:
        import json

        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            pass  # Title removed for cleaner UI
        with col2:
            if st.session_state.player_view == "sheet":
                char_dict = get_character_dict(st.session_state)
                if st.button(
                    "📥 Download PDF",
                    key="btn_open_pdf_dialog",
                    use_container_width=True,
                ):
                    show_pdf_export_preview(char_dict)
            else:
                # Definitive fix: In forge mode, always show "Cancel" to avoid old name persistence
                if st.button("🔙 Cancel", width="stretch"):
                    st.session_state.player_view = "sheet"
                    # If we don't have an active character (meaning we came from selection), go back to selection
                    if (
                        st.session_state.char_name == "New Hero"
                        or not st.session_state.get("character_active")
                    ):
                        st.session_state.character_active = False
                    st.rerun()
        with col3:
            if st.session_state.player_view == "sheet":
                from backend.utils.export_utils import convert_to_vtt_format

                char_dict = get_character_dict(st.session_state)
                vtt_char = convert_to_vtt_format(char_dict)
                json_str = json.dumps(vtt_char, indent=4)

                st.download_button(
                    label="💾 Export for VTT",
                    data=json_str,
                    file_name=f"{char_dict['char_name'].replace(' ', '_').lower()}_vtt.json",
                    mime="application/json",
                    width="stretch",
                )
        with col4:
            if st.button("🔄 Exit Hero", width="stretch", key="top_exit_hero_btn"):
                # Clear critical session state and query params before exiting
                from backend.core.state_manager import init_session_state

                st.session_state.character_active = False
                st.query_params.pop("cid", None)
                st.query_params.pop("edition", None)
                init_session_state(st.session_state, force=True)  # Reset to defaults
                st.rerun()

        if st.session_state.player_view == "sheet":
            # --- Main Content ---
            render_active_character(accent_color)
        else:
            render_character_creator()
