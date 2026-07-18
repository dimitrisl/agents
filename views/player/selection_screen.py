import streamlit as st
import logging

import uuid
from backend.services.rules_service import (
    parse_character_from_text,
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
)
from backend.utils.image_utils import generate_portrait_url
from backend.core.constants import (
    EDITION_2014,
    EDITION_2024,
)

from views.player._helpers import trigger_sync

logger = logging.getLogger(__name__)


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
