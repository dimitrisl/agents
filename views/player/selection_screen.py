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

    st.markdown(
        """
    <style>
    /* ── Hero Header ─────────────────────────────── */
    .sel-hero {
        text-align: center;
        padding: 2.5rem 1rem 1.5rem;
    }
    .sel-hero h1 {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #e8d5a3 0%, #c0392b 60%, #8b0000 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.3rem;
        letter-spacing: -0.02em;
    }
    .sel-hero p {
        color: #888;
        font-size: 1.05rem;
        margin: 0;
    }

    /* ── Section Cards ───────────────────────────── */
    .sel-card {
        background: linear-gradient(145deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%);
        border: 1px solid rgba(200,160,80,0.18);
        border-radius: 14px;
        padding: 1.4rem 1.6rem 1rem;
        margin-bottom: 1.2rem;
        transition: border-color 0.25s;
    }
    .sel-card:hover { border-color: rgba(200,160,80,0.4); }
    .sel-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #e8d5a3;
        margin-bottom: 0.25rem;
    }
    .sel-card-sub {
        font-size: 0.82rem;
        color: #777;
        margin-bottom: 0.9rem;
    }

    /* ── Character Vault ─────────────────────────── */
    .vault-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #e8d5a3;
        margin-bottom: 0.2rem;
    }
    .vault-sub {
        font-size: 0.82rem;
        color: #777;
        margin-bottom: 1rem;
    }
    .vault-divider {
        border: none;
        border-top: 1px solid rgba(200,160,80,0.12);
        margin: 0.6rem 0;
    }

    /* ── Suppress default Streamlit gaps ─────────── */
    div[data-testid="stVerticalBlock"] > div:has(.sel-card) { margin-bottom: 0; }
    </style>

    <div class="sel-hero">
      <h1>⚔️ Welcome, Adventurer</h1>
      <p>Choose your path to begin your journey.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── LEFT COLUMN ─────────────────────────────────────────────────────────
    with col_left:
        # ── Forge ──
        st.markdown(
            """
        <div class="sel-card">
          <div class="sel-card-title">✨ Forge a New Hero</div>
          <div class="sel-card-sub">Let AI assist you in creating a brand-new legendary character.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button("Go to Character Forge", width="stretch", type="primary"):
            from backend.core.state_manager import init_session_state

            init_session_state(st.session_state, force=True)
            st.session_state.character_active = True
            st.session_state.player_view = "forge"
            st.rerun()

        # ── PDF Import ──
        st.markdown(
            """
        <div class="sel-card" style="margin-top:1rem">
          <div class="sel-card-title">📄 Import from PDF</div>
          <div class="sel-card-sub">Upload an existing D&amp;D Character Sheet (PDF).</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

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
                                parsed_data["char_id"] = str(uuid.uuid4())[:8]
                                parsed_data["dnd_edition"] = import_edition
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

        # ── JSON / VTT Import ──
        st.markdown(
            """
        <div class="sel-card" style="margin-top:1rem">
          <div class="sel-card-title">⚙️ Import from JSON / VTT</div>
          <div class="sel-card-sub">Upload a character file (.json) from this app or a Foundry VTT export.</div>
        </div>
        """,
            unsafe_allow_html=True,
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
                    if "system" in raw_data and "items" in raw_data:
                        st.info(
                            "Foundry VTT format detected. Mapping to internal schema..."
                        )
                        data = import_vtt_character(raw_data)
                    else:
                        data = {}
                        if "character_info" in raw_data:
                            data.update(raw_data.pop("character_info"))
                        data.update(raw_data)
                    if not data:
                        st.error("Failed to process character data.")
                        st.stop()
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
                    if "weapons" in data and isinstance(data["weapons"], list):
                        for w in data["weapons"]:
                            if "attack_bonus" in w:
                                w["attack_bonus"] = str(w["attack_bonus"])
                            if "properties" in w and isinstance(w["properties"], list):
                                w["properties"] = ", ".join(w["properties"])
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
                    if "stats" not in data:
                        data["stats"] = {s: 10 for s in core_stats}
                    if not data.get("char_id"):
                        data["char_id"] = str(uuid.uuid4())[:8]
                    validated = CharacterSchema.model_validate(data, strict=False)
                    final_data = validated.model_dump()
                    if save_character(final_data):
                        update_session_from_dict(st.session_state, final_data)
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

    # ── RIGHT COLUMN ─────────────────────────────────────────────────────────
    with col_right:
        st.markdown(
            """
        <div class="vault-header">🛡️ Hero Vault</div>
        <div class="vault-sub">Load one of your previously saved characters.</div>
        """,
            unsafe_allow_html=True,
        )

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
                    name_parts = char_file.replace(".json", "").split("_")
                    display_name = " ".join(name_parts[:-1]).title()
                    edition = char_data.get("dnd_edition", "2014 Edition")
                    edition_tag = f"{'2024' if '2024' in edition else '2014'}"
                    char_class = char_data.get("char_class", "")
                    char_level = char_data.get("char_level", "")
                    label = (
                        f"🛡️ {display_name}  ·  {char_class} {char_level}  ({edition_tag})"
                        if char_class
                        else f"🛡️ {display_name}  ({edition_tag})"
                    )

                    delete_key = f"confirm_delete_{char_file}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False

                    if not st.session_state[delete_key]:
                        c_col1, c_col2 = st.columns([5, 1])
                        if c_col1.button(
                            label, width="stretch", key=f"load_{char_file}"
                        ):
                            update_session_from_dict(st.session_state, char_data)
                            is_char_2024 = "2024" in edition
                            st.session_state.dnd_edition_toggle = is_char_2024
                            st.session_state.dnd_edition = (
                                EDITION_2024 if is_char_2024 else EDITION_2014
                            )
                            st.query_params["edition"] = (
                                "2024" if is_char_2024 else "2014"
                            )
                            trigger_sync()
                            st.session_state.character_active = True
                            st.session_state.player_view = "sheet"
                            st.session_state.last_saved_char = get_character_dict(
                                st.session_state
                            )
                            char_id_val = char_data.get("char_id", "")
                            if char_id_val:
                                st.query_params["cid"] = char_id_val
                            st.rerun()
                        if c_col2.button(
                            "🗑️",
                            help=f"Delete {display_name}",
                            key=f"del_{char_file}",
                            width="stretch",
                        ):
                            st.session_state[delete_key] = True
                            st.rerun()
                    else:
                        d_col1, d_col2, d_col3 = st.columns([4, 1, 1])
                        d_col1.markdown(f"⚠️ Delete **{display_name}**?")
                        if d_col2.button(
                            "✔️",
                            help=f"Confirm deletion of {display_name}",
                            key=f"conf_{char_file}",
                            width="stretch",
                            type="primary",
                        ):
                            if delete_character(char_file):
                                st.toast(f"Deleted {display_name}")
                                del st.session_state[delete_key]
                                st.rerun()
                        if d_col3.button(
                            "✖️", help="Cancel", key=f"can_{char_file}", width="stretch"
                        ):
                            st.session_state[delete_key] = False
                            st.rerun()
            else:
                st.info("No saved heroes found matching the current edition.")
        else:
            st.markdown(
                """
            <div style="text-align:center;padding:3rem 1rem;color:#555;border:1px dashed rgba(200,160,80,0.2);border-radius:12px;">
              <div style="font-size:2.5rem;margin-bottom:0.5rem">📜</div>
              <div style="font-size:0.9rem">Your vault is empty.<br>Forge a new hero to begin.</div>
            </div>
            """,
                unsafe_allow_html=True,
            )
