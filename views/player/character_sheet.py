import streamlit as st
import logging

from backend.services.rules_service import (
    validate_character_build,
)
from backend.core.storage import (
    save_character,
)
from backend.core.state_manager import (
    get_character_dict,
    _set_val,
)
from backend.services.mechanics_service import (
    get_modifier as calculate_modifier,
)
from backend.utils.ui_utils import (
    render_character_header,
    render_active_roll_visual,
)
from backend.utils.image_utils import generate_portrait_url, save_custom_portrait

from views.player.tabs.core_stats import _render_core_stats
from views.player.tabs.combat_inventory import _render_combat_inventory
from views.player.tabs.features_spells import _render_features_spells
from views.player.tabs.roleplay import (
    _render_roleplay,
    _render_campaign_chronicle,
    _render_playstyle_guide,
)
from views.player._helpers import log_roll, trigger_sync
from views.player.level_up import run_level_up_wizard

logger = logging.getLogger(__name__)


def render_active_character(accent_color: str):
    """Renders the active character sheet and management tools."""
    # Stylized Header Banner
    render_character_header(
        st.session_state.char_name,
        st.session_state.race,
        st.session_state.char_class,
        st.session_state.char_level,
        st.session_state.background,
        st.session_state.alignment,
        accent_color,
        portrait_url=st.session_state.char_portrait,
        subclass=st.session_state.get("subclass"),
    )
    st.caption(f"📜 Ruleset: {st.session_state.dnd_edition}")
    render_active_roll_visual()

    # ------------------------------------------
    # Private DM Roll Request system (Auto-Refresh Fragment)
    # ------------------------------------------    @st.fragment(run_every=5)
    def render_dm_roll_notifications():
        char_id = st.session_state.get("char_id", "")
        char_name = st.session_state.get("char_name", "")
        char_filename = f"{char_name.replace(' ', '_').lower()}_{char_id}.json"

        from backend.core.db import get_db

        db = get_db()
        if db is not None:
            # Find all campaigns where this character is a party member
            campaigns_cursor = db["campaigns"].find({"party": char_filename})
            all_requests = []
            for camp_data in campaigns_cursor:
                roll_requests = camp_data.get("roll_requests", [])
                camp_name = camp_data.get("campaign_name")
                for req in roll_requests:
                    if (
                        req.get("status") == "pending"
                        or req.get("status") == "completed"
                    ) and (
                        (char_id and char_id in req.get("char_filename", ""))
                        or (char_name and char_name == req.get("char_name"))
                    ):
                        req_copy = dict(req)
                        req_copy["campaign_name"] = camp_name
                        all_requests.append(req_copy)

            # Show only the absolute latest request across all campaigns
            if all_requests:
                all_requests.sort(key=lambda x: x.get("created_at", ""))
                req = all_requests[-1]
                active_campaign = req.get("campaign_name")
                status = req.get("status")

                # Auto-dismiss logic for completed rolls
                if status == "completed":
                    import time

                    dismiss_key = f"dismiss_time_{req['id']}"
                    if dismiss_key not in st.session_state:
                        st.session_state[dismiss_key] = time.time() + 10  # Hide in 10s

                    if time.time() > st.session_state[dismiss_key]:
                        # Hide by effectively ignoring it in the next loop
                        return

                is_secret = req.get("is_secret", False)
                roll_title = (
                    f"🎲 Private Roll Request (SECRET): {active_campaign}"
                    if is_secret
                    else f"🎲 Private Roll Request: {active_campaign}"
                )
                secret_warning = (
                    "<p style='font-weight: bold; color: #ff9900; margin: 5px 0;'>🔒 Note: This is a SECRET roll. The final result will only be visible to the DM.</p>"
                    if is_secret
                    else ""
                )

                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div style='background-color: rgba(255, 75, 75, 0.15); border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 5px; margin-bottom: 10px;'>
                            <h4 style='color: #ff4b4b; margin: 0;'>{roll_title}</h4>
                            <p style='margin: 5px 0;'>The DM is requesting a <strong>{req["roll_type"]}</strong>.</p>
                            {secret_warning}
                            {f"<p style='font-style: italic; color: #aaa; margin: 5px 0;'>Reason: \"{req['reason']}\"</p>" if req.get("reason") else ""}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if status == "pending":
                        # Calculate modifier
                        stat_key = req.get("stat")
                        roll_type_lower = req["roll_type"].lower()

                        modifier = 0
                        if "saving throw" in roll_type_lower:
                            saves = st.session_state.get("saving_throw_values", {})
                            modifier = saves.get(
                                stat_key,
                                calculate_modifier(
                                    st.session_state.stats.get(stat_key, 10)
                                ),
                            )
                        elif "check" in roll_type_lower and stat_key in [
                            "STR",
                            "DEX",
                            "CON",
                            "INT",
                            "WIS",
                            "CHA",
                        ]:
                            modifier = calculate_modifier(
                                st.session_state.stats.get(stat_key, 10)
                            )
                        elif "check" in roll_type_lower:
                            skills = st.session_state.get("skills", {})
                            modifier = skills.get(stat_key, 0)
                        else:
                            modifier = 0

                        btn_label = "Roll Secretly" if is_secret else "Roll 1d20"
                        if modifier >= 0:
                            btn_label += f" + {modifier}"
                        else:
                            btn_label += f" - {abs(modifier)}"

                        col_roll1, col_roll2, col_dismiss = st.columns([1.5, 3, 1])
                        from backend.core.storage import submit_roll_result

                        if col_roll1.button(
                            f"🎲 {btn_label}",
                            key=f"btn_dm_roll_{req['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            from backend.utils.dice import quick_roll

                            res, raw = quick_roll(20, modifier)
                            result_text = f"{res} (d20: {raw} + {modifier})"

                            if is_secret:
                                log_roll(
                                    f"**{req['roll_type']}** (Secret DM Request): **Roll Sent Secretly**"
                                )
                                st.session_state.active_roll = {
                                    "label": f"{req['roll_type']} (Secret Roll)",
                                    "sides": 20,
                                    "raw": "?",
                                    "modifier": modifier,
                                    "total": "?",
                                    "adv_type": "None",
                                }
                            else:
                                log_roll(
                                    f"**{req['roll_type']}** (DM Request): **{res}** (d20: {raw} + {modifier})"
                                )
                                st.session_state.active_roll = {
                                    "label": f"{req['roll_type']} (DM Request)",
                                    "sides": 20,
                                    "raw": raw,
                                    "modifier": modifier,
                                    "total": res,
                                    "adv_type": "None",
                                }

                            if submit_roll_result(
                                active_campaign, req["id"], result_text
                            ):
                                st.rerun()
                            else:
                                st.error("Failed to submit roll result.")

                        if col_dismiss.button(
                            "🗑️ Dismiss",
                            key=f"btn_dismiss_roll_{req['id']}",
                            use_container_width=True,
                        ):
                            if submit_roll_result(
                                active_campaign, req["id"], "Dismissed by player"
                            ):
                                st.rerun()
                    else:
                        # Roll completed, show success message briefly
                        if is_secret:
                            st.success("🎲 Secret roll submitted to DM (Result hidden)")
                        else:
                            st.success(f"🎲 Rolled: **{req.get('result')}**")
                        st.caption("This notification will disappear automatically.")

    render_dm_roll_notifications()

    @st.fragment(run_every=5)
    def render_dm_whispers_channel():
        char_id = st.session_state.get("char_id", "")
        char_name = st.session_state.get("char_name", "")
        char_filename = f"{char_name.replace(' ', '_').lower()}_{char_id}.json"

        from backend.core.db import get_db

        db = get_db()
        if db is not None:
            # Find campaign this character is active in
            campaign = db["campaigns"].find_one({"party": char_filename})
            if campaign:
                campaign_name = campaign.get("campaign_name")
                whispers = campaign.get("whispers", [])

                # Filter whispers that involve this character
                my_whispers = [
                    w
                    for w in whispers
                    if w.get("sender") == char_name
                    or w.get("recipient") == char_name
                    or w.get("recipient") == "All"
                ]

                # Limit to the last 3 messages to prevent overflow
                my_whispers = my_whispers[-3:]

                # Render in a collapsible expander
                with st.expander("💬 DM Whisper Channel", expanded=False):
                    st.caption(f"Campaign: {campaign_name}")

                    # Message Log Area
                    chat_html = ""
                    for w in my_whispers:
                        sender = w.get("sender", "Unknown")
                        msg = w.get("message", "")
                        time_str = w.get("timestamp", "")

                        # Style differently for DM vs me
                        if sender == "DM":
                            bg_style = "rgba(255, 75, 75, 0.08)"
                            border_style = "border-left: 3px solid #ff4b4b"
                            color_style = "#ff4b4b"
                        else:
                            bg_style = "rgba(255, 255, 255, 0.05)"
                            border_style = "border-left: 3px solid #555"
                            color_style = "#ccc"

                        chat_html += f"""
                        <div style='background-color: {bg_style}; {border_style}; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px;'>
                            <div style='display: flex; justify-content: space-between; font-size: 0.8rem; color: #888;'>
                                <span style='font-weight: bold; color: {color_style};'>{sender}</span>
                                <span>{time_str}</span>
                            </div>
                            <div style='margin-top: 4px; color: #e0e0e0;'>{msg}</div>
                        </div>
                        """

                    if chat_html:
                        st.html(
                            f"<div style='max-height: 200px; overflow-y: auto; margin-bottom: 10px;'>{chat_html}</div>"
                        )
                    else:
                        st.info("No private whispers yet.")

                    # Message input using form to clear automatically on submit
                    with st.form(key="player_whisper_form", clear_on_submit=True):
                        col_input, col_send = st.columns(
                            [4, 1], vertical_alignment="bottom"
                        )
                        w_msg = col_input.text_input(
                            "Whisper to DM",
                            label_visibility="collapsed",
                            placeholder="Type a message to DM...",
                        )
                        submitted = col_send.form_submit_button(
                            "Send", use_container_width=True
                        )
                        if submitted:
                            if w_msg.strip():
                                from backend.core.storage import send_whisper

                                if send_whisper(
                                    campaign_name, char_name, "DM", w_msg.strip()
                                ):
                                    st.toast("Whisper sent to DM!")
                                    st.rerun()
                            else:
                                st.error("Failed to send whisper.")

    render_dm_whispers_channel()

    # ------------------------------------------
    # Auto-Save & Auto-Sync System
    # ------------------------------------------
    def sync_and_save_on_toggle():
        """Callback triggered when the Edit Mode toggle is changed."""
        # If it was toggled OFF, save any changes
        if not st.session_state.get("edit_mode", False):
            # 1. Check if data editors have pending changes
            editor_changes = False
            for editor_key in [
                "edit_equip_table",
                "edit_weapons",
                "edit_advancements",
                "edit_features",
                "edit_spells",
            ]:
                deltas = st.session_state.get(editor_key, {})
                if deltas:
                    if (
                        deltas.get("edited_rows")
                        or deltas.get("added_rows")
                        or deltas.get("deleted_rows")
                    ):
                        editor_changes = True
                        break

            current_char = get_character_dict(st.session_state)

            # Check for direct session state changes
            state_changes = False
            if st.session_state.get("last_saved_char") is not None:
                for k, v in current_char.items():
                    if k in [
                        "armor_class",
                        "hp_max",
                        "initiative_modifier",
                        "passive_perception",
                        "proficiency_bonus",
                        "hit_dice",
                    ]:
                        continue

                    saved_val = st.session_state.last_saved_char.get(k)

                    # Custom comparison helper to ignore list order for simple lists
                    def is_equal(val1, val2):
                        if isinstance(val1, list) and isinstance(val2, list):
                            if all(
                                isinstance(x, (str, int, float)) for x in val1
                            ) and all(isinstance(x, (str, int, float)) for x in val2):
                                return sorted(val1) == sorted(val2)
                        return val1 == val2

                    if not is_equal(v, saved_val):
                        state_changes = True
                        break
            else:
                state_changes = True

            if editor_changes or state_changes:
                trigger_sync()
                # trigger_sync() already saved the changes to the database.
                # Just capture the latest synchronized dict for last_saved_char cache.
                st.session_state.last_saved_char = get_character_dict(st.session_state)
                st.session_state.needs_validation = True

            # Invalidate editor dataframes to force recreation of UI components
            if "equip_df_editor" in st.session_state:
                del st.session_state["equip_df_editor"]
            if "weapons_df_editor" in st.session_state:
                del st.session_state["weapons_df_editor"]

    if st.session_state.get("leveling_up", False):
        with st.expander("⬆️ Level Up Wizard", expanded=True):
            st.write(f"Leveling up to {st.session_state.char_level + 1}...")
            if st.button("Confirm Level Up"):
                st.session_state.char_level += 1
                st.session_state.leveling_up = False
                st.rerun()
            if st.button("Cancel"):
                st.session_state.leveling_up = False
                st.rerun()

    # Dynamic columns depending on edit mode state
    edit_mode_active = st.session_state.get("edit_mode", False)
    if edit_mode_active:
        edit_col1, edit_col2, edit_col3, edit_col5 = st.columns([1.2, 1.2, 1, 1])
    else:
        edit_col1, edit_col3, edit_col5 = st.columns([1.2, 1, 1])
        edit_col2 = None

    edit_mode = edit_col1.toggle(
        "✏️ Edit Mode", key="edit_mode", on_change=sync_and_save_on_toggle
    )

    # If Edit Mode is active, show the Save Changes button
    if edit_mode and edit_col2:
        if edit_col2.button(
            "💾 Save Changes", use_container_width=True, type="primary"
        ):
            trigger_sync()
            st.session_state.last_saved_char = get_character_dict(st.session_state)
            st.session_state.needs_validation = True
            st.toast("⚡ Changes saved to vault!")
            st.rerun()

    if edit_col3.button("🔼 Level Up", use_container_width=True):
        run_level_up_wizard()

    if edit_col5.button("⚖️ Validate", use_container_width=True):
        with st.spinner("Checking build against the rules..."):
            char_data = get_character_dict(st.session_state)
            val_result = validate_character_build(char_data)
            if val_result:
                st.session_state.validation_result = val_result
                st.session_state.needs_validation = False
            else:
                st.error("Validation failed to complete.")
        st.rerun()

    if edit_mode_active:
        with st.expander("🖼️ Change Character Portrait", expanded=False):
            st.write(
                "Upload a custom image or enter an image URL to update your character's portrait."
            )
            col_url, col_upload = st.columns([2, 3])

            # 1. URL input
            input_url = col_url.text_input(
                "Portrait Image URL",
                value=st.session_state.char_portrait or "",
                key="portrait_url_input",
            )

            # 2. Upload file
            uploaded_file = col_upload.file_uploader(
                "Upload Image File",
                type=["png", "jpg", "jpeg", "webp"],
                key="portrait_file_uploader",
            )

            if st.button("Apply Portrait Update", use_container_width=True):
                updated = False
                if uploaded_file:
                    import uuid

                    file_ext = uploaded_file.name.split(".")[-1]
                    char_id = st.session_state.char_id or str(uuid.uuid4())[:8]
                    filename = f"{char_id}_custom.{file_ext}"
                    local_path = save_custom_portrait(
                        uploaded_file.getbuffer(), filename
                    )
                    st.session_state.char_portrait = local_path
                    updated = True
                elif input_url != st.session_state.char_portrait:
                    st.session_state.char_portrait = input_url
                    updated = True

                if updated:
                    trigger_sync()
                    new_char = get_character_dict(st.session_state)
                    save_character(new_char)
                    st.session_state.last_saved_char = new_char.copy()
                    st.success("Portrait updated successfully!")
                    st.rerun()

            st.markdown("---")
            if st.button("🔮 Generate Portrait with AI", use_container_width=True):
                with st.spinner("Generating character portrait with AI..."):
                    char_dict = get_character_dict(st.session_state)
                    new_portrait_path = generate_portrait_url(char_dict, force=True)
                    if new_portrait_path:
                        st.session_state.char_portrait = new_portrait_path
                        trigger_sync()
                        new_char = get_character_dict(st.session_state)
                        save_character(new_char)
                        st.session_state.last_saved_char = new_char.copy()
                        st.success("Portrait generated successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to generate portrait with AI.")

    if st.session_state.validation_result:
        val = st.session_state.validation_result
        if val.get("is_valid"):
            st.success("✅ **Character is Rules-Compliant!**")
        else:
            st.warning("⚠️ **Character may have rules violations.**")

        if val.get("issues"):
            with st.expander("🚨 Issues Found", expanded=True):
                for issue in val["issues"]:
                    st.write(f"- {issue}")
        if val.get("suggestions"):
            with st.expander("💡 Suggestions", expanded=True):
                for sug in val["suggestions"]:
                    st.write(f"- {sug}")

        corrections = val.get("corrections")
        if corrections:
            # Filter out corrections that are already identical to the current values to avoid listing them
            active_corrections = {}
            for k, v in corrections.items():
                if k == "stats" and isinstance(v, dict):
                    diff_stats = {}
                    for stat_k, stat_v in v.items():
                        if st.session_state.stats.get(stat_k) != stat_v:
                            diff_stats[stat_k] = stat_v
                    if diff_stats:
                        active_corrections["stats"] = diff_stats
                else:
                    current_val = getattr(st.session_state, k, None)
                    if current_val is None and k in st.session_state:
                        current_val = st.session_state[k]
                    if current_val != v:
                        active_corrections[k] = v

            if active_corrections:
                with st.expander("🔧 Suggested Auto-Corrections", expanded=True):
                    st.markdown(
                        "The following corrections can be applied automatically to align your character sheet with the rules:"
                    )
                    for k, v in active_corrections.items():
                        if k == "stats" and isinstance(v, dict):
                            for stat_k, stat_v in v.items():
                                current_stat = st.session_state.stats.get(stat_k, "?")
                                st.write(
                                    f"- **Ability Score ({stat_k})**: `{current_stat}` ➡️ `{stat_v}`"
                                )
                        elif k in [
                            "features_traits",
                            "advancements",
                            "prepared_spells",
                            "weapons",
                            "equipment",
                            "spells",
                        ]:
                            st.write(
                                f"- **{k.replace('_', ' ').title()}**: Will be updated with rules-compliant entries."
                            )
                        elif k == "playstyle_guide":
                            st.write(
                                "- **Playstyle Guide**: Will be regenerated and updated to match current character level."
                            )
                        else:
                            current_val = getattr(st.session_state, k, None)
                            if current_val is None and k in st.session_state:
                                current_val = st.session_state[k]
                            st.write(
                                f"- **{k.replace('_', ' ').title()}**: `{current_val}` ➡️ `{v}`"
                            )

                    if st.button(
                        "🔧 Apply Auto-Corrections",
                        type="primary",
                        use_container_width=True,
                    ):
                        for k, v in active_corrections.items():
                            if k == "stats" and isinstance(v, dict):
                                current_stats = st.session_state.stats
                                if isinstance(current_stats, dict):
                                    current_stats.update(v)
                                else:
                                    for stat_k, stat_v in v.items():
                                        setattr(current_stats, stat_k, stat_v)

                                # Also update the widget temp keys for the ability scores
                                for stat_k, stat_v in v.items():
                                    try:
                                        st.session_state[f"stat_val_{stat_k}"] = stat_v
                                    except Exception:
                                        logger.error(
                                            f"Could not set session state for stat {stat_k}"
                                        )
                            else:
                                _set_val(st.session_state, k, v)

                        trigger_sync()
                        updated_char = get_character_dict(st.session_state)
                        from backend.core.storage import save_character as save_to_disk

                        save_to_disk(updated_char)
                        st.session_state.last_saved_char = updated_char.copy()
                        st.session_state.validation_result = None
                        st.toast("✅ All corrections applied and character saved!")
                        st.rerun()

        if st.button("Dismiss Validation"):
            st.session_state.validation_result = None
            st.rerun()

    char_tab1, char_tab2, char_tab3, char_tab4, char_tab5, char_tab6 = st.tabs(
        [
            "📊 Core Stats & Skills",
            "⚔️ Combat & Inventory",
            "🧙 Features & Spells",
            "📖 Playstyle Guide",
            "🎭 Roleplay",
            "📜 Campaign Chronicle",
        ]
    )

    with char_tab1:
        _render_core_stats(edit_mode)

    with char_tab2:
        _render_combat_inventory(edit_mode)

    with char_tab3:
        _render_features_spells(edit_mode)

    with char_tab4:
        _render_playstyle_guide(edit_mode)

    with char_tab5:
        _render_roleplay(edit_mode)

    with char_tab6:
        _render_campaign_chronicle()
