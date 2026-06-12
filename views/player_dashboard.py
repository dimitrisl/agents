import streamlit as st
import logging

import uuid
import os
from backend.services.forge_service import (
    forge_character,
    forge_character_manual,
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
from backend.utils.ui_utils import (
    render_character_header,
    render_active_roll_visual,
    render_themed_markdown,
)
from backend.utils.image_utils import generate_portrait_url, save_custom_portrait
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


@st.dialog("📥 Character Sheet PDF Export")
def show_pdf_export_preview(char_dict: dict):
    """Displays a preview of the character data before exporting to PDF."""
    st.markdown("### 🧬 Phyrexian bio-mechanical template ready for export.")
    st.write("Review the compiled metrics before committing to the PDF.")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(f"**Name:** `{char_dict.get('char_name', 'Unnamed')}`")
        st.markdown(
            f"**Class:** `{char_dict.get('char_class', 'Unknown')} {char_dict.get('char_level', 1)}`"
        )
        if char_dict.get("subclass"):
            st.markdown(f"**Subclass:** `{char_dict['subclass']}`")
        st.markdown(f"**Species/Race:** `{char_dict.get('race', 'Unknown')}`")
        st.markdown(f"**Background:** `{char_dict.get('background', 'Unknown')}`")
        st.markdown(f"**Alignment:** `{char_dict.get('alignment', 'Neutral')}`")
        st.markdown(f"**Ruleset:** `{char_dict.get('dnd_edition', '2014 Edition')}`")
    with col2:
        portrait_url = char_dict.get("char_portrait")
        if portrait_url:
            display_portrait = portrait_url
            if not portrait_url.startswith("http") and not portrait_url.startswith(
                "data:"
            ):
                from backend.utils.ui_utils import get_image_base64

                b64 = get_image_base64(portrait_url)
                if b64:
                    display_portrait = b64
            st.image(display_portrait, use_container_width=True)
        else:
            st.info("No portrait loaded.")

    st.markdown("#### 📊 Core Vitals & Abilities")
    # Vitals columns
    v_col1, v_col2, v_col3 = st.columns(3)
    v_col1.metric("HP Max", char_dict.get("hp_max", 10))
    v_col2.metric("Armor Class", char_dict.get("armor_class", 10))
    v_col3.metric("Speed", f"{char_dict.get('speed', 30)} ft")

    # Abilities layout
    stats = char_dict.get("stats", {})
    cols = st.columns(6)
    for idx, stat_name in enumerate(["STR", "DEX", "CON", "INT", "WIS", "CHA"]):
        val = stats.get(stat_name, 10)
        mod = calculate_modifier(val)
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        with cols[idx]:
            st.markdown(
                f"""
                <div style='text-align: center; border: 1px solid #444; border-radius: 8px; padding: 8px; background-color: rgba(255,255,255,0.05);'>
                    <div style='font-size: 0.8rem; font-weight: bold; color: var(--primary-color); text-transform: uppercase;'>{stat_name}</div>
                    <div style='font-size: 1.5rem; font-weight: 800; margin: 4px 0;'>{val}</div>
                    <div style='font-size: 0.9rem; color: #888;'>({mod_str})</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    # Saving Throws & Skills
    saves_list = char_dict.get("saving_throws", [])
    skills_list = char_dict.get("skill_proficiencies", [])

    col_s, col_sk = st.columns(2)
    with col_s:
        st.markdown("**Saving Throws:**")
        if saves_list:
            st.write(", ".join(saves_list))
        else:
            st.caption("No saving throw proficiencies.")
    with col_sk:
        st.markdown("**Skill Proficiencies:**")
        if skills_list:
            st.write(", ".join(skills_list))
        else:
            st.caption("No skill proficiencies.")

    st.markdown("---")
    # Quick Inventory & Weapon summary
    w_col, e_col = st.columns(2)
    with w_col:
        weapons = char_dict.get("weapons", [])
        st.markdown(f"**⚔️ Weapons ({len(weapons)}):**")
        if weapons:
            for w in weapons[:3]:
                st.write(
                    f"- {w.get('name')} ({w.get('damage_dice')} {w.get('attack_bonus')})"
                )
            if len(weapons) > 3:
                st.write(f"*...and {len(weapons) - 3} more*")
        else:
            st.caption("No weapons equipped.")

    with e_col:
        features = char_dict.get("features_traits", [])
        st.markdown(f"**🛡️ Features & Traits ({len(features)}):**")
        if features:
            for f in features[:3]:
                st.write(f"- {f.get('name')}")
            if len(features) > 3:
                st.write(f"*...and {len(features) - 3} more*")
        else:
            st.caption("No features listed.")

    # Spells summary
    spells = char_dict.get("spells", {})
    total_spells = (
        sum(len(s_list) for s_list in spells.values())
        if isinstance(spells, dict)
        else 0
    )
    if total_spells > 0:
        st.markdown(f"**🧙 Spellcasting:** `{total_spells}` spells known / prepared.")

    st.markdown("---")
    st.info(
        "⚠️ **Note:** Make sure all adjustments are complete. Once downloaded, form fields can still be edited manually within any PDF viewer."
    )

    # PDF Bytes preparation and Download button
    template_path = "5E_CharacterSheet_Fillable.pdf"
    with st.spinner("Compiling PDF sheet..."):
        pdf_bytes = export_character_to_pdf(char_dict, template_path)

    if pdf_bytes:
        st.download_button(
            label="📥 Confirm & Download PDF",
            data=pdf_bytes,
            file_name=f"{char_dict['char_name']}_Sheet.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            key="confirm_download_pdf_btn",
        )
    else:
        st.error("Failed to generate character sheet PDF.")


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


def render_selection_screen():
    """Renders a high-aesthetics landing page for character selection or creation."""
    st.title("Welcome, Adventurer")
    st.markdown("### Choose your path to begin your journey.")
    st.markdown("---")

    col_forge, col_load = st.columns(2)

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

                                # Sync edition state on import
                                is_char_2024 = "2024" in import_edition
                                st.session_state.dnd_edition_toggle = is_char_2024
                                st.session_state.dnd_edition = (
                                    EDITION_2024 if is_char_2024 else EDITION_2014
                                )
                                st.query_params["edition"] = (
                                    "2024" if is_char_2024 else "2014"
                                )

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

        # --- JSON / VTT Import Section ---
        st.markdown("---")
        st.subheader("⚙️ Import from JSON / VTT")
        st.write(
            "Upload a character file (.json) from this app or a Foundry VTT export."
        )

        uploaded_json = st.file_uploader(
            "Upload JSON/VTT",
            type=["json"],
            label_visibility="collapsed",
            key="json_vtt_uploader",
        )

        if uploaded_json is not None:
            if st.button("📥 Import Data", type="primary", width="stretch"):
                try:
                    import json
                    from backend.core.schemas import CharacterSchema
                    from backend.utils.import_utils import import_vtt_character

                    raw_data = json.load(uploaded_json)

                    # --- Automatic Detection ---
                    if "system" in raw_data and "items" in raw_data:
                        # This looks like a Foundry VTT export
                        st.info(
                            "Foundry VTT format detected. Mapping to internal schema..."
                        )
                        data = import_vtt_character(raw_data)
                    else:
                        # Treat as internal format with robust mapping
                        data = {}
                        if "character_info" in raw_data:
                            data.update(raw_data.pop("character_info"))
                        data.update(raw_data)

                    if not data:
                        st.error("Failed to process character data.")
                        st.stop()

                    # --- Robust Mapping / Normalization ---
                    mappings = {
                        "name": "char_name",
                        "class": "char_class",
                        "level": "char_level",
                        "portrait": "char_portrait",
                        "edition": "dnd_edition",
                    }
                    for old_key, new_key in mappings.items():
                        if old_key in data and new_key not in data:
                            data[new_key] = data[old_key]

                    # Weapons normalization
                    if "weapons" in data and isinstance(data["weapons"], list):
                        for w in data["weapons"]:
                            if "attack_bonus" in w:
                                w["attack_bonus"] = str(w["attack_bonus"])
                            if "properties" in w and isinstance(w["properties"], list):
                                w["properties"] = ", ".join(w["properties"])

                    # Stats normalization
                    for stat_alt in [
                        "ability_scores",
                        "attributes",
                        "abilities",
                        "scores",
                    ]:
                        if stat_alt in data and "stats" not in data:
                            data["stats"] = data.pop(stat_alt)

                    core_stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
                    if "stats" not in data:
                        top_level_stats = {
                            s: data.get(s)
                            for s in core_stats
                            if data.get(s) is not None
                        }
                        if len(top_level_stats) >= 3:
                            data["stats"] = top_level_stats
                            for s in core_stats:
                                if s not in data["stats"]:
                                    data["stats"][s] = 10

                    # Ensure defaults
                    if "stats" not in data:
                        data["stats"] = {
                            "STR": 10,
                            "DEX": 10,
                            "CON": 10,
                            "INT": 10,
                            "WIS": 10,
                            "CHA": 10,
                        }
                    if not data.get("char_id"):
                        data["char_id"] = str(uuid.uuid4())[:8]

                    # Final validation
                    validated = CharacterSchema.model_validate(data, strict=False)
                    final_data = validated.model_dump()

                    # Save and activate
                    if save_character(final_data):
                        update_session_from_dict(st.session_state, final_data)

                        # Sync edition state
                        is_char_2024 = "2024" in final_data.get("dnd_edition", "")
                        st.session_state.dnd_edition_toggle = is_char_2024
                        st.session_state.dnd_edition = (
                            EDITION_2024 if is_char_2024 else EDITION_2014
                        )
                        st.query_params["edition"] = "2024" if is_char_2024 else "2014"

                        st.session_state.character_active = True
                        st.session_state.player_view = "sheet"
                        st.success(
                            f"Successfully imported {final_data.get('char_name')}!"
                        )
                        st.rerun()
                    else:
                        st.error("Failed to save imported character.")
                except Exception as e:
                    st.error(f"Import Error: {e}")
                    logger.error(f"JSON/VTT Import failed: {e}", exc_info=True)

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
                    if char_data.get("is_npc", False):
                        continue
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

                        # Sync active ruleset settings based on loaded character
                        is_char_2024 = "2024" in edition
                        st.session_state.dnd_edition_toggle = is_char_2024
                        st.session_state.dnd_edition = (
                            EDITION_2024 if is_char_2024 else EDITION_2014
                        )
                        st.query_params["edition"] = "2024" if is_char_2024 else "2014"

                        trigger_sync()
                        st.session_state.character_active = True
                        st.session_state.player_view = "sheet"
                        st.session_state.last_saved_char = get_character_dict(
                            st.session_state
                        )
                        # Persist char_id in URL so refresh auto-reloads
                        char_id_val = char_data.get("char_id", "")
                        if char_id_val:
                            st.query_params["cid"] = char_id_val
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
                st.info("No saved heroes found in the vault.")
        else:
            st.info("No saved heroes found in the vault.")


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

            def _apply_dmg_callback():
                dmg = st.session_state.get("dmg_val", 0)
                if dmg > 0:
                    curr = st.session_state.get(
                        "hp_current", st.session_state.get("hp_max", 10)
                    )
                    st.session_state.hp_current = max(0, curr - dmg)
                    st.session_state.dmg_val = 0
                    save_character(get_character_dict(st.session_state))

            def _apply_heal_callback():
                heal = st.session_state.get("heal_val", 0)
                if heal > 0:
                    curr = st.session_state.get(
                        "hp_current", st.session_state.get("hp_max", 10)
                    )
                    m_hp = st.session_state.get("hp_max", 10)
                    st.session_state.hp_current = min(m_hp, curr + heal)
                    st.session_state.heal_val = 0
                    save_character(get_character_dict(st.session_state))

            with hc1:
                st.number_input("Damage", min_value=0, step=1, key="dmg_val")
                st.button(
                    "🩸 Apply Dmg",
                    on_click=_apply_dmg_callback,
                    use_container_width=True,
                )

            with hc2:
                st.number_input("Heal", min_value=0, step=1, key="heal_val")
                st.button(
                    "💚 Apply Heal",
                    on_click=_apply_heal_callback,
                    use_container_width=True,
                )

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

            # Short Rest Popover
            with st.popover("⛺ Short Rest", use_container_width=True):
                st.markdown("### Short Rest")
                st.write("Spend Hit Dice to regain HP.")

                total_hd = st.session_state.char_level
                used_hd = st.session_state.get("hit_dice_used", 0)
                available_hd = max(0, total_hd - used_hd)

                st.write(f"Available Hit Dice: **{available_hd} / {total_hd}**")

                if available_hd > 0:
                    hd_to_spend = st.number_input(
                        "Number of Hit Dice to spend",
                        min_value=1,
                        max_value=available_hd,
                        value=1,
                        step=1,
                        key="short_rest_hd_count",
                    )

                    if st.button(
                        "Roll & Heal", type="primary", use_container_width=True
                    ):
                        import random
                        from backend.services.mechanics_service import get_modifier

                        con_score = st.session_state.stats.get("CON", 10)
                        con_mod = get_modifier(con_score)

                        # Get hit die size (e.g. "d8" or "d10")
                        hit_die_str = st.session_state.get("hit_dice", "d8")
                        try:
                            # Extract number after 'd'
                            die_size = int(hit_die_str.lower().split("d")[-1])
                        except Exception:
                            die_size = 8

                        rolls = [
                            random.randint(1, die_size) for _ in range(hd_to_spend)
                        ]
                        roll_sum = sum(rolls)
                        con_bonus = con_mod * hd_to_spend
                        total_healed = max(0, roll_sum + con_bonus)

                        old_hp = st.session_state.hp_current
                        new_hp = min(st.session_state.hp_max, old_hp + total_healed)
                        st.session_state.hp_current = new_hp
                        st.session_state.hit_dice_used = used_hd + hd_to_spend

                        # Add roll to roll history log
                        roll_msg = f"Short Rest: Spent {hd_to_spend}d{die_size} + {con_bonus} CON. Rolled {rolls}. Healed {total_healed} HP."
                        if "roll_history" not in st.session_state:
                            st.session_state.roll_history = []
                        st.session_state.roll_history.insert(0, roll_msg)

                        save_character(get_character_dict(st.session_state))
                        st.success(
                            f"Healed for {total_healed} HP! ({old_hp} ➡️ {new_hp})"
                        )

                        # Class-specific resource restoration
                        char_class = st.session_state.get("char_class", "").lower()
                        if "warlock" in char_class:
                            slots = st.session_state.get("spell_slots", {})
                            for lvl, data in slots.items():
                                data["used"] = 0
                            st.session_state.spell_slots = slots
                            st.info("🔮 Pact Magic spell slots restored!")

                        st.rerun()
                else:
                    st.warning("No Hit Dice remaining.")

            # Trance / Long Rest selection
            is_elf = "elf" in str(st.session_state.get("race", "")).lower()
            if is_elf:
                rest_label = "🧘 Elven Trance"
                rest_toast = "Trance completed! 4 hours of meditation restored HP, Hit Dice, and Spell Slots."
            else:
                rest_label = "🔥 Long Rest"
                rest_toast = (
                    "Long Rest completed! HP, Hit Dice, and Spell Slots restored."
                )

            if st.button(rest_label, type="primary", use_container_width=True):
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
                st.toast(rest_toast)
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
                    "Magic Bonus (+X)",
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
                "damage": None,
                "ability_modifier": None,
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
            render_themed_markdown(st.session_state.playstyle_guide)
            if st.button("🔄 Regenerate Guide", width="stretch"):
                st.session_state.playstyle_guide = ""
                st.rerun()


def render_character_creator():
    """Renders the AI Character Forge and Manual Character Builder interfaces with dynamic edition-based options."""
    st.markdown("### Forge a New Hero")

    if st.session_state.temp_forged_char is None:
        tab_ai, tab_manual = st.tabs(
            ["✨ AI Character Forge", "🛠️ Manual Character Builder"]
        )

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

        with tab_ai:
            st.write(
                "Choose your D&D edition first, then select your core pillars or let the AI decide!"
            )
            with st.container(border=True):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    forge_race = st.selectbox(
                        race_label,
                        ["AI Choice"] + race_options,
                        key="forge_race_ai",
                    )
                with col_b:
                    forge_class = st.selectbox(
                        "Class",
                        ["AI Choice"] + class_options,
                        key="forge_class_ai",
                    )
                with col_c:
                    forge_background = st.selectbox(
                        "Background",
                        ["AI Choice"] + bg_options,
                        key="forge_background_ai",
                    )

                col_lvl, col_g, col_sub = st.columns(3)
                with col_lvl:
                    forge_level = st.number_input(
                        "Target Level",
                        min_value=1,
                        max_value=20,
                        value=1,
                        key="forge_level_ai",
                    )
                with col_g:
                    forge_gender_selected = st.selectbox(
                        "Gender",
                        ["AI Choice"] + GENDERS,
                        key="forge_gender_selected_ai",
                    )
                    if forge_gender_selected == "Other":
                        forge_gender = st.text_input(
                            "Specify Gender",
                            placeholder="e.g. Agender, Fluid",
                            key="forge_gender_other_ai",
                        )
                    else:
                        forge_gender = forge_gender_selected

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
                        forge_subclass = st.selectbox(
                            "Subclass", subclass_options, key="forge_subclass_ai"
                        )
                    else:
                        st.info("Subclass unlocks at higher levels.")
                        forge_subclass = None

                concept = st.text_area(
                    "Additional Flavor / Concept:",
                    placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon.",
                    height=100,
                    key="concept_ai",
                )
                col_name, col_align, col_rolled = st.columns([2, 1, 1])
                with col_name:
                    forge_name = st.text_input(
                        "Character Name (optional)",
                        placeholder="AI Choice",
                        key="forge_name_ai",
                    )
                with col_align:
                    forge_alignment = st.selectbox(
                        "Alignment",
                        ["AI Choice"] + ALIGNMENTS,
                        key="forge_alignment_ai",
                    )
                with col_rolled:
                    use_rolled = st.toggle(
                        "🎲 Use Rolled Stats",
                        value=False,
                        help="Roll 4d6 and drop the lowest die for each of the six ability scores (Classic D&D Method). If disabled, standard array (15, 14, 13, 12, 10, 8) will be used.",
                        key="use_rolled_ai",
                    )

                if use_rolled:
                    st.info(
                        "**Classic Rolling Method (4d6 drop lowest):**  \n"
                        "The AI will simulate rolling four 6-sided dice for each ability score and discarding the lowest value. "
                        "This typically results in a more organic (and often more powerful) stat array than the Standard Array, "
                        "but carries the risk of lower-than-average scores."
                    )

            if st.button(
                "Generate Character",
                type="primary",
                width="stretch",
                key="ai_submit_button",
            ):
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

        with tab_manual:
            st.write(
                "Build your character step-by-step manually. The system will handle all the rules calculations!"
            )
            with st.container(border=True):
                # 1. Basic Info
                col_m_name, col_m_level, col_m_gender = st.columns([2, 1, 1])
                with col_m_name:
                    manual_name = st.text_input(
                        "Character Name", value="New Hero", key="manual_name"
                    )
                with col_m_level:
                    manual_level = st.number_input(
                        "Level", min_value=1, max_value=20, value=1, key="manual_level"
                    )
                with col_m_gender:
                    manual_gender_selected = st.selectbox(
                        "Gender", GENDERS, key="manual_gender_selected"
                    )
                    if manual_gender_selected == "Other":
                        manual_gender = st.text_input(
                            "Specify Gender",
                            placeholder="e.g. Agender, Fluid",
                            key="manual_gender_other",
                        )
                    else:
                        manual_gender = manual_gender_selected

                # 2. Pillars
                col_m_race, col_m_class, col_m_bg = st.columns(3)
                with col_m_race:
                    manual_race = st.selectbox(
                        f"{race_label}", race_options, key="manual_race"
                    )
                with col_m_class:
                    manual_class = st.selectbox(
                        "Class", class_options, key="manual_class"
                    )
                with col_m_bg:
                    manual_background = st.selectbox(
                        "Background", bg_options, key="manual_background"
                    )

                col_m_align, col_m_sub = st.columns(2)
                with col_m_align:
                    manual_alignment = st.selectbox(
                        "Alignment", ALIGNMENTS, key="manual_alignment"
                    )

                # Subclass Logic
                manual_subclass_options = ["None"]
                show_manual_subclass = False

                # 2024 rules: Subclass always at level 3
                if forge_edition == EDITION_2024:
                    if manual_level >= 3:
                        show_manual_subclass = True
                        manual_subclass_options += subclass_map.get(manual_class, [])
                # 2014 rules: Subclass level varies
                else:
                    sub_lvls = {
                        "Cleric": 1,
                        "Sorcerer": 1,
                        "Warlock": 1,
                        "Wizard": 2,
                        "Druid": 2,
                    }
                    req_lvl = sub_lvls.get(manual_class, 3)
                    if manual_level >= req_lvl:
                        show_manual_subclass = True
                        manual_subclass_options += subclass_map.get(manual_class, [])

                with col_m_sub:
                    if show_manual_subclass:
                        manual_subclass = st.selectbox(
                            "Subclass", manual_subclass_options, key="manual_subclass"
                        )
                    else:
                        st.info("Subclass unlocks at higher levels.")
                        manual_subclass = "None"

                # Concept
                manual_concept = st.text_area(
                    "Additional Flavor / Concept / Backstory Idea:",
                    placeholder="E.g., A dwarf blacksmith who wants to find the legendary forge of his ancestors.",
                    height=100,
                    key="manual_concept",
                )

                st.markdown("---")
                st.markdown("#### 🎲 Base Ability Scores")
                stat_method = st.selectbox(
                    "Ability Score Allocation Method",
                    [
                        "Standard Array (15, 14, 13, 12, 10, 8)",
                        "Roll for Stats (4d6 drop lowest)",
                        "Manual Entry / Custom",
                    ],
                    key="manual_stat_method",
                )

                if stat_method.startswith("Standard Array"):
                    col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
                    val_options = [15, 14, 13, 12, 10, 8]
                    with col_s1:
                        s_str = st.selectbox(
                            "STR", val_options, index=0, key="manual_arr_str"
                        )
                    with col_s2:
                        s_dex = st.selectbox(
                            "DEX", val_options, index=1, key="manual_arr_dex"
                        )
                    with col_s3:
                        s_con = st.selectbox(
                            "CON", val_options, index=2, key="manual_arr_con"
                        )
                    with col_s4:
                        s_int = st.selectbox(
                            "INT", val_options, index=3, key="manual_arr_int"
                        )
                    with col_s5:
                        s_wis = st.selectbox(
                            "WIS", val_options, index=4, key="manual_arr_wis"
                        )
                    with col_s6:
                        s_cha = st.selectbox(
                            "CHA", val_options, index=5, key="manual_arr_cha"
                        )

                    stats_assigned = [s_str, s_dex, s_con, s_int, s_wis, s_cha]
                    is_stat_valid = len(set(stats_assigned)) == 6
                    if not is_stat_valid:
                        st.warning(
                            "⚠️ Each standard array value (15, 14, 13, 12, 10, 8) must be assigned to exactly one ability score."
                        )

                elif stat_method.startswith("Roll for Stats"):
                    if st.button(
                        "🎲 Roll 6 Stats (4d6 drop lowest)", key="manual_roll_button"
                    ):
                        import random

                        rolled = []
                        for _ in range(6):
                            rolls = [random.randint(1, 6) for _ in range(4)]
                            rolls.sort()
                            rolled.append(sum(rolls[1:]))
                        st.session_state.manual_rolled_stats = rolled

                    if "manual_rolled_stats" in st.session_state:
                        rolled_vals = st.session_state.manual_rolled_stats
                        st.write(
                            f"Rolled Scores: **{', '.join(map(str, sorted(rolled_vals, reverse=True)))}**"
                        )

                        col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
                        with col_s1:
                            s_str = st.selectbox(
                                "STR", rolled_vals, index=0, key="manual_roll_str"
                            )
                        with col_s2:
                            s_dex = st.selectbox(
                                "DEX", rolled_vals, index=1, key="manual_roll_dex"
                            )
                        with col_s3:
                            s_con = st.selectbox(
                                "CON", rolled_vals, index=2, key="manual_roll_con"
                            )
                        with col_s4:
                            s_int = st.selectbox(
                                "INT", rolled_vals, index=3, key="manual_roll_int"
                            )
                        with col_s5:
                            s_wis = st.selectbox(
                                "WIS", rolled_vals, index=4, key="manual_roll_wis"
                            )
                        with col_s6:
                            s_cha = st.selectbox(
                                "CHA", rolled_vals, index=5, key="manual_roll_cha"
                            )

                        stats_assigned = [s_str, s_dex, s_con, s_int, s_wis, s_cha]
                        from collections import Counter

                        is_stat_valid = Counter(stats_assigned) == Counter(rolled_vals)
                        if not is_stat_valid:
                            st.warning(
                                "⚠️ Please assign each rolled score exactly once."
                            )
                    else:
                        st.info(
                            "Click the button above to roll your six ability scores."
                        )
                        is_stat_valid = False
                        s_str = s_dex = s_con = s_int = s_wis = s_cha = 10

                else:
                    col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
                    with col_s1:
                        s_str = st.number_input(
                            "STR",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_str",
                        )
                    with col_s2:
                        s_dex = st.number_input(
                            "DEX",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_dex",
                        )
                    with col_s3:
                        s_con = st.number_input(
                            "CON",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_con",
                        )
                    with col_s4:
                        s_int = st.number_input(
                            "INT",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_int",
                        )
                    with col_s5:
                        s_wis = st.number_input(
                            "WIS",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_wis",
                        )
                    with col_s6:
                        s_cha = st.number_input(
                            "CHA",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_cha",
                        )
                    is_stat_valid = True

                st.markdown("##### 📈 Ability Score Adjustments (Race / Background)")
                st.write(
                    "Apply D&D racial or background bonuses (+2 to one stat, +1 to another, or +1 to three stats)."
                )

                col_adj1, col_adj2, col_adj3 = st.columns(3)
                with col_adj1:
                    adj_plus_2 = st.selectbox(
                        "+2 Bonus to:",
                        ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                        index=0,
                        key="manual_adj_plus_2",
                    )
                with col_adj2:
                    adj_plus_1 = st.selectbox(
                        "+1 Bonus to:",
                        ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                        index=0,
                        key="manual_adj_plus_1",
                    )
                with col_adj3:
                    adj_plus_1_alt = st.selectbox(
                        "Alternative +1 Bonus to:",
                        ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                        index=0,
                        key="manual_adj_plus_1_alt",
                    )

                # Calculate final stats
                final_str = (
                    s_str
                    + (2 if adj_plus_2 == "STR" else 0)
                    + (1 if adj_plus_1 == "STR" else 0)
                    + (1 if adj_plus_1_alt == "STR" else 0)
                )
                final_dex = (
                    s_dex
                    + (2 if adj_plus_2 == "DEX" else 0)
                    + (1 if adj_plus_1 == "DEX" else 0)
                    + (1 if adj_plus_1_alt == "DEX" else 0)
                )
                final_con = (
                    s_con
                    + (2 if adj_plus_2 == "CON" else 0)
                    + (1 if adj_plus_1 == "CON" else 0)
                    + (1 if adj_plus_1_alt == "CON" else 0)
                )
                final_int = (
                    s_int
                    + (2 if adj_plus_2 == "INT" else 0)
                    + (1 if adj_plus_1 == "INT" else 0)
                    + (1 if adj_plus_1_alt == "INT" else 0)
                )
                final_wis = (
                    s_wis
                    + (2 if adj_plus_2 == "WIS" else 0)
                    + (1 if adj_plus_1 == "WIS" else 0)
                    + (1 if adj_plus_1_alt == "WIS" else 0)
                )
                final_cha = (
                    s_cha
                    + (2 if adj_plus_2 == "CHA" else 0)
                    + (1 if adj_plus_1 == "CHA" else 0)
                    + (1 if adj_plus_1_alt == "CHA" else 0)
                )

                st.markdown("**Final Ability Scores (Base + Adjustments):**")

                def display_stat(label, val):
                    mod = calculate_modifier(val)
                    mod_str = f"+{mod}" if mod >= 0 else str(mod)
                    return f"**{label}**: {val} ({mod_str})"

                st.write(
                    " | ".join(
                        [
                            display_stat("STR", final_str),
                            display_stat("DEX", final_dex),
                            display_stat("CON", final_con),
                            display_stat("INT", final_int),
                            display_stat("WIS", final_wis),
                            display_stat("CHA", final_cha),
                        ]
                    )
                )

                st.markdown("---")
                st.markdown("#### 🛡️ Proficiencies & Spellcasting")

                # Saving Throws (class-suggested defaults)
                class_saves = {
                    "Barbarian": ["STR", "CON"],
                    "Bard": ["DEX", "CHA"],
                    "Cleric": ["WIS", "CHA"],
                    "Druid": ["INT", "WIS"],
                    "Fighter": ["STR", "CON"],
                    "Monk": ["STR", "DEX"],
                    "Paladin": ["WIS", "CHA"],
                    "Ranger": ["STR", "DEX"],
                    "Rogue": ["DEX", "INT"],
                    "Sorcerer": ["CON", "CHA"],
                    "Warlock": ["WIS", "CHA"],
                    "Wizard": ["INT", "WIS"],
                    "Artificer": ["CON", "INT"],
                }
                default_saves = class_saves.get(manual_class, [])
                manual_saves = st.multiselect(
                    "Saving Throw Proficiencies",
                    ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
                    default=default_saves,
                    key=f"manual_saves_{manual_class}",
                )

                # Skill Proficiencies
                all_skills_list = [
                    "Athletics",
                    "Acrobatics",
                    "Sleight of Hand",
                    "Stealth",
                    "Arcana",
                    "History",
                    "Investigation",
                    "Nature",
                    "Religion",
                    "Animal Handling",
                    "Insight",
                    "Medicine",
                    "Perception",
                    "Survival",
                    "Deception",
                    "Intimidation",
                    "Performance",
                    "Persuasion",
                ]
                st.write(
                    "💡 *Tip: Classes typically grant 2 skill proficiencies (Rogue grants 4, Bard/Ranger grant 3) and Backgrounds typically grant 2.*"
                )
                manual_skills = st.multiselect(
                    "Skill Proficiencies",
                    all_skills_list,
                    default=[],
                    key="manual_skills",
                )

                # Spellcasting Ability
                class_spell_abilities = {
                    "Wizard": "INT",
                    "Artificer": "INT",
                    "Cleric": "WIS",
                    "Druid": "WIS",
                    "Ranger": "WIS",
                    "Bard": "CHA",
                    "Paladin": "CHA",
                    "Sorcerer": "CHA",
                    "Warlock": "CHA",
                }
                default_spell_ability = class_spell_abilities.get(manual_class, "None")
                manual_spell_ability = st.selectbox(
                    "Spellcasting Ability Modifier",
                    ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                    index=["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"].index(
                        default_spell_ability
                    ),
                    key=f"manual_spell_ability_{manual_class}",
                )

            submit_disabled = not is_stat_valid or not manual_name.strip()
            if st.button(
                "Create Character",
                type="primary",
                width="stretch",
                disabled=submit_disabled,
                key="manual_submit_button",
            ):
                final_stats_dict = {
                    "STR": final_str,
                    "DEX": final_dex,
                    "CON": final_con,
                    "INT": final_int,
                    "WIS": final_wis,
                    "CHA": final_cha,
                }
                with st.spinner("Compiling rules and manual forge..."):
                    result = forge_character_manual(
                        target_level=manual_level,
                        race=manual_race,
                        char_class=manual_class,
                        background=manual_background,
                        subclass=manual_subclass if manual_subclass != "None" else None,
                        alignment=manual_alignment,
                        gender=manual_gender,
                        name=manual_name,
                        base_stats=final_stats_dict,
                        skill_proficiencies=manual_skills,
                        saving_throws=manual_saves,
                        spell_ability=manual_spell_ability
                        if manual_spell_ability != "None"
                        else None,
                        concept=manual_concept,
                        edition=forge_edition,
                    )
                    if result and "char_name" in result:
                        result["char_portrait"] = generate_portrait_url(result)
                        st.session_state.temp_forged_char = result
                        st.session_state.temp_portrait = result["char_portrait"]
                        st.rerun()
                    else:
                        st.error(
                            "Failed to generate character. Please check inputs and try again."
                        )
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
                    portrait_url = generate_portrait_url(char, force=True)
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
                logger.info(f"Auto-saved new character: {char['char_name']}")
                st.session_state.last_saved_char = saved_dict.copy()
                st.session_state.temp_forged_char = None
                st.session_state.player_view = "sheet"
                st.session_state.edit_mode = True
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

    # STEP 2b: Choose Subclass (Required if level up crosses the subclass choice level)
    edition = st.session_state.get("dnd_edition", "2014 Edition")
    char_class = st.session_state.get("char_class", "Fighter")
    subclass_level = 3
    if edition == EDITION_2014:
        sub_lvls = {
            "Cleric": 1,
            "Sorcerer": 1,
            "Warlock": 1,
            "Wizard": 2,
            "Druid": 2,
        }
        subclass_level = sub_lvls.get(char_class, 3)

    current_subclass = st.session_state.get("subclass")
    needs_subclass = False
    if not current_subclass or current_subclass == "None":
        if target_lv >= subclass_level:
            needs_subclass = True

    if needs_subclass:
        st.markdown("---")
        st.markdown("#### 🎭 Step 2b: Choose Subclass")
        from backend.core.constants import SUBCLASSES_2014, SUBCLASSES_2024

        subclass_map = SUBCLASSES_2024 if edition == EDITION_2024 else SUBCLASSES_2014
        subclass_options = subclass_map.get(char_class, [])
        if subclass_options:
            temp["chosen_subclass"] = st.selectbox(
                f"Choose your {char_class} Subclass:",
                subclass_options,
                key="lv_up_chosen_subclass",
                index=subclass_options.index(temp.get("chosen_subclass"))
                if temp.get("chosen_subclass") in subclass_options
                else 0,
            )
        else:
            st.warning(f"No subclasses defined in the static library for {char_class}.")
            temp["chosen_subclass"] = None
    else:
        temp["chosen_subclass"] = None

    # STEP 2c: Class Features Unlocked (Static rules database)
    st.markdown("---")
    st.markdown("#### 🛡️ Step 2c: Class Features Unlocked")
    from backend.services.rules_service import get_static_class_features

    static_features = get_static_class_features(char_class, target_lv, edition)
    if static_features:
        st.write("You automatically unlock the following feature(s) at this level:")
        for feat in static_features:
            st.markdown(f"**{feat.get('name')}**")
            st.write(feat.get("description"))
            # Ensure static features are added to new_features
            existing_names = [f.get("name") for f in temp.get("new_features", [])]
            if feat.get("name") not in existing_names:
                temp.setdefault("new_features", []).append(feat)
    else:
        st.write("No new base class features unlocked at this level.")

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

        # Apply subclass if selected
        if temp.get("chosen_subclass"):
            st.session_state.subclass = temp["chosen_subclass"]

        # Add unlocked features (both static class features and AI enrichment)
        current_feat_names = [f.get("name") for f in st.session_state.features_traits]
        for feat in temp.get("new_features", []):
            if feat.get("name") not in current_feat_names:
                st.session_state.features_traits.append(feat)

        # Cleanup
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll

        trigger_sync()
        st.success(f"Ascension Complete! Level {target_lv} reached.")
        st.rerun()

    if col_fin2.button("↩️ Discard & Revert", width="stretch"):
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll
        st.rerun()
