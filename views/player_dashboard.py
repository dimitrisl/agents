import streamlit as st
import logging

import uuid
import os
from backend.services.forge_service import (
    forge_character,
    generate_playstyle_guide,
    analyze_level_up,
)
from backend.services.rules_service import (
    validate_character_build,
    parse_character_from_text,
    analyze_feat,
)
from backend.core.storage import (
    save_character,
    load_character,
    list_characters,
    delete_character,
)
from backend.core.state_manager import (
    get_character_dict,
    update_session_from_dict,
    _set_val,
)
from backend.services.mechanics_service import (
    get_modifier as calculate_modifier,
    get_level_up_vitals,
    check_progression_features,
)
from backend.utils.pdf_exporter import export_character_to_pdf
from backend.utils.ui_utils import render_character_header, render_active_roll_visual
from backend.utils.image_utils import generate_portrait_url
from backend.core.constants import (
    EDITION_2014,
    EDITION_2024,
    RACES_2014,
    CLASSES_2014,
    BACKGROUNDS_2014,
    SUBCLASSES_2014,
    SPECIES_2024,
    CLASSES_2024,
    BACKGROUNDS_2024,
    SUBCLASSES_2024,
    GENDERS,
    ALIGNMENTS,
)

logger = logging.getLogger(__name__)


def safe_int(val, default=0):
    try:
        if val is None:
            return default
        import math

        if isinstance(val, float) and math.isnan(val):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def log_roll(message: str):
    """Helper to log rolls to the session state history."""
    if "roll_history" not in st.session_state:
        st.session_state.roll_history = []
    st.session_state.roll_history.insert(0, message)
    if len(st.session_state.roll_history) > 20:
        st.session_state.roll_history = st.session_state.roll_history[:20]
    st.toast(message)


@st.cache_data
def get_item_effect(name: str) -> str:
    """Detects what a specific item does for the UI display using the KB."""
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _rules_repo.get_all_items()

    n = name.lower()
    item_data = next((i for i in all_items if i["name"].lower() == n), None)

    if not item_data:
        return "-"

    effects = []
    if "ac_base" in item_data:
        limit = item_data.get("dex_limit", 10)
        dex_str = f" + DEX (max {limit})" if limit < 10 else " + DEX"
        if limit == 0:
            dex_str = " (No DEX)"
        effects.append(f"Base AC {item_data['ac_base']}{dex_str}")
    if "ac_bonus" in item_data:
        effects.append(f"+{item_data['ac_bonus']} AC")
    if "stat_set" in item_data:
        for s, v in item_data["stat_set"].items():
            effects.append(f"{s} becomes {v}")
    if "stat_bonus" in item_data:
        for s, v in item_data["stat_bonus"].items():
            effects.append(f"+{v} {s}")

    return ", ".join(effects) if effects else "-"


def render_player_dashboard(accent_color: str):
    """Renders the main Player Dashboard view."""
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
                template_path = "5E_CharacterSheet_Fillable.pdf"
                pdf_bytes = export_character_to_pdf(char_dict, template_path)
                if pdf_bytes:
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_bytes,
                        file_name=f"{char_dict['char_name']}_Sheet.pdf",
                        mime="application/pdf",
                        width="stretch",
                    )
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
            if st.button("🔄 Exit Hero", width="stretch"):
                # Clear critical session state before exiting
                from backend.core.state_manager import init_session_state

                st.session_state.character_active = False
                init_session_state(st.session_state, force=True)  # Reset to defaults
                st.rerun()

        if st.session_state.player_view == "sheet":
            # --- Sidebar Global Actions ---
            with st.sidebar:
                st.markdown("### ⚙️ Hero Controls")
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
                        from backend.core.storage import save_character as save_to_disk

                        char_data = get_character_dict(st.session_state)
                        save_to_disk(char_data)
                        st.success("Character Saved!")
                    else:
                        st.warning("⚠️ Please name your character before saving.")
                st.markdown("---")

            # --- Main Content ---
            render_active_character(accent_color)
        else:
            render_character_creator()


def render_selection_screen():
    """Renders a high-aesthetics landing page for character selection or creation."""
    st.title("Welcome, Adventurer")
    st.markdown("### Choose your path to begin your journey.")
    st.markdown("---")

    col_load, col_forge = st.columns(2)

    with col_load:
        st.subheader("🛡️ Equip a Hero")
        st.write("Load one of your previously saved characters from the vault.")
        saved_chars = list_characters()
        if saved_chars:
            active_edition = st.session_state.get("dnd_edition", "2014 Edition")
            is_active_2024 = "2024" in active_edition

            filtered_chars = []
            for char_file in saved_chars:
                char_data = load_character(char_file)
                if char_data:
                    char_ed = char_data.get("dnd_edition", "2014 Edition")
                    is_char_2024 = "2024" in char_ed
                    if is_active_2024 == is_char_2024:
                        filtered_chars.append((char_file, char_data))

            if filtered_chars:
                for char_file, char_data in filtered_chars:
                    # Extract full name from filename (format: name_with_underscores_uuid.json)
                    name_parts = char_file.replace(".json", "").split("_")
                    display_name = " ".join(name_parts[:-1]).title()

                    c_col1, c_col2 = st.columns([4, 1])
                    edition = char_data.get("dnd_edition", "2014 Edition")
                    edition_tag = f" ({'2024' if '2024' in edition else '2014'})"

                    if c_col1.button(
                        f"🛡️ {display_name}{edition_tag}",
                        width="stretch",
                        key=f"load_{char_file}",
                    ):
                        update_session_from_dict(st.session_state, char_data)
                        trigger_sync()
                        st.session_state.character_active = True
                        st.session_state.player_view = "sheet"
                        st.session_state.last_saved_char = get_character_dict(
                            st.session_state
                        )
                        st.rerun()

                    # Delete button with double-click confirmation pattern
                    delete_key = f"confirm_delete_{char_file}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False

                    if not st.session_state[delete_key]:
                        if c_col2.button(
                            "🗑️",
                            help=f"Delete {display_name}",
                            key=f"del_{char_file}",
                            width="stretch",
                        ):
                            st.session_state[delete_key] = True
                            st.rerun()
                    else:
                        if c_col2.button(
                            "⚠️ OK?",
                            help="Confirm Delete",
                            key=f"conf_{char_file}",
                            width="stretch",
                            type="primary",
                        ):
                            if delete_character(char_file):
                                st.toast(f"Deleted {display_name}")
                                del st.session_state[delete_key]
                                st.rerun()
                        if st.button("Cancel", key=f"can_{char_file}"):
                            st.session_state[delete_key] = False
                            st.rerun()
            else:
                st.info(
                    f"No saved heroes found for the {'2024 Revision' if is_active_2024 else '2014 Edition'}."
                )
        else:
            st.info("No saved heroes found in the vault.")

    with col_forge:
        st.subheader("✨ Forge a New Hero")
        st.write("Let AI assist you in creating a brand new legendary character.")
        if st.button("Go to Character Forge", width="stretch"):
            from backend.core.state_manager import init_session_state

            # Force a reset to default values (New Hero)
            init_session_state(st.session_state, force=True)
            st.session_state.character_active = True
            st.session_state.player_view = "forge"
            st.rerun()

        st.markdown("---")
        st.subheader("📄 Import from PDF")
        st.write("Upload an existing D&D Character Sheet (PDF).")

        # Edition selection for import
        import_edition = st.selectbox(
            "Character Ruleset Edition",
            ["2014 Edition", "2024 Revision (5.5e)"],
            index=0 if "2014" in st.session_state.dnd_edition else 1,
            key="pdf_import_edition",
        )

        uploaded_pdf = st.file_uploader(
            "Upload PDF", type=["pdf"], label_visibility="collapsed"
        )

        if uploaded_pdf is not None:
            if st.button("🧠 Parse with AI", type="primary", width="stretch"):
                with st.spinner(
                    f"Extracting and parsing {import_edition} character data..."
                ):
                    try:
                        from backend.utils.pdf_importer import (
                            extract_text_and_fields_from_pdf,
                        )

                        extracted_text = extract_text_and_fields_from_pdf(uploaded_pdf)

                        if not extracted_text.strip():
                            st.error(
                                "Could not extract any text or fields from the PDF. It might be an image-only PDF."
                            )
                        else:
                            parsed_data = parse_character_from_text(
                                extracted_text, edition=import_edition
                            )
                            if parsed_data:
                                # Ensure we have a unique ID and save the portrait
                                parsed_data["char_id"] = str(uuid.uuid4())[:8]
                                parsed_data["dnd_edition"] = import_edition

                                # Generate and save portrait locally based on parsed data
                                local_portrait_path = generate_portrait_url(parsed_data)
                                if local_portrait_path:
                                    parsed_data["char_portrait"] = local_portrait_path

                                from backend.services.mechanics_service import (
                                    sync_character_stats,
                                )
                                from backend.repositories.rules_repository import (
                                    RulesRepository,
                                )

                                _rules_repo = RulesRepository()
                                class_data = _rules_repo.get_class_progression(
                                    parsed_data.get("char_class"), import_edition
                                )
                                parsed_data = sync_character_stats(
                                    parsed_data, class_data
                                )

                                update_session_from_dict(st.session_state, parsed_data)
                                st.session_state.character_active = True
                                st.session_state.player_view = "sheet"
                                saved_dict = get_character_dict(st.session_state)
                                save_character(saved_dict)
                                st.session_state.last_saved_char = saved_dict.copy()
                                st.toast("Character imported successfully!")
                                st.rerun()
                            else:
                                st.error(
                                    "AI failed to parse the character data correctly."
                                )
                    except Exception as e:
                        st.error(f"Error reading PDF: {e}")


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
                    if v != st.session_state.last_saved_char.get(k):
                        state_changes = True
                        break
            else:
                state_changes = True

            if editor_changes or state_changes:
                trigger_sync()
                new_char = get_character_dict(st.session_state)
                save_character(new_char)
                st.session_state.last_saved_char = new_char.copy()
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
            new_char = get_character_dict(st.session_state)
            save_character(new_char)
            st.session_state.last_saved_char = new_char.copy()
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

    char_tab1, char_tab2, char_tab3, char_tab4, char_tab5 = st.tabs(
        [
            "📊 Core Stats & Skills",
            "⚔️ Combat & Inventory",
            "🧙 Features & Spells",
            "📖 Playstyle Guide",
            "🎭 Roleplay",
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


def trigger_sync():
    """Forces a synchronization of derived stats using the backend service."""
    from backend.services.forge_service import process_character_update

    # 1. Collect Stat Updates & Level
    stat_updates = {}
    for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        temp_key = f"stat_val_{k}"
        if temp_key in st.session_state:
            stat_updates[k] = st.session_state[temp_key]

    # Explicitly catch the level from the widget key
    if "char_level" in st.session_state:
        stat_updates["char_level"] = st.session_state.char_level

    # 2. Collect Equipment Deltas
    equipment_deltas = st.session_state.get("edit_equip_table", {})
    weapon_deltas = st.session_state.get("edit_weapons", {})

    # 3. Call Backend Service
    current_char = get_character_dict(st.session_state)

    # Safety Check: Don't sync if basic info is missing (prevents accidental resets)
    if not current_char.get("char_name") or current_char.get("char_name") == "New Hero":
        # Check if we have it in session state keys directly as a fallback
        alt_name = st.session_state.get("char_name")
        if alt_name and alt_name != "New Hero":
            current_char["char_name"] = alt_name
        else:
            st.error(
                "⚠️ Cannot sync: Character name is missing. Please ensure your character is loaded correctly."
            )
            return

    updated = process_character_update(
        current_char, stat_updates, equipment_deltas, weapon_deltas
    )

    # 4. Update UI State
    update_session_from_dict(st.session_state, updated)

    # Invalidate editor dataframes to force recreation
    if "equip_df_editor" in st.session_state:
        del st.session_state["equip_df_editor"]
    if "weapons_df_editor" in st.session_state:
        del st.session_state["weapons_df_editor"]

    # Update widget temp keys from the fresh data
    for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        try:
            st.session_state[f"stat_val_{k}"] = st.session_state.stats[k]
        except Exception:
            logger.error(f"Could not set session state for stat {k}")

    # Save to database immediately to prevent data loss on subsequent UI interactions
    save_character(get_character_dict(st.session_state))

    # 5. CLEAR the editor state
    if "edit_equip_table" in st.session_state:
        del st.session_state["edit_equip_table"]
    if "edit_weapons" in st.session_state:
        del st.session_state["edit_weapons"]


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


def _render_core_stats(edit_mode: bool):
    """Renders ability scores, core attributes, and skills."""
    if edit_mode:
        c_n, c_c, c_l, c_r = st.columns(4)
        st.session_state.char_name = c_n.text_input(
            "Name", value=st.session_state.char_name, disabled=True
        )
        st.session_state.char_class = c_c.text_input(
            "Class", value=st.session_state.char_class, disabled=True
        )
        st.session_state.subclass = c_c.text_input(
            "Subclass", value=st.session_state.subclass or "", disabled=True
        )
        st.session_state.char_level = c_l.number_input(
            "Level", 1, 20, value=st.session_state.char_level, disabled=True
        )
        st.session_state.race = c_r.text_input(
            "Race", value=st.session_state.race, disabled=True
        )

        c_b, c_a, c_hp, c_ac = st.columns(4)
        st.session_state.background = c_b.text_input(
            "Background", value=st.session_state.background, disabled=True
        )
        st.session_state.alignment = c_a.text_input(
            "Alignment", value=st.session_state.alignment
        )
        c_hp.number_input(
            "Max HP (Derived)", 1, 500, value=st.session_state.hp_max, disabled=True
        )
        c_ac.number_input(
            "Armor Class (Derived)",
            1,
            50,
            value=st.session_state.armor_class,
            disabled=True,
        )

        c_hd, c_pass = st.columns(2)
        c_hd.text_input(
            "Hit Dice (Derived)", value=st.session_state.hit_dice or "", disabled=True
        )
        c_pass.number_input(
            "Passive Perception (Derived)",
            0,
            30,
            value=st.session_state.passive_perception,
            disabled=True,
        )

        st.markdown("#### Ability Scores")
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        def stat_input(col, label, key):
            current_val = st.session_state.stats.get(key, 10)
            col.number_input(
                label,
                min_value=1,
                max_value=30,
                value=int(current_val),
                key=f"stat_val_{key}",
            )

        # Ensure temp keys exist
        for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            if f"stat_val_{k}" not in st.session_state:
                st.session_state[f"stat_val_{k}"] = st.session_state.stats[k]

        stat_input(c1, "STR", "STR")
        stat_input(c2, "DEX", "DEX")
        stat_input(c3, "CON", "CON")
        stat_input(c4, "INT", "INT")
        stat_input(c5, "WIS", "WIS")
        stat_input(c6, "CHA", "CHA")

        st.markdown("#### Skills & Proficiencies")

        # Create a list of all 18 standard skills
        standard_skills = [
            "Acrobatics",
            "Animal Handling",
            "Arcana",
            "Athletics",
            "Deception",
            "History",
            "Insight",
            "Intimidation",
            "Investigation",
            "Medicine",
            "Nature",
            "Perception",
            "Performance",
            "Persuasion",
            "Religion",
            "Sleight of Hand",
            "Stealth",
            "Survival",
        ]

        import pandas as pd

        # Build a DataFrame for the editor
        skill_data = []
        for sk in standard_skills:
            skill_data.append(
                {
                    "Skill": sk,
                    "Bonus": st.session_state.skills.get(sk, 0),
                    "Proficient": sk in st.session_state.skill_proficiencies,
                    "Expert": sk in getattr(st.session_state, "skill_expertise", []),
                }
            )

        df_skills = pd.DataFrame(skill_data)

        edited_df = st.data_editor(
            df_skills,
            column_config={
                "Proficient": st.column_config.CheckboxColumn("P", help="Proficient?"),
                "Expert": st.column_config.CheckboxColumn("E", help="Expertise?"),
                "Bonus": st.column_config.NumberColumn(
                    "Bonus", disabled=True, help="Automatically calculated"
                ),
            },
            disabled=["Skill"],
            hide_index=True,
            use_container_width=True,
            key="skill_data_editor",
        )

        # Sync back to session state
        if st.session_state.get("skill_data_editor"):
            new_skills = {}
            new_profs = []
            new_exps = []
            for _, row in edited_df.iterrows():
                new_skills[row["Skill"]] = row["Bonus"]
                if row["Proficient"]:
                    new_profs.append(row["Skill"])
                if row["Expert"]:
                    new_exps.append(row["Skill"])

            st.session_state.skills = new_skills
            st.session_state.skill_proficiencies = new_profs
            st.session_state.skill_expertise = new_exps

        st.session_state.saving_throws = st.multiselect(
            "Saving Throw Proficiencies",
            options=["STR", "DEX", "CON", "INT", "WIS", "CHA"],
            default=st.session_state.saving_throws,
        )
    else:
        # --- COMBAT & STATUS ---
        st.markdown("### ⚔️ Combat & Status")
        col_hp, col_cond, col_rest = st.columns([1.5, 2, 1])

        with col_hp:
            hp_curr = st.session_state.get("hp_current")
            if hp_curr is None:
                hp_curr = st.session_state.hp_max
                st.session_state.hp_current = hp_curr

            st.markdown(f"**HP:** `{hp_curr}` / `{st.session_state.hp_max}`")
            hp_bar_pct = max(0.0, min(1.0, hp_curr / max(1, st.session_state.hp_max)))
            st.progress(hp_bar_pct)

            hc1, hc2 = st.columns([1, 1])
            with hc1:
                dmg = st.number_input(
                    "Damage", min_value=0, value=0, step=1, key="dmg_val"
                )
                if (
                    st.button("🩸 Apply Dmg", key="apply_dmg", use_container_width=True)
                    and dmg > 0
                ):
                    st.session_state.hp_current = max(0, hp_curr - dmg)
                    save_character(get_character_dict(st.session_state))
                    st.rerun()
            with hc2:
                heal = st.number_input(
                    "Heal", min_value=0, value=0, step=1, key="heal_val"
                )
                if (
                    st.button(
                        "💚 Apply Heal", key="apply_heal", use_container_width=True
                    )
                    and heal > 0
                ):
                    st.session_state.hp_current = min(
                        st.session_state.hp_max, hp_curr + heal
                    )
                    save_character(get_character_dict(st.session_state))
                    st.rerun()

        with col_cond:
            curr_cond = st.session_state.get("conditions", [])
            new_cond = st.multiselect(
                "Active Conditions",
                options=[
                    "Blinded",
                    "Charmed",
                    "Deafened",
                    "Frightened",
                    "Grappled",
                    "Incapacitated",
                    "Invisible",
                    "Paralyzed",
                    "Petrified",
                    "Poisoned",
                    "Prone",
                    "Restrained",
                    "Stunned",
                    "Unconscious",
                    "Exhaustion",
                ],
                default=curr_cond,
                key="player_conditions",
            )
            if new_cond != curr_cond:
                st.session_state.conditions = new_cond
                save_character(get_character_dict(st.session_state))
                st.rerun()

        with col_rest:
            st.markdown("**Camp & Rest**")
            if st.button("🔥 Long Rest", type="primary", use_container_width=True):
                st.session_state.hp_current = st.session_state.hp_max
                st.session_state.hit_dice_used = max(
                    0,
                    st.session_state.get("hit_dice_used", 0)
                    - max(1, st.session_state.char_level // 2),
                )
                slots = st.session_state.get("spell_slots", {})
                for lvl, data in slots.items():
                    data["used"] = 0
                st.session_state.spell_slots = slots
                save_character(get_character_dict(st.session_state))
                st.toast("Long Rest completed! HP and Spell Slots restored.")
                st.rerun()

        st.markdown("---")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Max HP", st.session_state.hp_max)
        c2.metric("Armor Class", st.session_state.armor_class)
        init_mod = st.session_state.get("initiative_modifier") or 0
        c3.metric("Initiative", f"{'+' if init_mod >= 0 else ''}{init_mod}")
        c4.metric("Speed", f"{st.session_state.speed} ft")
        c5.metric("Proficiency", f"+{st.session_state.proficiency_bonus}")

        st.markdown("#### Ability Scores")
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        def render_score(label, score):
            mod = calculate_modifier(score)
            mod_str = f"+{mod}" if mod >= 0 else f"{mod}"
            st.markdown(
                f"""
                <div class="score-box">
                    <div class="score-label">{label}</div>
                    <div class="score-mod">{mod_str}</div>
                    <div class="score-value">{score}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )
            # Add the roll button below the visual box
            if st.button("🎲 Roll", key=f"p_roll_{label}"):
                from backend.utils.dice import quick_roll

                res, raw = quick_roll(20, mod)
                log_roll(f"**{label}** Check: **{res}** (d20: {raw}, Mod: {mod_str})")
                st.session_state.active_roll = {
                    "label": f"{label} Check",
                    "sides": 20,
                    "raw": raw,
                    "modifier": mod,
                    "total": res,
                    "adv_type": "None",
                }
                st.rerun()

        with c1:
            render_score("STR", st.session_state.stats["STR"])
        with c2:
            render_score("DEX", st.session_state.stats["DEX"])
        with c3:
            render_score("CON", st.session_state.stats["CON"])
        with c4:
            render_score("INT", st.session_state.stats["INT"])
        with c5:
            render_score("WIS", st.session_state.stats["WIS"])
        with c6:
            render_score("CHA", st.session_state.stats["CHA"])

        st.markdown("<br>", unsafe_allow_html=True)
        # Add a global Custom Roll for players too
        with st.popover("🎲 Custom / Damage Roll", width="stretch"):
            st.markdown("### Custom Roll")

            # Extract relevant dice for this character
            relevant_dice = {20}  # Always include d20

            # 1. Hit Die
            try:
                hd_size = int(st.session_state.hit_dice.lower().split("d")[-1])
                relevant_dice.add(hd_size)
            except Exception:
                pass

            # 2. Weapon Dice
            import re

            from backend.services.mechanics_service import rebuild_damage_formula

            for w in st.session_state.weapons:
                dmg = str(
                    w.get("damage")
                    or rebuild_damage_formula(
                        w.get("damage_dice"), w.get("damage_bonus")
                    )
                )
                found = re.findall(r"d(\d+)", dmg)
                for d in found:
                    relevant_dice.add(int(d))

            # 3. Spell Dice (Quick scan of descriptions/names)
            # This is a bit more complex but we can scan the spells
            for lvl_spells in st.session_state.spells.values():
                for s in lvl_spells:
                    found = re.findall(r"d(\d+)", s)
                    for d in found:
                        relevant_dice.add(int(d))

            # Sort and format for display
            dice_options = sorted(list(relevant_dice), reverse=True)
            if not any(d in dice_options for d in [12, 10, 8, 6, 4]):
                # Fallback if character is empty/new
                dice_options = [20, 12, 10, 8, 6, 4]

            pd_c1, pd_c2, pd_c3, pd_c4 = st.columns([1, 1, 1, 1])
            p_dtype = pd_c1.selectbox("Dice", dice_options, index=0)

            # Ability Modifier Picker
            abilities = ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
            p_ability = pd_c2.selectbox("Ability", abilities, index=0)

            # Skill Modifier Picker
            skill_list = ["None"] + sorted(
                list(st.session_state.get("skills", {}).keys())
            )
            p_skill = pd_c3.selectbox("Skill", skill_list, index=0)

            p_extra = pd_c4.number_input("Bonus", value=0)
            st.caption(
                "Note: Skill bonuses usually include their relevant ability modifier."
            )

            p_adv = st.radio(
                "Advantage?",
                ["None", "Advantage", "Disadvantage"],
                horizontal=True,
                key="custom_roll_adv",
            )

            if st.button(
                "Roll!", type="primary", width="stretch", key="custom_roll_btn"
            ):
                from backend.utils.dice import quick_roll

                # Calculate total modifier
                total_mod = p_extra
                mod_parts = []
                if p_extra != 0:
                    mod_parts.append(f"{p_extra}")

                if p_ability != "None":
                    a_mod = calculate_modifier(st.session_state.stats[p_ability])
                    total_mod += a_mod
                    mod_parts.append(f"{p_ability}({'+' if a_mod >= 0 else ''}{a_mod})")

                if p_skill != "None":
                    s_mod = st.session_state.skills[p_skill]
                    total_mod += s_mod
                    mod_parts.append(f"{p_skill}({'+' if s_mod >= 0 else ''}{s_mod})")

                mod_desc = " + ".join(mod_parts) if mod_parts else "0"

                if p_adv == "None":
                    res, raw = quick_roll(p_dtype, total_mod)
                    msg = f"**Custom Roll ({p_dtype})**: **{res}** (raw: {raw} + {mod_desc})"
                    log_roll(msg)
                    st.session_state.active_roll = {
                        "label": f"Custom Roll (d{p_dtype})",
                        "sides": p_dtype,
                        "raw": raw,
                        "modifier": total_mod,
                        "total": res,
                        "adv_type": "None",
                    }
                    st.rerun()
                else:
                    r1, raw1 = quick_roll(p_dtype, total_mod)
                    r2, raw2 = quick_roll(p_dtype, total_mod)
                    final = max(r1, r2) if p_adv == "Advantage" else min(r1, r2)
                    msg = f"**{p_adv} ({p_dtype})**: **{final}** (Rolls: {r1}, {r2} | Mod: {mod_desc})"
                    log_roll(msg)
                    st.session_state.active_roll = {
                        "label": f"Custom Roll with {p_adv}",
                        "sides": p_dtype,
                        "raw": [raw1, raw2],
                        "raw_selected": raw1
                        if (p_adv == "Advantage" and raw1 >= raw2)
                        or (p_adv == "Disadvantage" and raw1 <= raw2)
                        else raw2,
                        "modifier": total_mod,
                        "total": final,
                        "adv_type": p_adv,
                    }
                    st.rerun()

        col_sk, col_sv = st.columns(2)
        with col_sk:
            st.markdown("#### Skills")
            skills = st.session_state.get("skills", {})
            if skills is None:
                skills = {}
            for k, v in skills.items():
                indicator = ""
                if k in st.session_state.skill_proficiencies:
                    indicator = "● "
                if k in getattr(st.session_state, "skill_expertise", []):
                    indicator = "★ "

                sc1, sc2 = st.columns([4, 1])
                sc1.write(f"{indicator}**{k}:** {v}")
                if sc2.button("🎲", key=f"roll_skill_{k}"):
                    from backend.utils.dice import quick_roll

                    res, raw = quick_roll(20, v)
                    log_roll(f"**{k}** Check: **{res}** (d20: {raw} + {v})")
                    st.session_state.active_roll = {
                        "label": f"{k} Check",
                        "sides": 20,
                        "raw": raw,
                        "modifier": v,
                        "total": res,
                        "adv_type": "None",
                    }
                    st.rerun()
        with col_sv:
            st.markdown("#### Saving Throws")
            saves = st.session_state.get("saving_throw_values", {})
            if saves is None:
                saves = {}
            for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                prof = stat in st.session_state.saving_throws
                indicator = "● " if prof else "○ "

                total_sv = saves.get(
                    stat, calculate_modifier(st.session_state.stats[stat])
                )

                svc1, svc2 = st.columns([4, 1])
                svc1.write(f"{indicator}**{stat}:** {total_sv}")
                if svc2.button("🎲", key=f"roll_sv_{stat}"):
                    from backend.utils.dice import quick_roll

                    res, raw = quick_roll(20, total_sv)
                    log_roll(
                        f"**{stat}** Saving Throw: **{res}** (d20: {raw} + {total_sv})"
                    )
                    st.session_state.active_roll = {
                        "label": f"{stat} Saving Throw",
                        "sides": 20,
                        "raw": raw,
                        "modifier": total_sv,
                        "total": res,
                        "adv_type": "None",
                    }
                    st.rerun()

    st.markdown("---")
    st.markdown("#### ✨ Heroic Advancements (Feats & ASI)")
    if edit_mode:
        edited_adv_df = st.data_editor(
            st.session_state.advancements,
            num_rows="dynamic",
            key="edit_advancements",
            column_config={
                "level": st.column_config.NumberColumn(
                    "Level", min_value=1, max_value=20
                ),
                "type": st.column_config.SelectboxColumn(
                    "Type", options=["Feat", "Origin Feat", "ASI"]
                ),
                "name": st.column_config.TextColumn("Name / Details"),
                "description": st.column_config.TextColumn("Description"),
            },
        )
        if edited_adv_df is not None:
            new_advancements = []
            import pandas as pd

            rows = (
                edited_adv_df.iterrows()
                if isinstance(edited_adv_df, pd.DataFrame)
                else enumerate(edited_adv_df)
            )
            for _, row in rows:
                new_advancements.append(
                    {
                        "level": safe_int(row.get("level"), 1),
                        "type": row.get("type") or "Feat",
                        "name": row.get("name") or "New Advancement",
                        "description": row.get("description") or "",
                    }
                )
            st.session_state.advancements = new_advancements
    else:
        if not st.session_state.advancements:
            st.write("No advancements recorded.")
        else:
            for adv in st.session_state.advancements:
                st.write(
                    f"🔹 **Lv.{adv.get('level', '?')} {adv.get('type', '')}:** {adv.get('name', '')} — *{adv.get('description', '')}*"
                )


def _render_combat_inventory(edit_mode: bool):
    """Renders weapons and equipment sections."""
    st.markdown("#### Weapons")
    if edit_mode:
        import pandas as pd

        if "weapons_df_editor" not in st.session_state:
            st.session_state.weapons_df_editor = pd.DataFrame(st.session_state.weapons)

        st.data_editor(
            st.session_state.weapons_df_editor,
            num_rows="dynamic",
            key="edit_weapons",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Weapon Name", width="large"),
                "magic_bonus": st.column_config.NumberColumn(
                    "+X",
                    width="small",
                    help="Magic bonus (e.g. +1, +2)",
                    step=1,
                    min_value=0,
                    max_value=100,
                ),
                "attack_bonus": st.column_config.TextColumn(
                    "To Hit", width="small", help="Attack bonus e.g. +5, -1"
                ),
                "damage_dice": st.column_config.TextColumn(
                    "Damage Dice", width="medium", help="Damage dice e.g. 1d8 slashing"
                ),
                "damage_bonus": st.column_config.TextColumn(
                    "Dmg Bonus", width="small", help="Damage bonus e.g. +3, -1"
                ),
                "is_custom": st.column_config.CheckboxColumn(
                    "Custom",
                    width="small",
                    help="Lock manual To Hit & Damage, skip auto-sync",
                ),
                "properties": st.column_config.TextColumn(
                    "Properties",
                    width="medium",
                    help="Properties (e.g., Finesse, Light, Versatile)",
                ),
            },
        )
        w_add_btn, w_add_qty = st.columns([5, 1])
        with w_add_qty:
            qty = st.number_input(
                "Qty", 1, 10, 1, key="add_weapon_qty", label_visibility="collapsed"
            )
        with w_add_btn:
            if st.button("➕ Add New Weapon(s)", use_container_width=True):
                trigger_sync()
                for _ in range(qty):
                    st.session_state.weapons.append(
                        {
                            "name": "New Weapon",
                            "magic_bonus": 0,
                            "attack_bonus": "+0",
                            "damage_dice": "1d4",
                            "damage_bonus": "+0",
                            "properties": "",
                            "range": "",
                            "is_custom": False,
                        }
                    )
                if "weapons_df_editor" in st.session_state:
                    del st.session_state["weapons_df_editor"]
                st.rerun()

        # Individual Removal Section
        if st.session_state.weapons:
            st.markdown("---")
            st.caption("🗑️ Weapon Removal")
            del_w_col, del_btn_col = st.columns([3, 1])
            w_options = [
                f"{i + 1}. {w.get('name', 'Unknown')}"
                for i, w in enumerate(st.session_state.weapons)
            ]
            selected_to_del = del_w_col.selectbox(
                "Select weapon to remove",
                options=w_options,
                label_visibility="collapsed",
                key="weapon_to_delete_select",
            )
            if del_btn_col.button(
                "🗑️ Remove Selected", use_container_width=True, type="secondary"
            ):
                idx = int(selected_to_del.split(".")[0]) - 1
                if 0 <= idx < len(st.session_state.weapons):
                    st.session_state.weapons.pop(idx)
                    if "weapons_df_editor" in st.session_state:
                        del st.session_state["weapons_df_editor"]
                    trigger_sync()
                    save_character(get_character_dict(st.session_state))
                    st.rerun()
    else:
        weapons = st.session_state.get("weapons", [])
        if weapons is None:
            weapons = []
        for i, w in enumerate(weapons):
            with st.container(border=True):
                # Row 1: weapon name
                w_name_col, w_roll1, w_roll2 = st.columns([3, 1, 1])
                w_name_col.markdown(f"🗡️ **{w.get('name', 'Unknown')}**")

                # Row 2: To Hit and Damage as separate labeled cells
                info_col1, info_col2, info_col3 = st.columns([1, 2, 1])
                info_col1.markdown(f"**To Hit**  \n`{w.get('attack_bonus', '+0')}`")
                info_col2.markdown(
                    f"**Damage Dice**  \n`{w.get('damage_dice', w.get('damage', '1d4'))}`"
                )
                info_col3.markdown(f"**Dmg Bonus**  \n`{w.get('damage_bonus', '+0')}`")

                # Show properties and range if present
                extra_info = []
                if w.get("properties"):
                    extra_info.append(f"**Properties:** {w.get('properties')}")
                if w.get("range"):
                    extra_info.append(f"**Range:** {w.get('range')}")
                if extra_info:
                    st.caption(" • ".join(extra_info))

                if w_roll1.button("🎯 To Hit", key=f"atk_{i}", width="stretch"):
                    from backend.utils.dice import quick_roll

                    atk_bonus_str = str(w.get("attack_bonus", "+0")).replace("+", "")
                    try:
                        atk_bonus = int(atk_bonus_str)
                    except (ValueError, TypeError):
                        atk_bonus = 0

                    global_atk = getattr(st.session_state, "global_attack_bonus", 0)
                    total_atk = atk_bonus + global_atk
                    res, raw = quick_roll(20, total_atk)

                    bonus_text = f"{atk_bonus}"
                    if global_atk:
                        bonus_text = f"{total_atk} ({atk_bonus} + {global_atk} Global)"

                    log_roll(
                        f"**{w.get('name')}** To Hit: **{res}** (d20: {raw} + {bonus_text})"
                    )
                    st.session_state.active_roll = {
                        "label": f"{w.get('name')} Attack Roll",
                        "sides": 20,
                        "raw": raw,
                        "modifier": total_atk,
                        "total": res,
                        "adv_type": "None",
                    }
                    if raw == 20:
                        st.balloons()
                    st.rerun()

                if w_roll2.button("💥 Dmg", key=f"dmg_{i}", width="stretch"):
                    from backend.utils.dice import roll_dice
                    import re
                    from backend.services.mechanics_service import (
                        rebuild_damage_formula,
                    )

                    dmg_str = w.get("damage") or rebuild_damage_formula(
                        w.get("damage_dice"), w.get("damage_bonus")
                    )
                    global_dmg = getattr(st.session_state, "global_damage_bonus", 0)
                    if global_dmg:
                        dmg_str = f"{dmg_str} + {global_dmg}"

                    res = roll_dice(dmg_str)
                    if "error" in res:
                        st.error(f"Error rolling damage: {res['error']}")
                    else:
                        log_roll(
                            f"**{w.get('name')}** Damage: **{res['total']}** ({res['result_text']})"
                        )
                        try:
                            sides = int(re.search(r"d(\d+)", dmg_str).group(1))
                        except Exception:
                            sides = 6

                        rolls = res.get("rolls", [1])
                        st.session_state.active_roll = {
                            "label": f"{w.get('name')} Damage",
                            "sides": sides,
                            "raw": rolls if len(rolls) > 1 else rolls[0],
                            "raw_selected": sum(rolls),
                            "modifier": res.get("modifier", 0),
                            "total": res.get("total", 1),
                            "adv_type": "None",
                        }
                        st.rerun()

    # 5.5e Weapon Masteries
    if st.session_state.dnd_edition == "2024 Revision (5.5e)":
        st.markdown("#### ⚔️ Weapon Masteries")
        if edit_mode:
            from backend.core.constants import WEAPON_MASTERIES_2024

            st.session_state.weapon_masteries = st.multiselect(
                "Mastered Properties:",
                options=WEAPON_MASTERIES_2024,
                default=st.session_state.weapon_masteries,
            )
        else:
            if st.session_state.weapon_masteries:
                cols = st.columns(len(st.session_state.weapon_masteries))
                for idx, mastery in enumerate(st.session_state.weapon_masteries):
                    with cols[idx]:
                        st.info(f"**{mastery}**")
            else:
                st.write("No weapon masteries unlocked.")

    st.markdown("#### Equipment")
    import pandas as pd
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _rules_repo.get_all_items()

    # Standardize equipment format (List of Dicts)
    current_equip = []
    attuned_count = 0
    equipment = st.session_state.get("equipment", [])
    if equipment is None:
        equipment = []
    for e in equipment:
        if isinstance(e, dict):
            item_name = e.get("name", "")
            item_data = next(
                (i for i in all_items if i["name"].lower() == item_name.lower()), None
            )

            display_ac = e.get("ac_bonus", 0)
            if display_ac == 0 and item_data:
                if "ac_base" in item_data:
                    display_ac = item_data["ac_base"]
                elif "ac_bonus" in item_data:
                    display_ac = item_data["ac_bonus"]

            item_dict = {
                "Item": item_name,
                "Equipped": e.get("equipped", False),
                "Attuned": e.get("attuned", False),
                "AC": display_ac,
                "Mod 1": e.get("mod1", "None"),
                "Val 1": e.get("val1", 0),
                "Mod 2": e.get("mod2", "None"),
                "Val 2": e.get("val2", 0),
            }
            current_equip.append(item_dict)
            if e.get("attuned", False):
                attuned_count += 1
        else:
            # Handle string/object fallbacks
            name = e if isinstance(e, str) else getattr(e, "name", "Unknown Item")
            current_equip.append(
                {
                    "Item": name,
                    "Equipped": False,
                    "Attuned": False,
                    "AC": 0,
                    "Mod 1": "None",
                    "Val 1": 0,
                    "Mod 2": "None",
                    "Val 2": 0,
                }
            )

    if edit_mode:
        # --- Inventory Header with Stats ---
        col_inv1, col_inv2 = st.columns([2, 2])
        att_color = "red" if attuned_count > 3 else "green"
        col_inv1.markdown(f"📊 **Attunement:** :{att_color}[{attuned_count} / 3]")
        col_inv2.markdown(f"🛡️ **Total AC:** {st.session_state.armor_class}")

        st.caption(
            "💡 **Tip:** Manually set bonuses (e.g., ATK, STR, HP) in the Mod/Val columns."
        )

        equip_df = pd.DataFrame(current_equip)
        if equip_df.empty:
            equip_df = pd.DataFrame(
                columns=["Item", "Equipped", "AC", "Mod 1", "Val 1", "Mod 2", "Val 2"]
            )

        attr_options = [
            "None",
            "STR",
            "DEX",
            "CON",
            "INT",
            "WIS",
            "CHA",
            "HP",
            "SPD",
            "INIT",
            "ATK",
            "DMG",
            "SAVES",
        ]

        if "equip_df_editor" not in st.session_state:
            st.session_state.equip_df_editor = equip_df

        st.data_editor(
            st.session_state.equip_df_editor,
            num_rows="dynamic",
            key="edit_equip_table",
            use_container_width=True,
            column_config={
                "Item": st.column_config.TextColumn("Item", width="large"),
                "Equipped": st.column_config.CheckboxColumn("Equipped", width="small"),
                "Attuned": st.column_config.CheckboxColumn("Attuned", width="small"),
                "AC": st.column_config.NumberColumn("AC", width="small"),
                "Mod 1": st.column_config.SelectboxColumn(
                    "Mod 1", options=attr_options, width="medium"
                ),
                "Val 1": st.column_config.NumberColumn("Val 1", width="small"),
                "Mod 2": st.column_config.SelectboxColumn(
                    "Mod 2", options=attr_options, width="medium"
                ),
                "Val 2": st.column_config.NumberColumn("Val 2", width="small"),
            },
        )
        e_add_btn, e_add_qty = st.columns([5, 1])
        with e_add_qty:
            qty = st.number_input(
                "Qty", 1, 10, 1, key="add_item_qty", label_visibility="collapsed"
            )
        with e_add_btn:
            if st.button("➕ Add New Item(s)", width="stretch"):
                # To add an item, we must trigger sync to save pending edits first,
                # then append the new item and rerun.
                trigger_sync()
                for _ in range(qty):
                    st.session_state.equipment.append(
                        {
                            "name": "New Item",
                            "equipped": False,
                            "attuned": False,
                            "ac_bonus": 0,
                            "mod1": "None",
                            "val1": 0,
                            "mod2": "None",
                            "val2": 0,
                        }
                    )
                if "equip_df_editor" in st.session_state:
                    del st.session_state["equip_df_editor"]
                st.rerun()
    else:
        if current_equip:
            display_data = []
            for e in current_equip:
                manual_desc = []
                if e["AC"]:
                    manual_desc.append(f"+{e['AC']} AC")
                if e["Mod 1"] != "None":
                    manual_desc.append(f"+{e['Val 1']} {e['Mod 1']}")
                if e["Mod 2"] != "None":
                    manual_desc.append(f"+{e['Val 2']} {e['Mod 2']}")

                kb_effect = get_item_effect(e["Item"])
                final_effect = kb_effect
                if manual_desc:
                    final_effect = f"{kb_effect} | Custom: {', '.join(manual_desc)}"

                display_data.append(
                    {
                        "Equipped": "✅" if e["Equipped"] else "❌",
                        "Item": e["Item"],
                        "Effect": final_effect,
                    }
                )
            st.table(display_data)
        else:
            st.write("Inventory is empty.")


def _render_features_spells(edit_mode: bool):
    """Renders features and spellcasting sections."""
    st.markdown("#### Features & Traits")
    if edit_mode:
        edited_features_df = st.data_editor(
            st.session_state.features_traits, num_rows="dynamic", key="edit_features"
        )
        if edited_features_df is not None:
            new_features = []
            import pandas as pd

            rows = (
                edited_features_df.iterrows()
                if isinstance(edited_features_df, pd.DataFrame)
                else enumerate(edited_features_df)
            )
            for _, row in rows:
                new_features.append(
                    {
                        "name": row.get("name") or "New Feature",
                        "description": row.get("description") or "",
                        "source": row.get("source"),
                    }
                )
            st.session_state.features_traits = new_features
    else:
        features = st.session_state.get("features_traits", [])
        if features is None:
            features = []
        for f in features:
            name = f.get("name", "Feature")
            desc = f.get("description", "").replace(
                "\n", "  \n"
            )  # Ensure markdown line breaks
            st.markdown(f"**{name}**  \n{desc}")
            st.divider()

    st.markdown("#### Spells")
    if edit_mode:
        cs1, cs2, cs3 = st.columns(3)
        options = ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
        current_ability = st.session_state.spell_ability
        ability_index = (
            options.index(current_ability) if current_ability in options else 0
        )

        st.session_state.spell_ability = cs1.selectbox(
            "Spellcasting Ability",
            options,
            index=ability_index,
        )
        cs2.number_input(
            "Spell Save DC (Derived)",
            0,
            30,
            st.session_state.spell_save_dc,
            disabled=True,
        )
        cs3.text_input(
            "Spell Attack Bonus (Derived)",
            st.session_state.spell_attack_bonus,
            disabled=True,
        )

        flat_spells = []
        for lvl, spell_list in st.session_state.spells.items():
            for spell in spell_list:
                flat_spells.append({"level": lvl, "spell": spell})

        edited_spells = st.data_editor(
            flat_spells,
            num_rows="dynamic",
            key="edit_spells",
            column_config={
                "level": st.column_config.SelectboxColumn(
                    "Level",
                    options=[
                        "cantrips",
                        "level_1",
                        "level_2",
                        "level_3",
                        "level_4",
                        "level_5",
                        "level_6",
                        "level_7",
                        "level_8",
                        "level_9",
                    ],
                ),
                "spell": st.column_config.TextColumn("Spell Name"),
            },
        )
        if edited_spells is not None:
            new_spells = {}
            import pandas as pd

            rows = (
                edited_spells.iterrows()
                if isinstance(edited_spells, pd.DataFrame)
                else enumerate(edited_spells)
            )
            for _, row in rows:
                if row.get("level") and row.get("spell"):
                    lvl = row["level"]
                    if lvl not in new_spells:
                        new_spells[lvl] = []
                    new_spells[lvl].append(row["spell"])
            st.session_state.spells = new_spells
    else:
        # Check if they have any spells
        spells = st.session_state.get("spells", {})
        if hasattr(spells, "model_dump"):
            spells_dict = spells.model_dump()
        elif isinstance(spells, dict):
            spells_dict = spells
        else:
            spells_dict = {}

        has_any_spell = any(spells_dict.get(k) for k in spells_dict)

        if not has_any_spell:
            st.write("No spells known.")
        else:
            if (
                st.session_state.spell_ability
                and st.session_state.spell_ability != "None"
            ):
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Ability", st.session_state.spell_ability)
                sc2.metric("Save DC", st.session_state.spell_save_dc)
                sc3.metric("Attack Bonus", st.session_state.spell_attack_bonus)
                st.markdown("---")

            # Determine if class is a prepared caster
            char_class = str(st.session_state.get("char_class", "")).lower()
            is_prepared_caster = any(
                c in char_class for c in ["wizard", "cleric", "druid", "paladin"]
            )

            # Initialize prepared spells state if missing
            if (
                "prepared_spells" not in st.session_state
                or st.session_state.prepared_spells is None
            ):
                st.session_state.prepared_spells = []

            # Clean list of prepared spells for easy case-insensitive check
            prepared_clean = [
                p.strip().lower() for p in st.session_state.prepared_spells if p
            ]

            if is_prepared_caster:
                view_mode = st.radio(
                    "📖 Spellbook View:",
                    [
                        "⚔️ Prepared Spells (Combat)",
                        "📝 Manage Spellbook (Prepare Spells)",
                    ],
                    horizontal=True,
                    key="spellbook_view_toggle",
                )
            else:
                view_mode = "⚔️ Prepared Spells (Combat)"  # non-prepared casters show everything in combat

            # Load rules repository to get spell details
            from backend.repositories.rules_repository import RulesRepository

            repo = RulesRepository()
            edition = st.session_state.get("dnd_edition", "2014 Edition")
            all_spells = repo.get_all_spells(edition)
            spells_lookup = (
                {s["name"].lower().strip(): s for s in all_spells} if all_spells else {}
            )

            level_keys = [
                "cantrips",
                "level_1",
                "level_2",
                "level_3",
                "level_4",
                "level_5",
                "level_6",
                "level_7",
                "level_8",
                "level_9",
            ]

            # --- SPELL SLOTS UI ---
            spell_slots = st.session_state.get("spell_slots", {})
            if spell_slots and view_mode == "⚔️ Prepared Spells (Combat)":
                st.markdown("##### ⚡ Spell Slots")

                # Concentration Indicator
                if st.session_state.get("concentrating_on"):
                    conc_col1, conc_col2 = st.columns([3, 1])
                    with conc_col1:
                        st.info(
                            f"🧠 **Concentrating on:** {st.session_state.concentrating_on}"
                        )
                    with conc_col2:
                        if st.button(
                            "Drop",
                            key="drop_conc_spells",
                            help="Drop Concentration",
                            use_container_width=True,
                        ):
                            st.session_state.concentrating_on = None
                            save_character(get_character_dict(st.session_state))
                            st.rerun()

                slot_levels = sorted(
                    [k for k in spell_slots.keys() if k.startswith("level_")],
                    key=lambda x: int(x.split("_")[1]),
                )
                valid_slots = [
                    sl for sl in slot_levels if spell_slots[sl].get("max", 0) > 0
                ]

                if valid_slots:
                    # chunk into rows of 4
                    for i in range(0, len(valid_slots), 4):
                        chunk = valid_slots[i : i + 4]
                        cols = st.columns(4)
                        for col_idx, sl_key in enumerate(chunk):
                            sl_num = sl_key.split("_")[1]
                            max_s = spell_slots[sl_key].get("max", 0)
                            used_s = spell_slots[sl_key].get("used", 0)
                            with cols[col_idx]:
                                st.caption(
                                    f"**Level {sl_num}** ({max_s - used_s}/{max_s})"
                                )
                                # Render inline checkboxes
                                slot_cols = st.columns(max_s)
                                for j in range(max_s):
                                    is_used = j < used_s
                                    with slot_cols[j]:
                                        new_used = st.checkbox(
                                            "X",
                                            value=is_used,
                                            key=f"slot_{sl_key}_{j}",
                                            label_visibility="collapsed",
                                        )
                                        if new_used != is_used:
                                            # We need to compute the total used slots based on which ones are checked
                                            # Since Streamlit runs top-to-bottom, we just adjust the counter +1 or -1
                                            if new_used:
                                                spell_slots[sl_key]["used"] = min(
                                                    max_s, used_s + 1
                                                )
                                            else:
                                                spell_slots[sl_key]["used"] = max(
                                                    0, used_s - 1
                                                )
                                            st.session_state.spell_slots = spell_slots
                                            save_character(
                                                get_character_dict(st.session_state)
                                            )
                                            st.rerun()
                    st.markdown("---")

            if view_mode == "📝 Manage Spellbook (Prepare Spells)":
                with st.expander("➕ Add New Spell", expanded=False):
                    add_col1, add_col2 = st.columns([3, 1])
                    all_spell_names = sorted(list(spells_lookup.keys()))
                    with add_col1:
                        new_spell_name = st.selectbox(
                            "Search & Select Spell",
                            [""] + [s.title() for s in all_spell_names],
                            help="Type to search for a spell from the rules.",
                        )
                    with add_col2:
                        st.write("")  # padding
                        st.write("")  # padding
                        if st.button("Add to Spellbook", use_container_width=True):
                            if new_spell_name:
                                lookup_key = new_spell_name.lower().strip()
                                spell_data = spells_lookup.get(lookup_key)
                                if spell_data:
                                    lvl_num = spell_data.get("level", 0)
                                    target_lvl_key = (
                                        "cantrips"
                                        if lvl_num == 0
                                        else f"level_{lvl_num}"
                                    )
                                else:
                                    target_lvl_key = "level_1"  # Fallback

                                if target_lvl_key not in spells_dict:
                                    spells_dict[target_lvl_key] = []
                                if new_spell_name not in spells_dict[target_lvl_key]:
                                    spells_dict[target_lvl_key].append(new_spell_name)
                                    st.session_state.spells = spells_dict
                                    save_character(get_character_dict(st.session_state))
                                    st.rerun()
                st.markdown("---")

            shown_any_level = False

            for lvl_key in level_keys:
                spell_list = spells_dict.get(lvl_key, [])
                if not spell_list:
                    continue

                # Filter spells based on preparation if in combat view
                is_cantrip = lvl_key == "cantrips"
                if (
                    view_mode == "⚔️ Prepared Spells (Combat)"
                    and not is_cantrip
                    and is_prepared_caster
                ):
                    spell_list = [
                        s for s in spell_list if s.strip().lower() in prepared_clean
                    ]
                    if not spell_list:
                        continue

                shown_any_level = True
                lvl_title = lvl_key.title().replace("_", " ")
                st.markdown(f"##### {lvl_title}")

                for s_name in spell_list:
                    s_name_clean = s_name.strip()
                    spell_data = spells_lookup.get(s_name_clean.lower())

                    if spell_data:
                        school = spell_data.get("school", "Unknown").title()
                        lvl_num = spell_data.get("level", 0)
                        lvl_lbl = "Cantrip" if lvl_num == 0 else f"Level {lvl_num}"
                        desc = spell_data.get("description", "")
                        casting_time = spell_data.get("castingTime", "1 action")
                        s_range = spell_data.get("range", "Touch")
                        duration = spell_data.get("duration", "Instantaneous")
                        components = spell_data.get("components", [])
                        material = spell_data.get("material")
                        ritual = spell_data.get("ritual", False)
                        concentration = spell_data.get("concentration", False)
                        classes = spell_data.get("classes", [])
                    else:
                        school = "Unknown"
                        lvl_lbl = (
                            "Cantrip"
                            if lvl_key == "cantrips"
                            else f"Level {lvl_key.split('_')[1]}"
                        )
                        desc = "No description found in the rules database."
                        casting_time = "1 action"
                        s_range = "Unknown"
                        duration = "Instantaneous"
                        components = []
                        material = None
                        ritual = False
                        concentration = False
                        classes = []

                    # Build tags for expander label
                    tags = []
                    if concentration:
                        tags.append("⏱️ Conc")
                    if ritual:
                        tags.append("📜 Rit")
                    # If managing spellbook, indicate if prepared in expander title
                    is_prep = s_name_clean.lower() in prepared_clean
                    if is_prepared_caster and not is_cantrip:
                        if is_prep:
                            tags.append("✅ Prepared")
                        else:
                            tags.append("❌ Unprepared")

                    tags_str = f" ({', '.join(tags)})" if tags else ""
                    expander_label = f"✨ {s_name_clean} ({lvl_lbl} {school}){tags_str}"

                    with st.expander(expander_label):
                        # Preparation Toggle if managing
                        if (
                            is_prepared_caster
                            and not is_cantrip
                            and view_mode == "📝 Manage Spellbook (Prepare Spells)"
                        ):
                            prep_val = st.checkbox(
                                f"Prepare **{s_name_clean}**",
                                value=is_prep,
                                key=f"prep_check_{lvl_key}_{s_name_clean}",
                            )
                            if prep_val != is_prep:
                                if prep_val:
                                    st.session_state.prepared_spells.append(
                                        s_name_clean
                                    )
                                else:
                                    st.session_state.prepared_spells = [
                                        p
                                        for p in st.session_state.prepared_spells
                                        if p.strip().lower() != s_name_clean.lower()
                                    ]
                                # Auto save character state
                                save_character(get_character_dict(st.session_state))
                                st.rerun()

                        # Show description and details
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Casting Time:** {casting_time}")
                            st.markdown(f"**Range:** {s_range}")
                            st.markdown(f"**Duration:** {duration}")
                        with c2:
                            comps_str = (
                                ", ".join([c.upper() for c in components])
                                if components
                                else "None"
                            )
                            st.markdown(f"**Components:** {comps_str}")
                            if material:
                                st.markdown(f"**Materials:** *{material}*")
                            if classes:
                                st.markdown(
                                    f"**Classes:** {', '.join([c.title() for c in classes])}"
                                )

                        st.markdown("---")
                        st.markdown(desc)

                        # Search description for dice formulas to roll
                        import re

                        dice_formulas = re.findall(r"\b\d+d\d+(?:\+\d+)?\b", desc)
                        # deduplicate formulas
                        unique_formulas = []
                        for f in dice_formulas:
                            if f not in unique_formulas:
                                unique_formulas.append(f)

                        # Action Row
                        st.markdown("**Actions:**")
                        cols = st.columns(max(3, len(unique_formulas) + 2))

                        # Button 1: Cast Spell
                        with cols[0]:
                            if st.button(
                                "✨ Cast",
                                key=f"cast_{lvl_key}_{s_name_clean}",
                                use_container_width=True,
                            ):
                                spell_slots_state = st.session_state.get(
                                    "spell_slots", {}
                                )
                                slot_key = lvl_key

                                can_cast = True
                                if not is_cantrip and slot_key in spell_slots_state:
                                    max_s = spell_slots_state[slot_key].get("max", 0)
                                    used_s = spell_slots_state[slot_key].get("used", 0)
                                    if used_s < max_s:
                                        spell_slots_state[slot_key]["used"] += 1
                                        st.session_state.spell_slots = spell_slots_state
                                    else:
                                        can_cast = False
                                        st.toast(
                                            f"No {lvl_lbl} slots remaining!", icon="⚠️"
                                        )

                                if can_cast:
                                    if concentration:
                                        st.session_state.concentrating_on = s_name_clean

                                    save_character(get_character_dict(st.session_state))
                                    log_roll(f"Casted **{s_name_clean}** ({lvl_lbl})!")
                                    st.rerun()

                        # Button 2: Spell Attack (if description mentions spell attack)
                        requires_attack = (
                            "spell attack" in desc.lower()
                            or "spell attack" in casting_time.lower()
                        )
                        with cols[1]:
                            if requires_attack:
                                bonus_str = str(
                                    st.session_state.get("spell_attack_bonus", "+0")
                                ).replace("+", "")
                                try:
                                    bonus = int(bonus_str)
                                except Exception:
                                    bonus = 0
                                if st.button(
                                    "🎯 Attack",
                                    key=f"atk_{lvl_key}_{s_name_clean}",
                                    use_container_width=True,
                                ):
                                    from backend.utils.dice import quick_roll

                                    res, raw = quick_roll(20, bonus)
                                    log_roll(
                                        f"**{s_name_clean}** Spell Attack: **{res}** (d20: {raw} + {bonus})"
                                    )
                                    st.session_state.active_roll = {
                                        "label": f"{s_name_clean} Attack Roll",
                                        "sides": 20,
                                        "raw": raw,
                                        "modifier": bonus,
                                        "total": res,
                                        "adv_type": "None",
                                    }
                                    if raw == 20:
                                        st.balloons()
                                    st.rerun()
                            elif (
                                "saving throw" in desc.lower() or "save" in desc.lower()
                            ):
                                save_dc = st.session_state.get("spell_save_dc", 8)
                                st.caption(f"🛡️ **Save DC:** {save_dc}")

                        # Buttons for rolling dice formulas
                        for idx, formula in enumerate(unique_formulas):
                            with cols[2 + idx]:
                                if st.button(
                                    f"🎲 {formula}",
                                    key=f"roll_{lvl_key}_{s_name_clean}_{formula}",
                                    use_container_width=True,
                                ):
                                    from backend.utils.dice import roll_dice

                                    res = roll_dice(formula)
                                    if "error" in res:
                                        st.error(f"Error rolling dice: {res['error']}")
                                    else:
                                        log_roll(
                                            f"**{s_name_clean}** ({formula}): **{res['total']}** ({res['result_text']})"
                                        )
                                        try:
                                            sides = int(
                                                re.search(r"d(\d+)", formula).group(1)
                                            )
                                        except Exception:
                                            sides = 6
                                        rolls = res.get("rolls", [1])
                                        st.session_state.active_roll = {
                                            "label": f"{s_name_clean} — {formula}",
                                            "sides": sides,
                                            "raw": rolls
                                            if len(rolls) > 1
                                            else rolls[0],
                                            "raw_selected": sum(rolls),
                                            "modifier": res.get("modifier", 0),
                                            "total": res.get("total", 1),
                                            "adv_type": "None",
                                        }
                                        st.rerun()

            if not shown_any_level and view_mode == "⚔️ Prepared Spells (Combat)":
                st.info(
                    "No level 1-9 spells are currently prepared for combat. Switch to 'Manage Spellbook' to prepare your spells."
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
            st.markdown(st.session_state.playstyle_guide)
            if st.button("🔄 Regenerate Guide", width="stretch"):
                st.session_state.playstyle_guide = ""
                st.rerun()


def render_character_creator():
    """Renders the AI Character Forge interface with dynamic edition-based options."""
    st.markdown("### Forge a New Hero")
    st.write(
        "Choose your D&D edition first, then select your core pillars or let the AI decide!"
    )

    with st.container(border=True):
        # Determine lists based on edition
        forge_edition = st.session_state.dnd_edition

        if forge_edition == EDITION_2014:
            race_label = "Race"
            race_options = RACES_2014
            bg_options = BACKGROUNDS_2014
            class_options = CLASSES_2014
            subclass_map = SUBCLASSES_2014
        else:
            race_label = "Species"
            race_options = SPECIES_2024
            bg_options = BACKGROUNDS_2024
            class_options = CLASSES_2024
            subclass_map = SUBCLASSES_2024

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            forge_race = st.selectbox(
                race_label,
                ["AI Choice"] + race_options,
            )
        with col_b:
            forge_class = st.selectbox(
                "Class",
                ["AI Choice"] + class_options,
            )
        with col_c:
            forge_background = st.selectbox(
                "Background",
                ["AI Choice"] + bg_options,
            )

        col_lvl, col_g, col_sub = st.columns(3)
        with col_lvl:
            forge_level = st.number_input(
                "Target Level", min_value=1, max_value=20, value=1
            )
        with col_g:
            forge_gender = st.selectbox("Gender", ["AI Choice"] + GENDERS)

        # Subclass Logic
        subclass_options = ["AI Choice"]
        show_subclass = False

        if forge_class != "AI Choice":
            # 2024 rules: Subclass always at level 3
            if forge_edition == EDITION_2024:
                if forge_level >= 3:
                    show_subclass = True
                    subclass_options += subclass_map.get(forge_class, [])
            # 2014 rules: Subclass level varies
            else:
                sub_lvls = {
                    "Cleric": 1,
                    "Sorcerer": 1,
                    "Warlock": 1,
                    "Wizard": 2,
                    "Druid": 2,
                }
                req_lvl = sub_lvls.get(forge_class, 3)
                if forge_level >= req_lvl:
                    show_subclass = True
                    subclass_options += subclass_map.get(forge_class, [])

        with col_sub:
            if show_subclass:
                forge_subclass = st.selectbox("Subclass", subclass_options)
            else:
                st.info("Subclass unlocks at higher levels.")
                forge_subclass = None

        concept = st.text_area(
            "Additional Flavor / Concept:",
            placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon.",
            height=100,
        )
        col_name, col_align, col_rolled = st.columns([2, 1, 1])
        with col_name:
            forge_name = st.text_input(
                "Character Name (optional)", placeholder="AI Choice"
            )
        with col_align:
            forge_alignment = st.selectbox("Alignment", ["AI Choice"] + ALIGNMENTS)
        with col_rolled:
            use_rolled = st.toggle("🎲 Use Rolled Stats", value=False)

    if st.session_state.temp_forged_char is None:
        if st.button("Generate Character", type="primary", width="stretch"):
            logger.info(
                f"User requested AI Character Forge: Edition={forge_edition}, Race={forge_race}, Class={forge_class}, Subclass={forge_subclass}, Level={forge_level}"
            )
            with st.spinner("Rolling stats and forging character..."):
                result = forge_character(
                    forge_level,
                    forge_race,
                    forge_class,
                    forge_background,
                    concept,
                    name=forge_name if forge_name.strip() else "AI Choice",
                    gender=forge_gender,
                    stats_mode="rolled" if use_rolled else "standard",
                    alignment=forge_alignment,
                    edition=forge_edition,
                    subclass=forge_subclass,
                )
                if result and "char_name" in result:
                    result["char_portrait"] = generate_portrait_url(result)
                    st.session_state.temp_forged_char = result
                    st.session_state.temp_portrait = result["char_portrait"]
                    st.rerun()
                else:
                    st.error("Failed to generate character. Please try again.")
    else:
        # --- Preview of the forged character ---
        char = st.session_state.temp_forged_char
        st.markdown("### 🔍 Hero Preview")
        with st.container(border=True):
            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                st.markdown(f"**Name:** {char['char_name']}")
                class_info = f"{char['char_class']}"
                if char.get("subclass"):
                    class_info += f" ({char['subclass']})"
                st.markdown(f"**Class:** {class_info} (Level {char['char_level']})")
                st.markdown(
                    f"**Race/Species:** {char['race']} | **Background:** {char['background']}"
                )
                st.markdown(f"**Edition:** {char.get('dnd_edition', '2014 Edition')}")
                if char.get("advancements"):
                    st.markdown("**Advancements:**")
                    for adv in char["advancements"]:
                        st.write(
                            f"- Lv.{adv.get('level')} {adv.get('type')}: {adv.get('name')}"
                        )
                st.markdown(f"**Backstory Snippet:** {char['backstory'][:200]}...")
            with col_p2:
                st.markdown("**Stats:**")
                stats_str = " | ".join([f"{k}:{v}" for k, v in char["stats"].items()])
                st.write(stats_str)

            if st.button("🔄 Regenerate Portrait", width="stretch"):
                with st.spinner("Forging visual identity..."):
                    portrait_url = generate_portrait_url(char)
                    st.session_state.temp_portrait = portrait_url
                    st.rerun()

            if "temp_portrait" in st.session_state and st.session_state.temp_portrait:
                st.image(
                    st.session_state.temp_portrait,
                    caption="Character Portrait Preview",
                    width="stretch",
                )

            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("✅ Accept & Equip Hero", width="stretch", type="primary"):
                char["char_id"] = str(uuid.uuid4())[:8]
                update_session_from_dict(st.session_state, char)
                trigger_sync()
                if "temp_portrait" in st.session_state:
                    st.session_state.char_portrait = st.session_state.temp_portrait
                    st.session_state.temp_portrait = None

                saved_dict = get_character_dict(st.session_state)
                if save_character(saved_dict):
                    logger.info(f"Auto-saved new character: {char['char_name']}")
                st.session_state.last_saved_char = saved_dict.copy()
                st.session_state.temp_forged_char = None
                st.session_state.player_view = "sheet"
                st.rerun()

            if c_btn2.button("❌ Discard", width="stretch"):
                # Clean up the portrait if discarded
                if (
                    "temp_portrait" in st.session_state
                    and st.session_state.temp_portrait
                ):
                    try:
                        if os.path.exists(st.session_state.temp_portrait):
                            os.remove(st.session_state.temp_portrait)
                            logger.info(
                                f"Cleaned up discarded portrait: {st.session_state.temp_portrait}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to clean up discarded portrait: {e}")

                st.session_state.temp_forged_char = None
                st.session_state.temp_portrait = None
                st.rerun()


@st.dialog("🔥 The Forge: Character Ascension")
def run_level_up_wizard():
    """Manual-first guide for leveling up with optional AI support and preview/revert."""
    target_lv = st.session_state.char_level + 1

    # Initialize Temp State for Level Up if not present
    if "lv_up_temp" not in st.session_state:
        st.session_state.lv_up_temp = {
            "hp_inc": 0,
            "hp_method": "Fixed (Average)",
            "asi_feat_choice": "Ability Score Improvement",
            "stats_raised": [],
            "selected_feat": None,
            "new_features": [],
            "ai_consulted": False,
            "selected_spells": [],
            "selected_spells_data": [],
        }

    temp = st.session_state.lv_up_temp

    st.markdown(f"### Elevating to Level {target_lv}")

    # STEP 1: Vitals (HP)
    st.markdown("#### 💓 Step 1: Vital Stats")

    vitals = get_level_up_vitals(
        st.session_state.char_class,
        st.session_state.char_level,
        st.session_state.stats.get("CON", 10),
        st.session_state.dnd_edition,
        st.session_state.get("features_traits", []),
    )

    die_size = vitals["die_size"]
    con_mod = vitals["con_mod"]
    avg_hp = vitals["average_hp_gain"]

    hp_col1, hp_col2 = st.columns([1, 1])
    temp["hp_method"] = hp_col1.radio(
        "HP Increase Method:",
        ["Fixed (Average)", "Roll for it!"],
        horizontal=True,
        index=0 if temp["hp_method"] == "Fixed (Average)" else 1,
    )

    if temp["hp_method"] == "Fixed (Average)":
        temp["hp_inc"] = avg_hp
        hp_col2.info(f"Adding average HP: **+{avg_hp}**")
    else:
        if "lv_up_hp_roll" not in st.session_state:
            extra_hp = vitals.get("hp_bonus_per_level", 0)
            total_bonus = con_mod + extra_hp
            bonus_str = f" + {total_bonus}" if total_bonus != 0 else ""
            if hp_col2.button(f"🎲 Roll 1d{die_size}{bonus_str}"):
                import random

                roll = random.randint(1, die_size)
                st.session_state.lv_up_hp_roll = max(1, roll + total_bonus)
                st.rerun()
        if "lv_up_hp_roll" in st.session_state:
            temp["hp_inc"] = st.session_state.lv_up_hp_roll
            hp_col2.success(f"🎲 Rolled: **+{temp['hp_inc']}**")
            if hp_col2.button("🔄 Re-roll"):
                del st.session_state.lv_up_hp_roll
                st.rerun()

    # STEP 2: ASI or Feat (Backend driven)
    progression = check_progression_features(
        st.session_state.char_class, target_lv, st.session_state.dnd_edition
    )
    is_asi_level = progression["is_asi_level"]

    if is_asi_level:
        st.markdown("---")
        st.markdown("#### ⚖️ Step 2: Ability Score Improvement or Feat")
        temp["asi_feat_choice"] = st.radio(
            "Choose your benefit:",
            ["Ability Score Improvement", "Feat"],
            horizontal=True,
        )

        if temp["asi_feat_choice"] == "Ability Score Improvement":
            st.info(
                "💡 **Tip:** To increase a single ability score by **+2**, select the same stat in both dropdowns."
            )
            col_s1, col_s2 = st.columns(2)
            s1 = col_s1.selectbox(
                "Stat 1 (+1)", ["STR", "DEX", "CON", "INT", "WIS", "CHA"], key="asi_s1"
            )
            s2 = col_s2.selectbox(
                "Stat 2 (+1)", ["STR", "DEX", "CON", "INT", "WIS", "CHA"], key="asi_s2"
            )
            temp["stats_raised"] = [s1, s2]

            # Validate that stats do not exceed 20
            current_stats = st.session_state.stats
            raised_stats = {}
            for stat in temp["stats_raised"]:
                raised_stats[stat] = raised_stats.get(stat, 0) + 1

            for stat, increase in raised_stats.items():
                current_val = current_stats.get(stat, 10)
                if current_val + increase > 20:
                    st.warning(
                        f"⚠️ **Rule Warning:** Increasing {stat} from {current_val} to {current_val + increase} exceeds the standard D&D limit of **20**."
                    )
        else:
            from backend.repositories.rules_repository import RulesRepository

            rules_repo = RulesRepository()
            all_feats = rules_repo.get_all_feats(st.session_state.dnd_edition)
            feat_map = {f["name"]: f for f in all_feats}
            feat_names = list(feat_map.keys())

            temp["selected_feat"] = st.selectbox("Select Feat:", options=feat_names)

            # --- Prerequisite Validation ---
            selected_feat_data = feat_map.get(temp["selected_feat"], {})
            prereqs = selected_feat_data.get("prerequisites", {})
            if isinstance(prereqs, dict):
                prereq_warnings = []
                min_lvl = prereqs.get("min_level", 0)
                if min_lvl > 0 and target_lv < min_lvl:
                    prereq_warnings.append(
                        f"Requires **Level {min_lvl}+** (you will be Level {target_lv})"
                    )
                stat_reqs = prereqs.get("stat_requirements", {})
                current_stats = st.session_state.stats
                for stat_key, min_val in stat_reqs.items():
                    char_val = current_stats.get(stat_key, 10)
                    if char_val < min_val:
                        prereq_warnings.append(
                            f"Requires **{stat_key} {min_val}+** (yours is {char_val})"
                        )
                other_reqs = prereqs.get("other", [])
                if other_reqs:
                    prereq_warnings.append(
                        f"Other requirements: {', '.join(other_reqs)}"
                    )
                if prereq_warnings:
                    st.warning(
                        "⚠️ **Prerequisite Warning:**\n- " + "\n- ".join(prereq_warnings)
                    )

            # --- Sync Feat Mechanics ---
            if st.button("🔍 Sync Feat Mechanics"):
                with st.spinner(
                    f"Consulting the Oracle about {temp['selected_feat']}..."
                ):
                    analysis = analyze_feat(
                        temp["selected_feat"], st.session_state.dnd_edition
                    )
                    temp["feat_analysis"] = analysis

                    # Apply automated HP bonuses (e.g. Tough)
                    hp_per_lvl = analysis.get("hp_bonus_per_level", 0)
                    if hp_per_lvl > 0:
                        extra_hp = hp_per_lvl * target_lv
                        temp["hp_inc"] += extra_hp
                        st.success(
                            f"📈 Applied +{extra_hp} HP from {temp['selected_feat']}!"
                        )

                    # Suggest stat bonus
                    if analysis.get("has_stat_choice"):
                        st.info(
                            f"💡 This feat allows a +1 to: {', '.join(analysis.get('stat_choice_options', []))}"
                        )
                    elif any(v > 0 for v in analysis.get("stat_bonus", {}).values()):
                        bonus_stats = [
                            k
                            for k, v in analysis.get("stat_bonus", {}).items()
                            if v > 0
                        ]
                        st.success(
                            f"💡 This feat gives a +1 to: {', '.join(bonus_stats)}"
                        )

            # Support for Feats that provide an Ability Score Increase (+1)
            feat_desc = feat_map.get(temp["selected_feat"], {}).get("description", "")
            has_stat_increase = (
                "increase your" in feat_desc.lower()
                and "score by 1" in feat_desc.lower()
            )

            # Determine index for the selectbox
            default_index = 0  # "None"
            if "feat_analysis" in temp:
                analysis = temp["feat_analysis"]
                bonus_stats = [
                    k for k, v in analysis.get("stat_bonus", {}).items() if v > 0
                ]
                if bonus_stats:
                    stat_options = ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
                    if bonus_stats[0] in stat_options:
                        default_index = stat_options.index(bonus_stats[0])

            if has_stat_increase or st.session_state.dnd_edition == EDITION_2024:
                feat_stat = st.selectbox(
                    "Feat Stat Bonus (+1):",
                    ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                    index=default_index,
                    key="feat_stat_bonus",
                    help="Some feats (like Resilient) allow you to increase an ability score by 1. Select the stat here.",
                )
                temp["feat_stat_bonus"] = feat_stat if feat_stat != "None" else None
            else:
                # For feats like Tough that have NO stat bonus, we hide the selector
                temp["feat_stat_bonus"] = None

            # Show description of selected feat
            if temp["selected_feat"]:
                selected_feat_data = feat_map.get(temp["selected_feat"])
                if selected_feat_data:
                    with st.expander("Feat Details", expanded=False):
                        desc = selected_feat_data.get(
                            "description", "No description available."
                        )
                        st.write(desc)

                        # Removed AI completion button to avoid meta-text
                    temp["selected_feat_desc"] = selected_feat_data.get(
                        "description", ""
                    )

    # STEP 3: Learn Spells (Optional)
    st.markdown("---")
    st.markdown("#### 🔮 Step 3: Learn Spells (Optional)")

    from backend.repositories.rules_repository import RulesRepository

    rules_repo = RulesRepository()
    edition = st.session_state.get("dnd_edition", "2014 Edition")
    all_spells = rules_repo.get_all_spells(edition)

    if all_spells:
        char_class_lower = str(st.session_state.get("char_class", "")).lower()
        subclass_lower = str(st.session_state.get("subclass", "")).lower()

        # Calculate maximum spell level slot appropriate for target level
        is_full = any(
            c in char_class_lower
            for c in ["wizard", "cleric", "druid", "sorcerer", "bard", "warlock"]
        )
        is_half = any(c in char_class_lower for c in ["paladin", "ranger", "artificer"])
        is_third = any(
            s in subclass_lower for s in ["eldritch knight", "arcane trickster"]
        )

        if is_full:
            max_lvl = (target_lv + 1) // 2
        elif is_half:
            max_lvl = (target_lv + 3) // 4
        elif is_third:
            max_lvl = (target_lv + 5) // 6
        else:
            max_lvl = 1  # Allow cantrips / 1st level spells for generic feats

        max_lvl = min(9, max(0, max_lvl))

        if "wizard" in char_class_lower:
            rec = "2 new Wizard spells"
        elif any(
            c in char_class_lower for c in ["sorcerer", "bard", "warlock", "ranger"]
        ):
            rec = "1 new spell"
        elif any(c in char_class_lower for c in ["cleric", "druid", "paladin"]):
            rec = (
                "access to all class spells of your levels (add any you wish to track)"
            )
        elif is_third:
            rec = "1 new Wizard spell"
        else:
            rec = "spells if granted by a Feat (e.g. Magic Initiate)"

        lvl_str = "Cantrips" if max_lvl == 0 else f"up to Level {max_lvl}"
        st.info(
            f"📚 **Class Rules Guide:** As a Level {target_lv} {st.session_state.get('char_class', '').title()}, you can learn/add spells of **{lvl_str}**. Standard rules recommendation: **{rec}**."
        )

        # Checkbox to include Cantrips
        include_cantrips = st.checkbox(
            "Show Cantrips (Level 0)",
            value=False,
            help="Cantrips are normally only learned at specific levels according to your class progression table.",
        )

        # Hide any spells that exceed the maximum castable level, and filter out cantrips unless checked
        min_lvl = 0 if include_cantrips else 1
        all_spells = [s for s in all_spells if min_lvl <= s.get("level", 0) <= max_lvl]

        class_spells = [
            s
            for s in all_spells
            if char_class_lower in [c.lower() for c in s.get("classes", [])]
        ]

        # Radio to toggle list
        spell_filter = st.radio(
            "Show spells for:",
            ["My Class Spells Only", "All Spells"],
            horizontal=True,
            key="lv_up_spell_filter",
        )

        available_spells = (
            class_spells
            if (spell_filter == "My Class Spells Only" and class_spells)
            else all_spells
        )
        # Sort spells by level, then name
        available_spells = sorted(
            available_spells,
            key=lambda x: (x.get("level", 0), x.get("name", "").lower()),
        )

        option_labels = []
        option_map = {}
        for s in available_spells:
            lvl = s.get("level", 0)
            lvl_lbl = "Cantrip" if lvl == 0 else f"Level {lvl}"
            label = f"[{lvl_lbl}] {s['name']}"
            option_labels.append(label)
            option_map[label] = s

        temp["selected_spells"] = st.multiselect(
            "Select spells to add to your spellbook:",
            options=option_labels,
            default=temp.get("selected_spells", []),
        )

        temp["selected_spells_data"] = [
            {"name": option_map[lbl]["name"], "level": option_map[lbl].get("level", 0)}
            for lbl in temp["selected_spells"]
            if lbl in option_map
        ]

        # Rule Validation Warning for spell count
        num_selected = len(temp["selected_spells_data"])
        limit = 0
        if "wizard" in char_class_lower:
            limit = 2
        elif any(
            c in char_class_lower for c in ["sorcerer", "bard", "warlock", "ranger"]
        ):
            limit = 1
        elif is_third:
            limit = 1

        if limit > 0 and num_selected > limit:
            st.warning(
                f"⚠️ **Rule Limit Warning:** You have selected {num_selected} spells, but your class progression table only allows learning {limit} new spell{'s' if limit > 1 else ''} at this level. (You can still proceed if your DM permitted additional spells/feats)."
            )
    else:
        st.write("No spells found in the rules database.")

    # STEP 4: AI Enrichment (Optional)
    st.markdown("---")
    st.markdown("#### ✨ Step 4: Consult the Oracle (Optional)")
    if not temp["ai_consulted"]:
        if st.button("🔮 Ask AI for Features & Suggestions"):
            with st.spinner("Oracle is analyzing your path..."):
                char_data = get_character_dict(st.session_state)

                # Prepare context for AI based on manual choices
                user_choices_context = {
                    "HP Increase": f"+{temp['hp_inc']} ({temp['hp_method']})",
                }
                if is_asi_level:
                    if temp["asi_feat_choice"] == "Ability Score Improvement":
                        user_choices_context["Benefit Chosen"] = (
                            f"ASI (+1 to {', '.join(temp['stats_raised'])})"
                        )
                    else:
                        user_choices_context["Benefit Chosen"] = (
                            f"Feat: {temp['selected_feat']}"
                        )

                analysis = analyze_level_up(
                    char_data, user_choices=user_choices_context
                )
                if analysis:
                    temp["new_features"] = analysis.get("automatic_changes", [])
                    temp["suggestions"] = analysis.get("suggestions", [])
                    temp["ai_consulted"] = True
                    st.rerun()
    else:
        st.success("Oracle has spoken. New features and suggestions loaded.")
        for feat in temp["new_features"]:
            with st.expander(f"🔹 {feat.get('name')}"):
                st.write(feat.get("description"))

    # STEP 5: PREVIEW
    st.markdown("---")
    st.markdown("#### 🛡️ Step 5: Level Up Preview")
    prev_col1, prev_col2 = st.columns(2)

    # Calculate preview stats
    prev_hp = st.session_state.hp_max + temp["hp_inc"]
    prev_stats = st.session_state.stats.copy()
    if temp["asi_feat_choice"] == "Ability Score Improvement":
        for s in temp["stats_raised"]:
            prev_stats[s] = prev_stats.get(s, 10) + 1

    prev_col1.metric("Max HP", f"{prev_hp}", delta=f"+{temp['hp_inc']}")
    if is_asi_level:
        if temp["asi_feat_choice"] == "Ability Score Improvement":
            stats_display = ", ".join([f"{s}+1" for s in temp["stats_raised"]])
            prev_col2.metric("Stats Boost", stats_display)
        elif temp["selected_feat"]:
            feat_info = temp["selected_feat"]
            if temp.get("feat_stat_bonus"):
                feat_info += f" (+1 {temp['feat_stat_bonus']})"
            prev_col2.metric("New Feat", feat_info)

    if temp.get("selected_spells_data"):
        st.markdown(
            f"**🔮 Spells to Learn:** {', '.join([s['name'] for s in temp['selected_spells_data']])}"
        )

    st.markdown("---")

    # FINAL ACTIONS
    col_fin1, col_fin2 = st.columns(2)

    if col_fin1.button("🔥 Finalize Ascension", width="stretch", type="primary"):
        # APPLY CHANGES
        st.session_state.char_level = target_lv
        st.session_state.hp_max = prev_hp

        # Apply Stats
        st.session_state.stats = prev_stats
        if temp["asi_feat_choice"] == "Feat" and temp.get("feat_stat_bonus"):
            stat = temp["feat_stat_bonus"]
            st.session_state.stats[stat] = st.session_state.stats.get(stat, 10) + 1

        # Add feat if chosen
        if temp["asi_feat_choice"] == "Feat" and temp["selected_feat"]:
            st.session_state.features_traits.append(
                {
                    "name": f"Feat: {temp['selected_feat']}",
                    "description": temp.get(
                        "selected_feat_desc", "Selected during manual level up."
                    ),
                }
            )

        # Add selected spells to known list
        spells = st.session_state.get("spells", {})
        if hasattr(spells, "model_dump"):
            spells_dict = spells.model_dump()
        elif isinstance(spells, dict):
            spells_dict = spells
        else:
            spells_dict = {}

        for s_info in temp.get("selected_spells_data", []):
            name = s_info["name"]
            lvl = s_info["level"]
            lvl_key = "cantrips" if lvl == 0 else f"level_{lvl}"
            if lvl_key not in spells_dict:
                spells_dict[lvl_key] = []
            if name not in spells_dict[lvl_key]:
                spells_dict[lvl_key].append(name)

        st.session_state.spells = spells_dict

        # Add AI features if consulted
        if temp["ai_consulted"]:
            current_feat_names = [
                f.get("name") for f in st.session_state.features_traits
            ]
            for feat in temp["new_features"]:
                if feat.get("name") not in current_feat_names:
                    st.session_state.features_traits.append(feat)

            # Update spell slots if AI provided them
            if "updated_spell_slots" in temp and temp["updated_spell_slots"]:
                # We store slots in a dedicated field if needed, or trigger sync to recalculate
                pass

        # Cleanup
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll

        trigger_sync()
        save_character(get_character_dict(st.session_state))
        st.success(f"Ascension Complete! Level {target_lv} reached.")
        st.rerun()

    if col_fin2.button("↩️ Discard & Revert", width="stretch"):
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll
        st.rerun()
