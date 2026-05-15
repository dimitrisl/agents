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
)
import pypdf
from backend.core.storage import (
    save_character,
    load_character,
    list_characters,
    delete_character,
    list_campaigns,
)
from backend.core.state_manager import (
    get_character_dict,
    update_session_from_dict,
)
from backend.services.mechanics_service import (
    get_modifier as calculate_modifier,
    get_level_up_vitals,
    check_progression_features,
)
from backend.utils.pdf_exporter import export_character_to_pdf
from backend.utils.ui_utils import render_character_header
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

logger = logging.getLogger("DnDAssistant.PlayerView")


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
        col1, col2, col3 = st.columns([3, 1, 1])
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
                        use_container_width=True,
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
                    use_container_width=True,
                    key="side_sync",
                ):
                    trigger_sync()
                    st.rerun()

                if st.button(
                    "💾 Save to File", use_container_width=True, key="side_save"
                ):
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
            for char_file in saved_chars:
                # Extract full name from filename (format: name_with_underscores_uuid.json)
                name_parts = char_file.replace(".json", "").split("_")
                display_name = " ".join(name_parts[:-1]).title()

                c_col1, c_col2 = st.columns([4, 1])
                char_data = load_character(char_file)
                edition_tag = ""
                if char_data:
                    edition = char_data.get("dnd_edition", "2014 Edition")
                    edition_tag = f" ({'2024' if '2024' in edition else '2014'})"

                if c_col1.button(
                    f"🛡️ {display_name}{edition_tag}",
                    width="stretch",
                    key=f"load_{char_file}",
                ):
                    if char_data:
                        update_session_from_dict(st.session_state, char_data)
                        st.session_state.character_active = True
                        st.session_state.player_view = "sheet"
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
                        import pdfplumber

                        pdf_reader = pypdf.PdfReader(uploaded_pdf)
                        extracted_text = ""

                        # 1. Robust Form Field Extraction (AcroForm + Manual Annotation Scan)
                        field_data_found = {}
                        try:
                            # Try standard pypdf fields first
                            fields = pdf_reader.get_fields()
                            if fields:
                                for name, data in fields.items():
                                    val = data.get("/V")
                                    if val:
                                        field_data_found[name] = val

                            # Manual scan for widget annotations
                            for page in pdf_reader.pages:
                                annots = page.get("/Annots")
                                if annots:
                                    for annot in annots:
                                        try:
                                            obj = annot.get_object()
                                            if obj.get("/Subtype") == "/Widget":
                                                name = obj.get("/T")
                                                val = obj.get("/V")
                                                if (
                                                    name
                                                    and val
                                                    and name not in field_data_found
                                                ):
                                                    field_data_found[name] = val
                                        except Exception as e:
                                            logger.warning(
                                                f"Field extraction error: {e}"
                                            )
                                            continue
                        except Exception as e:
                            logger.warning(f"Field extraction error: {e}")

                        if field_data_found:
                            extracted_text += "--- FORM FIELDS ---\n"
                            for field_name, val in field_data_found.items():
                                extracted_text += f"{field_name}: {val}\n"
                            extracted_text += "--- END FORM FIELDS ---\n\n"

                        # 2. Enhanced Text Extraction with pdfplumber
                        try:
                            uploaded_pdf.seek(0)
                            with pdfplumber.open(uploaded_pdf) as pdf:
                                extracted_text += "--- VISUAL LAYOUT TEXT ---\n"
                                for page in pdf.pages:
                                    page_text = page.extract_text(layout=True)
                                    if page_text:
                                        extracted_text += page_text + "\n"

                                    tables = page.extract_tables()
                                    for table in tables:
                                        for row in table:
                                            clean_row = [
                                                str(c).replace("\n", " ")
                                                if c is not None
                                                else ""
                                                for c in row
                                            ]
                                            if any(c.strip() for c in clean_row):
                                                extracted_text += (
                                                    " | ".join(clean_row) + "\n"
                                                )
                                extracted_text += "--- END VISUAL LAYOUT TEXT ---\n"
                        except Exception as e:
                            logger.error(f"pdfplumber failed: {e}")
                            uploaded_pdf.seek(0)
                            for page in pdf_reader.pages:
                                text = page.extract_text()
                                if text:
                                    extracted_text += text + "\n"

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
                                save_character(get_character_dict(st.session_state))
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

    # --- Campaign Section ---
    st.markdown("---")
    current_camp = st.session_state.get("active_campaign")

    if current_camp:
        with st.container(border=True):
            col_camp1, col_camp2 = st.columns([3, 1])
            col_camp1.markdown(f"🏰 **Active Campaign:** {current_camp}")
            if col_camp2.button(
                "🚪 Leave", key="leave_camp_btn", use_container_width=True
            ):
                from backend.core.storage import remove_from_campaign

                char_id = st.session_state.char_id
                char_filename = f"{st.session_state.char_name.replace(' ', '_').lower()}_{char_id}.json"

                if remove_from_campaign(current_camp, char_filename):
                    st.session_state.active_campaign = None
                    st.success(f"Left {current_camp}.")
                    st.rerun()
                else:
                    st.error("Failed to leave campaign.")
    else:
        with st.expander("🏰 Join a Campaign", expanded=False):
            camps = list_campaigns()
            if camps:
                selected_camp = st.selectbox("Select Campaign to Join", camps)
                if st.button("Request to Join"):
                    from backend.core.storage import join_campaign

                    char_id = st.session_state.char_id
                    char_filename = f"{st.session_state.char_name.replace(' ', '_').lower()}_{char_id}.json"

                    if join_campaign(selected_camp, char_filename):
                        st.session_state.active_campaign = selected_camp
                        st.success(
                            f"Successfully joined {selected_camp}! The DM can now see you."
                        )
                        st.rerun()
                    else:
                        st.error("Failed to join campaign.")
            else:
                st.info("No active campaigns found. Ask your DM to create one first!")

    edit_col1, edit_col2, edit_col3, edit_col4 = st.columns([1, 1, 1, 1])
    edit_mode = edit_col1.toggle("✏️ Edit Mode")

    if edit_col2.button("🔼 Level Up", width="stretch", type="primary"):
        run_level_up_wizard()

    if edit_col3.button("🎨 Portrait", width="stretch"):
        with st.spinner("Forging visual identity..."):
            char_data = get_character_dict(st.session_state)
            st.session_state.char_portrait = generate_portrait_url(char_data)
            st.rerun()

    if edit_mode:
        if edit_col4.button("💾 Save", width="stretch"):
            trigger_sync()
            char_data = get_character_dict(st.session_state)
            if save_character(char_data):
                st.session_state.needs_validation = True
                st.toast("Changes saved! You can now validate your build.")
                st.rerun()
            else:
                st.error("Save failed.")

    if st.session_state.needs_validation:
        if st.button("⚖️ Validate Character Build", type="primary"):
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
        if st.button("Dismiss Validation"):
            st.session_state.validation_result = None
            st.rerun()

    if st.session_state.char_portrait:
        import os

        if os.path.exists(st.session_state.char_portrait):
            with st.expander("🖼️ Portrait Preview", expanded=False):
                st.image(st.session_state.char_portrait, width="stretch")
        else:
            st.warning("🖼️ Portrait file missing. Using default.")
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=100)

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

    updated = process_character_update(current_char, stat_updates, equipment_deltas)

    # 4. Update UI State
    update_session_from_dict(st.session_state, updated)

    # Update widget temp keys from the fresh data
    for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        st.session_state[f"stat_val_{k}"] = st.session_state.stats[k]

    # 5. CLEAR the editor state
    if "edit_equip_table" in st.session_state:
        st.session_state["edit_equip_table"] = {
            "edited_rows": {},
            "added_rows": [],
            "deleted_rows": [],
        }


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


def _render_core_stats(edit_mode: bool):
    """Renders ability scores, core attributes, and skills."""
    if edit_mode:
        c_n, c_c, c_l, c_r = st.columns(4)
        c_n.text_input("Name", key="char_name")
        c_c.text_input("Class", key="char_class")
        c_c.text_input("Subclass", key="subclass")
        c_l.number_input("Level", 1, 20, key="char_level")
        c_r.text_input("Race", key="race")

        c_b, c_a, c_hp, c_ac = st.columns(4)
        c_b.text_input("Background", key="background")
        c_a.text_input("Alignment", key="alignment")
        c_hp.number_input("Max HP (Derived)", 1, 500, key="hp_max", disabled=True)
        c_ac.number_input(
            "Armor Class (Derived)", 1, 50, key="armor_class", disabled=True
        )

        c_hd, c_pass = st.columns(2)
        c_hd.text_input("Hit Dice (Derived)", key="hit_dice", disabled=True)
        c_pass.number_input(
            "Passive Perception (Derived)",
            0,
            30,
            key="passive_perception",
            disabled=True,
        )

        st.markdown("#### Ability Scores")
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        def stat_input(col, label, key):
            col.number_input(label, 1, 30, key=f"stat_val_{key}")

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
                "Bonus": st.column_config.NumberColumn("Bonus", disabled=False),
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

        st.write(
            "Saving Throws (Proficient):", ", ".join(st.session_state.saving_throws)
        )
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Max HP", st.session_state.hp_max)
        c2.metric("Armor Class", st.session_state.armor_class)
        c3.metric("Speed", f"{st.session_state.speed} ft")
        c4.metric("Proficiency", f"+{st.session_state.proficiency_bonus}")

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
        with st.popover("🎲 Custom / Damage Roll", use_container_width=True):
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

            for w in st.session_state.weapons:
                dmg = w.get("damage", "")
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
                "Roll!", type="primary", use_container_width=True, key="custom_roll_btn"
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
                    st.success(msg)
                else:
                    r1, raw1 = quick_roll(p_dtype, total_mod)
                    r2, raw2 = quick_roll(p_dtype, total_mod)
                    final = max(r1, r2) if p_adv == "Advantage" else min(r1, r2)
                    msg = f"**{p_adv} ({p_dtype})**: **{final}** (Rolls: {r1}, {r2} | Mod: {mod_desc})"
                    log_roll(msg)
                    st.success(msg)

        col_sk, col_sv = st.columns(2)
        with col_sk:
            st.markdown("#### Skills")
            for k, v in st.session_state.skills.items():
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
        with col_sv:
            st.markdown("#### Saving Throws")
            saves = st.session_state.get("saving_throw_values", {})
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

    st.markdown("---")
    st.markdown("#### ✨ Heroic Advancements (Feats & ASI)")
    if edit_mode:
        st.session_state.advancements = st.data_editor(
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
        st.session_state.weapons = st.data_editor(
            st.session_state.weapons,
            num_rows="dynamic",
            key="edit_weapons",
            use_container_width=True,
        )
        if st.button("➕ Add New Weapon", use_container_width=True):
            st.session_state.weapons.append(
                {"name": "New Weapon", "attack_bonus": "+0", "damage": "1d4"}
            )
            st.rerun()
    else:
        for i, w in enumerate(st.session_state.weapons):
            with st.container(border=True):
                w_col1, w_col2, w_col3 = st.columns([3, 1, 1])
                w_col1.markdown(f"🗡️ **{w.get('name', 'Unknown')}**")
                w_col1.caption(
                    f"To Hit: {w.get('attack_bonus', '+0')} | Dmg: {w.get('damage', '1d4')}"
                )

                if w_col2.button("🎯 To Hit", key=f"atk_{i}", use_container_width=True):
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
                    if raw == 20:
                        st.balloons()
                        st.success("CRITICAL HIT! 🎯")
                    elif raw == 1:
                        st.error("NATURAL 1! 💀")

                if w_col3.button("💥 Dmg", key=f"dmg_{i}", use_container_width=True):
                    from backend.utils.dice import roll_dice

                    dmg_str = w.get("damage", "1d4")
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

    # Standardize equipment format (List of Dicts)
    current_equip = []
    attuned_count = 0
    for e in st.session_state.equipment:
        if isinstance(e, dict):
            item_dict = {
                "Item": e.get("name", ""),
                "Equipped": e.get("equipped", False),
                "Attuned": e.get("attuned", False),
                "AC": e.get("ac_bonus", 0),
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

        st.data_editor(
            equip_df,
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
        if st.button("➕ Add New Item", use_container_width=True):
            # To add an item, we must trigger sync to save pending edits first,
            # then append the new item and rerun.
            trigger_sync()
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
        st.session_state.features_traits = st.data_editor(
            st.session_state.features_traits, num_rows="dynamic", key="edit_features"
        )
    else:
        for f in st.session_state.features_traits:
            name = f.get("name", "Feature")
            desc = f.get("description", "").replace(
                "\n", "  \n"
            )  # Ensure markdown line breaks
            st.markdown(f"**{name}**  \n{desc}")
            st.divider()

    st.markdown("#### Spells")
    if edit_mode:
        cs1, cs2, cs3 = st.columns(3)
        options = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        current_ability = st.session_state.spell_ability
        ability_index = (
            options.index(current_ability) if current_ability in options else 3
        )

        st.session_state.spell_ability = cs1.selectbox(
            "Spellcasting Ability",
            options,
            index=ability_index,
        )
        st.session_state.spell_save_dc = cs2.number_input(
            "Spell Save DC", 0, 30, st.session_state.spell_save_dc
        )
        st.session_state.spell_attack_bonus = cs3.text_input(
            "Spell Attack Bonus", st.session_state.spell_attack_bonus
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
        new_spells = {}
        for row in edited_spells:
            if row.get("level") and row.get("spell"):
                lvl = row["level"]
                if lvl not in new_spells:
                    new_spells[lvl] = []
                new_spells[lvl].append(row["spell"])
        st.session_state.spells = new_spells
    else:
        if not st.session_state.spells:
            st.write("No spells known.")
        else:
            for lvl, spell_list in st.session_state.spells.items():
                st.write(
                    f"**{lvl.title().replace('_', ' ')}:** {', '.join(spell_list)}"
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
                if "temp_portrait" in st.session_state:
                    st.session_state.char_portrait = st.session_state.temp_portrait
                    st.session_state.temp_portrait = None

                if save_character(get_character_dict(st.session_state)):
                    logger.info(f"Auto-saved new character: {char['char_name']}")
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
            if hp_col2.button(f"🎲 Roll 1d{die_size} + {con_mod}"):
                import random

                roll = random.randint(1, die_size)
                st.session_state.lv_up_hp_roll = max(1, roll + con_mod)
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
            col_s1, col_s2 = st.columns(2)
            s1 = col_s1.selectbox(
                "Stat 1 (+1)", ["STR", "DEX", "CON", "INT", "WIS", "CHA"], key="asi_s1"
            )
            s2 = col_s2.selectbox(
                "Stat 2 (+1)", ["STR", "DEX", "CON", "INT", "WIS", "CHA"], key="asi_s2"
            )
            temp["stats_raised"] = [s1, s2]
        else:
            from backend.repositories.rules_repository import RulesRepository

            rules_repo = RulesRepository()
            all_feats = rules_repo.get_all_feats(st.session_state.dnd_edition)
            feat_map = {f["name"]: f for f in all_feats}
            feat_names = list(feat_map.keys())

            temp["selected_feat"] = st.selectbox("Select Feat:", options=feat_names)

            # Support for Half-Feats (+1 to a stat)
            st.info("💡 Many feats provide a +1 bonus to an ability score.")
            feat_stat = st.selectbox(
                "Feat Stat Bonus (+1) - Optional:",
                ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                key="feat_stat_bonus",
            )
            temp["feat_stat_bonus"] = feat_stat if feat_stat != "None" else None

            # Show description of selected feat
            if temp["selected_feat"]:
                selected_feat_data = feat_map.get(temp["selected_feat"])
                if selected_feat_data:
                    with st.expander("Feat Details", expanded=False):
                        st.write(
                            selected_feat_data.get(
                                "description", "No description available."
                            )
                        )
                    temp["selected_feat_desc"] = selected_feat_data.get(
                        "description", ""
                    )

    # STEP 3: AI Enrichment (Optional)
    st.markdown("---")
    st.markdown("#### ✨ Step 3: Consult the Oracle (Optional)")
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

    # STEP 4: PREVIEW
    st.markdown("---")
    st.markdown("#### 🛡️ Level Up Preview")
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

    st.markdown("---")

    # FINAL ACTIONS
    col_fin1, col_fin2 = st.columns(2)

    if col_fin1.button(
        "🔥 Finalize Ascension", use_container_width=True, type="primary"
    ):
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

    if col_fin2.button("↩️ Discard & Revert", use_container_width=True):
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll
        st.rerun()
