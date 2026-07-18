from views.dm._helpers import show_npc_stat_block

import streamlit as st
import logging
import uuid
import os
from backend.services.forge_service import forge_character
from backend.core.ai_client import generate_session_prep
from backend.services.module_parser_service import ModuleParserService
from backend.core.storage import (
    save_campaign,
    load_campaign,
    list_campaigns,
    list_characters,
    load_character,
    delete_campaign,
)
from backend.utils.image_utils import generate_portrait_url
from backend.utils.ui_utils import (
    render_themed_markdown,
)
from backend.core.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    SPECIES_2024,
    CLASSES_2024,
)

logger = logging.getLogger("DnDAssistant.DMView")


def _render_campaign_selection():
    """Renders the screen to load or create a campaign."""
    with st.container(border=True):
        st.subheader("Load Existing Campaign")

        c_col1, c_col2 = st.columns([4, 1])
        with c_col2:
            if st.button(
                "🔄 Refresh", key="refresh_camp_list_btn", use_container_width=True
            ):
                st.cache_data.clear()
                st.rerun()

        camp_list = list_campaigns()
        if camp_list:
            col_sel, col_btn_load, col_btn_del = st.columns(
                [2.5, 0.9, 0.8], vertical_alignment="bottom"
            )
            with col_sel:
                selected_camp = st.selectbox(
                    "Select Campaign", camp_list, key="sel_camp_main"
                )
            with col_btn_load:
                if st.button(
                    "Load Campaign",
                    type="primary",
                    key="load_camp_btn",
                    use_container_width=True,
                ):
                    data = load_campaign(selected_camp)
                    if data:
                        st.session_state.campaign_notes = data.get("notes", "")
                        st.session_state.active_campaign_name = selected_camp
                        st.session_state.campaign_party_files = data.get("party", [])
                        st.session_state.active_campaign_data = data

                        # Automatically populate the party in session state
                        st.session_state.party = []
                        for f in st.session_state.campaign_party_files:
                            char_data = load_character(f)
                            if char_data:
                                st.session_state.party.append(char_data)

                        logger.info(
                            f"Loaded campaign: {selected_camp} with {len(st.session_state.party)} members."
                        )
                        st.toast(f"Loaded campaign: {selected_camp}")
                        st.rerun()
            with col_btn_del:
                delete_key = f"confirm_delete_camp_{selected_camp}"
                if delete_key not in st.session_state:
                    st.session_state[delete_key] = False

                if not st.session_state[delete_key]:
                    if st.button(
                        "🗑️ Delete",
                        key=f"del_camp_{selected_camp}",
                        use_container_width=True,
                    ):
                        st.session_state[delete_key] = True
                        st.rerun()
                else:
                    if st.button(
                        "⚠️ OK?",
                        key=f"conf_camp_{selected_camp}",
                        type="primary",
                        use_container_width=True,
                        help="Confirm Campaign Deletion",
                    ):
                        if delete_campaign(selected_camp):
                            st.toast(f"Deleted campaign: {selected_camp}")
                            st.session_state[delete_key] = False
                            st.rerun()
                        else:
                            st.error("Failed to delete campaign.")
                    if st.button(
                        "Cancel",
                        key=f"can_camp_{selected_camp}",
                        use_container_width=True,
                    ):
                        st.session_state[delete_key] = False
                        st.rerun()
        else:
            st.write("No saved campaigns found.")

    with st.container(border=True):
        st.subheader("Start New Campaign")
        col_name, col_btn_new = st.columns([4, 1], vertical_alignment="bottom")
        with col_name:
            new_camp_name = st.text_input(
                "Campaign Name",
                placeholder="e.g., Curse of Strahd",
                key="new_camp_input",
            )
        with col_btn_new:
            if st.button("Create Campaign", key="create_camp_btn"):
                if new_camp_name:
                    st.session_state.active_campaign_name = new_camp_name
                    st.session_state.campaign_notes = ""
                    st.session_state.active_campaign_data = {
                        "campaign_name": new_camp_name,
                        "notes": "",
                        "party": [],
                        "sessions": [],
                        "module_pdf_uri": None,
                        "extracted_npcs": [],
                    }
                    save_campaign(new_camp_name, "")
                    st.rerun()
                else:
                    st.warning("Please enter a campaign name.")


def _render_campaign_notes():
    """Renders the session logs, module manager, and campaign tools."""
    st.subheader("Campaign Manager")

    tab_overview, tab_history, tab_vault, tab_module_lore = st.tabs(
        ["Overview", "Session History", "NPC Vault", "Module Lore"]
    )

    with tab_overview:
        st.session_state.campaign_notes = st.text_area(
            "Full Master Lore & Notes:",
            st.session_state.campaign_notes,
            height=400,
            key="master_notes_area",
        )
        with st.container(border=True):
            st.markdown("#### Save Campaign")
            if st.button(
                "💾 Save Campaign",
                type="primary",
                key="save_notes_btn",
                width="stretch",
            ):
                # Always persist the active_campaign_data when saving
                camp_data = st.session_state.get("active_campaign_data", {})
                if save_campaign(
                    st.session_state.active_campaign_name,
                    st.session_state.campaign_notes,
                    sessions=camp_data.get("sessions", []),
                    module_pdf_uri=camp_data.get("module_pdf_uri"),
                    extracted_npcs=camp_data.get("extracted_npcs", []),
                    module_lore=camp_data.get("module_lore"),
                ):
                    st.toast("Campaign saved successfully!")
                else:
                    st.error("Failed to save campaign.")

    with tab_history:
        camp_data = st.session_state.get("active_campaign_data", {})
        sessions = camp_data.get("sessions", [])

        # Display timeline of previous sessions
        if sessions:
            st.markdown("#### Past Sessions")
            for idx, s in enumerate(sessions):
                with st.expander(
                    f"Session {s.get('session_number', idx + 1)}", expanded=False
                ):
                    # Editable Recap
                    edited_recap = st.text_area(
                        "Recap (Visible to Players)",
                        value=s.get("actual_recap", ""),
                        key=f"edit_recap_{idx}",
                        height=150,
                    )
                    # Editable Prep Notes
                    edited_prep = st.text_area(
                        "Prep Notes & DM Ideas (Secret to DM)",
                        value=s.get("prep_notes", ""),
                        key=f"edit_prep_{idx}",
                        height=150,
                    )

                    c_save, c_sync, _ = st.columns([1.5, 1.5, 3])

                    if c_save.button("💾 Save Changes", key=f"btn_save_session_{idx}"):
                        sessions[idx]["actual_recap"] = edited_recap
                        sessions[idx]["prep_notes"] = edited_prep
                        camp_data["sessions"] = sessions
                        st.session_state.active_campaign_data = camp_data
                        save_campaign(
                            st.session_state.active_campaign_name,
                            st.session_state.campaign_notes,
                            sessions=sessions,
                            module_pdf_uri=camp_data.get("module_pdf_uri"),
                            extracted_npcs=camp_data.get("extracted_npcs", []),
                        )
                        st.toast(f"Session {idx + 1} updated successfully!")
                        st.rerun()

                    if c_sync.button(
                        "📤 Sync to Google Doc", key=f"btn_sync_session_{idx}"
                    ):
                        gdoc_id = camp_data.get("google_doc_id")
                        gcreds_str = camp_data.get("google_credentials_json")

                        if not gdoc_id or not gcreds_str:
                            st.error(
                                "Google Docs configuration is missing. Configure it at the bottom of the page first."
                            )
                        else:
                            try:
                                import json

                                creds_info = json.loads(gcreds_str)
                                from backend.utils.google_docs import (
                                    append_to_google_doc,
                                )

                                sync_text = f"\n\n=== Session {idx + 1} Chronicle ===\n{edited_recap}\n"

                                with st.spinner("Syncing to Google Doc..."):
                                    if append_to_google_doc(
                                        creds_info, gdoc_id, sync_text
                                    ):
                                        st.success(
                                            "Session recap successfully appended to Google Doc!"
                                        )
                                    else:
                                        st.error(
                                            "Google Docs API call failed. Verify credentials and permissions."
                                        )
                            except Exception as e:
                                st.error(f"Failed to read credentials or connect: {e}")

        st.markdown("---")
        st.markdown("#### Next Session Planner")

        previous_recap = st.text_area(
            "Reality Recap (What actually happened last time?):", height=100
        )
        dm_ideas = st.text_area("Ideas for next session:", height=100)

        if st.button(
            "🪄 Generate Session Prep", type="primary", use_container_width=True
        ):
            with st.spinner("Analyzing module and notes..."):
                file_name = camp_data.get("module_pdf_uri")
                prep_result = generate_session_prep(file_name, previous_recap, dm_ideas)
                st.session_state.session_prep_result = prep_result

                # Save as new session draft
                new_session = {
                    "session_number": len(sessions) + 1,
                    "actual_recap": previous_recap,
                    "dm_ideas_for_next": dm_ideas,
                    "prep_notes": prep_result,
                }
                sessions.append(new_session)
                camp_data["sessions"] = sessions
                st.session_state.active_campaign_data = camp_data
                save_campaign(
                    st.session_state.active_campaign_name,
                    st.session_state.campaign_notes,
                    sessions=sessions,
                    module_pdf_uri=file_name,
                    extracted_npcs=camp_data.get("extracted_npcs", []),
                )

        if st.session_state.get("session_prep_result"):
            render_themed_markdown(st.session_state.session_prep_result)

        st.markdown("---")
        with st.expander("🔑 Google Docs Integration Settings", expanded=False):
            st.markdown("""
            ### Setup Instructions
            1. Create a Google Cloud Project and enable the **Google Docs API**.
            2. Create a **Service Account** under credentials, download the **JSON credentials key**.
            3. Share your target Google Document with the Service Account email (e.g., `xxx@xxx.iam.gserviceaccount.com`) as an **Editor**.
            4. Copy-paste the **Document ID** (from the Doc URL) and the **JSON key file contents** below.
            """)

            gdoc_id = st.text_input(
                "Google Document ID",
                value=camp_data.get("google_doc_id", ""),
                help="The ID of the shared Google Doc (from the URL)",
                key="gdocs_doc_id_input",
            )
            gcreds = st.text_area(
                "Service Account JSON Key File Content",
                value=camp_data.get("google_credentials_json", ""),
                help="Paste the entire contents of the downloaded credentials JSON file",
                key="gdocs_creds_input",
            )

            if st.button("💾 Save Google Docs Config", key="btn_save_gdocs_config"):
                camp_data["google_doc_id"] = gdoc_id
                camp_data["google_credentials_json"] = gcreds
                st.session_state.active_campaign_data = camp_data
                save_campaign(
                    st.session_state.active_campaign_name,
                    st.session_state.campaign_notes,
                    sessions=sessions,
                    module_pdf_uri=camp_data.get("module_pdf_uri"),
                    extracted_npcs=camp_data.get("extracted_npcs", []),
                    google_doc_id=gdoc_id,
                    google_credentials_json=gcreds,
                )
                st.toast("Google Docs configuration saved!")
                st.rerun()

    with tab_vault:
        camp_data = st.session_state.get("active_campaign_data", {})
        vault_npcs = camp_data.get("vault_npcs", [])

        col_import, col_forge = st.columns(2)
        with col_import:
            with st.expander("📥 Import from Storage (NPCs Only)", expanded=False):
                all_chars = list_characters()
                npc_only_chars = []
                for c_file in all_chars:
                    c_data = load_character(c_file)
                    if c_data and c_data.get("is_npc", False):
                        npc_only_chars.append(c_file)

                if npc_only_chars:

                    def format_char_filename(fname):
                        return fname.replace(".json", "").replace("_", " ").title()

                    char_to_add = st.selectbox(
                        "Select NPC to Add",
                        npc_only_chars,
                        format_func=format_char_filename,
                        key="vault_ingest_select",
                    )
                    if st.button(
                        "Add to Vault", key="add_to_vault_btn", width="stretch"
                    ):
                        if char_to_add not in vault_npcs:
                            vault_npcs.append(char_to_add)
                            camp_data["vault_npcs"] = vault_npcs
                            st.session_state.active_campaign_data = camp_data

                            save_campaign(
                                st.session_state.active_campaign_name,
                                st.session_state.campaign_notes,
                                sessions=camp_data.get("sessions", []),
                                module_pdf_uri=camp_data.get("module_pdf_uri"),
                                extracted_npcs=camp_data.get("extracted_npcs", []),
                                vault_npcs=vault_npcs,
                            )
                            st.success("Added to Vault!")
                            st.rerun()
                        else:
                            st.warning("Already in vault.")

        with col_forge:
            with st.expander("✨ AI Quick Forge (NPC)", expanded=False):
                q_edition = st.session_state.dnd_edition
                q_race_options = (
                    RACES_2014 if q_edition == EDITION_2014 else SPECIES_2024
                )
                q_class_options = (
                    CLASSES_2014 if q_edition == EDITION_2014 else CLASSES_2024
                )

                q_race = st.selectbox(
                    "Race/Species", ["AI Choice"] + q_race_options, key="vault_q_race"
                )
                q_class = st.selectbox(
                    "Class", ["AI Choice"] + q_class_options, key="vault_q_class"
                )
                q_level = st.number_input("Level", 1, 20, 1, key="vault_q_level")
                q_name = st.text_input(
                    "Name (optional)", placeholder="AI Choice", key="vault_q_name"
                )
                q_concept = st.text_input("Concept", key="vault_q_concept")

                if st.button(
                    "Forge & Add to Vault", key="vault_forge_add_btn", width="stretch"
                ):
                    with st.spinner("Forging & Generating Portrait..."):
                        result = forge_character(
                            q_level,
                            q_race,
                            q_class,
                            "AI Choice",
                            q_concept,
                            name=q_name if q_name.strip() else "AI Choice",
                            edition=q_edition,
                        )
                        if result:
                            result["char_id"] = str(uuid.uuid4())[:8]
                            result["is_npc"] = True
                            portrait_path = generate_portrait_url(result)
                            if portrait_path:
                                result["char_portrait"] = portrait_path

                            from backend.core.storage import save_character

                            if save_character(result):
                                char_filename = f"{result['char_name'].replace(' ', '_').lower()}_{result['char_id']}.json"
                                vault_npcs.append(char_filename)
                                camp_data["vault_npcs"] = vault_npcs
                                st.session_state.active_campaign_data = camp_data

                                save_campaign(
                                    st.session_state.active_campaign_name,
                                    st.session_state.campaign_notes,
                                    sessions=camp_data.get("sessions", []),
                                    module_pdf_uri=camp_data.get("module_pdf_uri"),
                                    extracted_npcs=camp_data.get("extracted_npcs", []),
                                    vault_npcs=vault_npcs,
                                )
                                st.success(
                                    f"Forged and added {result['char_name']} to Vault!"
                                )
                                st.rerun()
                            else:
                                st.error("Failed to save forged character.")

        with st.expander("➕ Manually Create NPC", expanded=False):
            with st.form("manual_npc_form", clear_on_submit=True):
                col_name, col_role, col_race = st.columns(3)
                m_name = col_name.text_input(
                    "Name*", placeholder="e.g. Goblin Boss", key="m_npc_name"
                )
                m_role = col_role.text_input(
                    "Role / Class", placeholder="e.g. Monster, Boss", key="m_npc_role"
                )
                m_race = col_race.text_input(
                    "Race / Species", placeholder="e.g. Goblin, Beast", key="m_npc_race"
                )

                col_ac, col_hp, col_speed, col_cr = st.columns(4)
                m_ac = col_ac.number_input(
                    "Armor Class", min_value=0, value=10, key="m_npc_ac"
                )
                m_hp = col_hp.number_input(
                    "Hit Points (Max)", min_value=1, value=10, key="m_npc_hp"
                )
                m_speed = col_speed.number_input(
                    "Speed (ft)", min_value=0, value=30, step=5, key="m_npc_speed"
                )
                m_cr = col_cr.number_input(
                    "Challenge Rating / Level",
                    min_value=1,
                    max_value=20,
                    value=1,
                    key="m_npc_cr",
                )

                st.markdown("**Ability Scores**")
                s_cols = st.columns(6)
                m_str = s_cols[0].number_input(
                    "STR", min_value=1, max_value=30, value=10, key="m_npc_str"
                )
                m_dex = s_cols[1].number_input(
                    "DEX", min_value=1, max_value=30, value=10, key="m_npc_dex"
                )
                m_con = s_cols[2].number_input(
                    "CON", min_value=1, max_value=30, value=10, key="m_npc_con"
                )
                m_int = s_cols[3].number_input(
                    "INT", min_value=1, max_value=30, value=10, key="m_npc_int"
                )
                m_wis = s_cols[4].number_input(
                    "WIS", min_value=1, max_value=30, value=10, key="m_npc_wis"
                )
                m_cha = s_cols[5].number_input(
                    "CHA", min_value=1, max_value=30, value=10, key="m_npc_cha"
                )

                st.markdown("**Attacks / Weapons**")
                st.caption(
                    "Specify attacks/weapons in format: `Name | +X to hit | YdZ+W damage` (one per line). Example: `Scimitar | +4 | 1d6+2 slashing` or `Bite | +5 | 1d8+3 piercing`."
                )
                m_weapons_text = st.text_area(
                    "Attacks/Weapons (one per line)",
                    placeholder="Weapon Name | To Hit | Damage",
                    key="m_npc_weapons_text",
                )

                st.markdown("**Special Traits / Features**")
                st.caption(
                    "Specify traits in format: `Trait Name: Trait Description` (one per line). Example: `Pack Tactics: Advantage if an ally is nearby.`"
                )
                m_features_text = st.text_area(
                    "Traits/Features (one per line)",
                    placeholder="Trait Name: Description",
                    key="m_npc_features_text",
                )

                st.markdown("**Lore / Backstory**")
                m_backstory = st.text_area(
                    "Backstory / Description",
                    placeholder="Enter NPC biography or DM notes...",
                    key="m_npc_backstory",
                )

                st.markdown("**Portrait**")
                m_portrait = st.file_uploader(
                    "Upload NPC Portrait (PNG/JPG)",
                    type=["png", "jpg", "jpeg"],
                    key="m_npc_portrait",
                )

                submit_btn = st.form_submit_button(
                    "Create and Add NPC", use_container_width=True
                )

                if submit_btn:
                    if not m_name:
                        st.error("NPC name is required.")
                    else:
                        # Parse weapons
                        weapons_parsed = []
                        if m_weapons_text.strip():
                            for line in m_weapons_text.strip().split("\n"):
                                if "|" in line:
                                    parts = [p.strip() for p in line.split("|")]
                                    if len(parts) >= 3:
                                        weapons_parsed.append(
                                            {
                                                "name": parts[0],
                                                "attack_bonus": parts[1],
                                                "damage_dice": parts[2],
                                                "damage_bonus": "+0",
                                            }
                                        )
                                    elif len(parts) == 2:
                                        weapons_parsed.append(
                                            {
                                                "name": parts[0],
                                                "attack_bonus": parts[1],
                                                "damage_dice": "1d4",
                                                "damage_bonus": "+0",
                                            }
                                        )

                        # Parse features
                        features_parsed = []
                        if m_features_text.strip():
                            for line in m_features_text.strip().split("\n"):
                                if ":" in line:
                                    name_part, desc_part = line.split(":", 1)
                                    features_parsed.append(
                                        {
                                            "name": name_part.strip(),
                                            "description": desc_part.strip(),
                                        }
                                    )
                                else:
                                    features_parsed.append(
                                        {"name": "Feature", "description": line.strip()}
                                    )

                        stats_dict = {
                            "STR": m_str,
                            "DEX": m_dex,
                            "CON": m_con,
                            "INT": m_int,
                            "WIS": m_wis,
                            "CHA": m_cha,
                        }

                        from backend.services.dm_service import create_manual_npc
                        from backend.core.storage import save_character

                        img_path = None
                        if m_portrait:
                            os.makedirs("data/module_pics", exist_ok=True)
                            safe_name = (
                                "".join(c for c in m_name if c.isalnum() or c in " _-")
                                .strip()
                                .replace(" ", "_")
                                .lower()
                            )
                            img_path = f"data/module_pics/{safe_name}_{str(uuid.uuid4())[:4]}.png"
                            with open(img_path, "wb") as f:
                                f.write(m_portrait.getbuffer())

                        try:
                            char_dict = create_manual_npc(
                                name=m_name,
                                role=m_role,
                                race=m_race,
                                ac=m_ac,
                                hp_max=m_hp,
                                speed=m_speed,
                                char_level=m_cr,
                                stats=stats_dict,
                                weapons=weapons_parsed,
                                features_traits=features_parsed,
                                backstory=m_backstory,
                                dnd_edition=st.session_state.dnd_edition,
                                char_portrait=img_path,
                            )

                            if save_character(char_dict):
                                char_filename = f"{char_dict['char_name'].replace(' ', '_').lower()}_{char_dict['char_id']}.json"
                                if char_filename not in vault_npcs:
                                    vault_npcs.append(char_filename)
                                    camp_data["vault_npcs"] = vault_npcs
                                    st.session_state.active_campaign_data = camp_data

                                    save_campaign(
                                        st.session_state.active_campaign_name,
                                        st.session_state.campaign_notes,
                                        sessions=camp_data.get("sessions", []),
                                        module_pdf_uri=camp_data.get("module_pdf_uri"),
                                        extracted_npcs=[],
                                        vault_npcs=vault_npcs,
                                    )
                                    st.success(
                                        f"Successfully created and added {m_name} to Vault!"
                                    )
                                    st.rerun()
                            else:
                                st.error("Failed to save manually created NPC.")
                        except Exception as e:
                            st.error(f"Error creating NPC: {e}")

        st.markdown("#### The Vault Roster")

        # Display Full Character NPCs
        if vault_npcs:
            st.markdown("##### Campaign NPCs & Monsters")
            for npc_file in vault_npcs:
                npc_data = load_character(npc_file)
                if npc_data:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
                        img_path = npc_data.get("char_portrait")
                        if img_path and os.path.exists(img_path):
                            c1.image(img_path, width=50)

                        c2.markdown(f"**{npc_data['char_name']}**")
                        c2.caption(
                            f"{npc_data['race']} {npc_data['char_class']} (Lv.{npc_data['char_level']})"
                        )

                        if c3.button("View Sheet", key=f"view_{npc_file}"):
                            show_npc_stat_block(npc_data)

                        if c4.button("To Initiative", key=f"init_v_{npc_file}"):
                            new_entry = {
                                "id": str(uuid.uuid4())[:8],
                                "name": npc_data["char_name"],
                                "init": 10,
                                "hp": int(
                                    npc_data.get("hp_max")
                                    or npc_data.get("hp_current")
                                    or 10
                                ),
                                "max_hp": int(npc_data.get("hp_max") or 10),
                                "ac": int(npc_data.get("armor_class") or 10),
                                "portrait": npc_data.get("char_portrait"),
                                "is_player": False,
                                "conditions": [],
                            }
                            if "initiative_order" not in st.session_state:
                                st.session_state.initiative_order = []
                            st.session_state.initiative_order.append(new_entry)
                            st.toast(f"Added {npc_data['char_name']} to Initiative!")

    with tab_module_lore:
        st.markdown("### Extracted Module Lore")
        camp_data = st.session_state.get("active_campaign_data", {})
        lore_content = camp_data.get("module_lore", "")

        if lore_content:
            st.markdown(lore_content)
        else:
            st.info(
                "No lore has been extracted yet. Upload an adventure module below to extract its NPCs and Lore."
            )

        with st.expander("📖 Extract from PDF Module", expanded=False):
            if camp_data.get("module_pdf_uri"):
                st.success(
                    "✅ An Adventure Module is currently loaded in the AI's memory."
                )
                if st.button("🗑️ Clear Module & Re-upload", use_container_width=True):
                    camp_data["module_pdf_uri"] = None
                    camp_data["extracted_npcs"] = []
                    st.session_state.active_campaign_data = camp_data

                    save_campaign(
                        st.session_state.active_campaign_name,
                        st.session_state.campaign_notes,
                        sessions=camp_data.get("sessions", []),
                        module_pdf_uri=None,
                        extracted_npcs=[],
                        vault_npcs=vault_npcs,
                    )
                    st.rerun()
            else:
                uploaded_pdf = st.file_uploader(
                    "Upload Adventure Module (PDF)", type=["pdf"]
                )
                if uploaded_pdf and st.button("Extract NPCs & Lore"):
                    temp_pdf_path = f"scratch/{uploaded_pdf.name}"
                    os.makedirs("scratch", exist_ok=True)
                    with open(temp_pdf_path, "wb") as f:
                        f.write(uploaded_pdf.getbuffer())

                    with st.spinner(
                        "Uploading to Gemini & Extracting... This may take a minute for large PDFs."
                    ):
                        parser = ModuleParserService()
                        g_file = parser.upload_pdf_to_gemini(temp_pdf_path)
                        camp_data["module_pdf_uri"] = g_file.name

                        extracted = parser.extract_npcs(g_file)
                        from backend.core.storage import save_character

                        for npc in extracted:
                            # 1. Download image
                            img_path = None
                            page_num = npc.get("page_number_for_art", 0)
                            if page_num > 0:
                                img_path = parser.extract_image_from_page(
                                    temp_pdf_path, page_num, npc.get("name", "Unknown")
                                )

                            # 2. Map to Character Schema
                            new_char_id = str(uuid.uuid4())[:8]
                            stats_raw = npc.get("stats", {})

                            def safe_int(val, default=10):
                                try:
                                    return int(val)
                                except (ValueError, TypeError):
                                    return default

                            stats_clean = {
                                "STR": safe_int(stats_raw.get("STR")),
                                "DEX": safe_int(stats_raw.get("DEX")),
                                "CON": safe_int(stats_raw.get("CON")),
                                "INT": safe_int(stats_raw.get("INT")),
                                "WIS": safe_int(stats_raw.get("WIS")),
                                "CHA": safe_int(stats_raw.get("CHA")),
                            }

                            weapons_raw = npc.get("weapons", [])
                            weapons_clean = []
                            for w in weapons_raw:
                                weapons_clean.append(
                                    {
                                        "name": str(w.get("name") or "Unknown Weapon"),
                                        "attack_bonus": str(
                                            w.get("attack_bonus") or "+0"
                                        ),
                                        "damage_dice": str(
                                            w.get("damage_dice") or "1d4"
                                        ),
                                        "is_custom": True,
                                    }
                                )

                            char_dict = {
                                "char_id": new_char_id,
                                "is_npc": True,
                                "char_name": npc.get("name", "Unknown NPC"),
                                "char_class": "Monster"
                                if not npc.get("role")
                                else npc.get("role")[:20],
                                "race": "Unknown",
                                "background": "Module NPC",
                                "dnd_edition": st.session_state.dnd_edition,
                                "char_level": safe_int(npc.get("char_level"), 1),
                                "armor_class": safe_int(npc.get("ac")),
                                "hp_max": safe_int(npc.get("hp_max")),
                                "speed": safe_int(npc.get("speed"), 30),
                                "stats": stats_clean,
                                "features_traits": npc.get("features_traits", []),
                                "weapons": weapons_clean,
                                "backstory": npc.get("role", ""),
                                "char_portrait": img_path,
                            }

                            if save_character(char_dict):
                                char_filename = f"{char_dict['char_name'].replace(' ', '_').lower()}_{new_char_id}.json"
                                if char_filename not in vault_npcs:
                                    vault_npcs.append(char_filename)

                        # Create a textual summary for the DM's notes
                        npc_summary = "\n\n### Extracted Module NPCs\n"
                        for npc in extracted:
                            npc_summary += f"- **{npc.get('name', 'Unknown')}**: {npc.get('role', 'Monster')} (AC {npc.get('ac', 10)}, HP {npc.get('hp_max', 10)})\n"

                        module_lore = camp_data.get("module_lore", "")
                        module_lore += npc_summary
                        camp_data["module_lore"] = module_lore

                        camp_data["vault_npcs"] = vault_npcs
                        st.session_state.active_campaign_data = camp_data

                        save_campaign(
                            st.session_state.active_campaign_name,
                            st.session_state.campaign_notes,
                            sessions=camp_data.get("sessions", []),
                            module_pdf_uri=g_file.name,
                            extracted_npcs=[],  # No longer use legacy extracted dicts
                            vault_npcs=vault_npcs,
                            module_lore=module_lore,
                        )
                        st.rerun()
