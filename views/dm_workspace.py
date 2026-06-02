import streamlit as st
import logging
import uuid
import os
from backend.services.forge_service import forge_character
from backend.services.dm_service import (
    generate_npc,
    generate_random_encounter,
    generate_riddle,
)
from backend.core.ai_client import generate_session_prep
from backend.services.module_parser_service import ModuleParserService
from backend.core.storage import (
    save_campaign,
    load_campaign,
    list_campaigns,
    list_characters,
    load_character,
    delete_campaign,
    save_character,
    add_roll_request,
    clear_roll_requests,
)
from backend.utils.image_utils import generate_portrait_url
from backend.utils.ui_utils import (
    render_active_roll_visual,
    get_image_base64,
    render_themed_markdown,
)
from backend.services.mechanics_service import get_modifier as calculate_modifier
from backend.core.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    SPECIES_2024,
    CLASSES_2024,
)

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

        dm_tab1, dm_tab2, dm_tab3, dm_tab4, dm_tab5 = st.tabs(
            [
                "📝 Campaign Notes",
                "👥 Party Manager",
                "📊 Party Dashboard",
                "🎲 AI Generators",
                "⚔️ Initiative Tracker",
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

    tab_overview, tab_history, tab_vault = st.tabs(
        ["Overview", "Session History", "NPC Vault"]
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
                    st.markdown("**Recap:**")
                    st.write(s.get("actual_recap", ""))
                    st.markdown("**Prep Notes:**")
                    st.write(s.get("prep_notes", ""))

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

        with st.expander("📖 Extract from PDF Module", expanded=False):
            if camp_data.get("module_pdf_uri"):
                st.success(f"Module Uploaded: {camp_data.get('module_pdf_uri')}")
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

                        camp_data["vault_npcs"] = vault_npcs
                        st.session_state.active_campaign_data = camp_data

                        save_campaign(
                            st.session_state.active_campaign_name,
                            st.session_state.campaign_notes,
                            sessions=camp_data.get("sessions", []),
                            module_pdf_uri=g_file.name,
                            extracted_npcs=[],  # No longer use legacy extracted dicts
                            vault_npcs=vault_npcs,
                        )
                        st.rerun()

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


def _render_party_tracker():
    """Renders the player character ingestion and tracking tools."""
    st.subheader("Party Management")

    active_edition = st.session_state.get("dnd_edition", "2014 Edition")
    is_active_2024 = "2024" in active_edition

    # ── Invite Players by Username ────────────────────────────────────────────
    with st.expander("👤 Invite a Player", expanded=True):
        from backend.repositories.user_repository import UserRepository as _UserRepo
        from backend.repositories.character_repository import (
            CharacterRepository as _CharRepo,
        )

        active_campaign = st.session_state.get("active_campaign_name")
        if not active_campaign:
            st.warning("No active campaign.")
        else:
            _ur = _UserRepo()
            all_users = _ur.list_all()
            dm_user = st.session_state.get("user", {})
            dm_id = dm_user.get("id", "")

            # Exclude the DM from the player list
            player_users = [
                u for u in all_users if f"local_user_{u['username']}" != dm_id
            ]

            if not player_users:
                st.info("No other registered players found.")
            else:
                user_options = {
                    u["name"]: f"local_user_{u['username']}" for u in player_users
                }
                selected_display = st.selectbox(
                    "Select Player",
                    list(user_options.keys()),
                    key="dm_invite_select_user",
                )
                selected_owner_id = user_options[selected_display]

                # Load that player's characters
                _cr = _CharRepo()
                player_chars = _cr.list_all(owner_id=selected_owner_id)

                if not player_chars:
                    st.caption(f"{selected_display} has no characters yet.")
                else:
                    char_options = {}
                    for fname in player_chars:
                        cdata = _cr.load(fname)
                        if cdata:
                            label = f"{cdata['char_name']} (Lv.{cdata.get('char_level', 1)} {cdata.get('char_class', '')})"
                            char_options[label] = (fname, cdata)

                    if char_options:
                        selected_char_label = st.selectbox(
                            "Select Character to Add",
                            list(char_options.keys()),
                            key="dm_invite_select_char",
                        )
                        sel_fname, sel_cdata = char_options[selected_char_label]

                        # Check if already in party
                        already_in = any(
                            c.get("char_id") == sel_cdata.get("char_id")
                            for c in st.session_state.party
                        )

                        if already_in:
                            st.success(
                                f"✅ {sel_cdata['char_name']} is already in the party."
                            )
                        else:
                            if st.button(
                                f"➕ Add {sel_cdata['char_name']} to Party",
                                type="primary",
                                use_container_width=True,
                                key="dm_invite_add_btn",
                            ):
                                st.session_state.party.append(sel_cdata)
                                from backend.core.storage import join_campaign

                                join_campaign(active_campaign, sel_fname)
                                st.success(
                                    f"✅ {sel_cdata['char_name']} added to party!"
                                )
                                st.rerun()

    with st.expander("📥 Ingest Characters from Storage", expanded=False):
        joined_files = st.session_state.get("campaign_party_files", [])
        if joined_files:
            st.info(f"There are {len(joined_files)} players who joined this campaign.")
            if st.button(
                "👥 Sync All Joined Players",
                key="sync_joined_btn",
                width="stretch",
            ):
                for f in joined_files:
                    char_data = load_character(f)
                    if char_data:
                        char_ed = char_data.get("dnd_edition", "2014 Edition")
                        is_char_2024 = "2024" in char_ed
                        if is_active_2024 == is_char_2024:
                            if not any(
                                c.get("char_id") == char_data.get("char_id")
                                for c in st.session_state.party
                            ):
                                st.session_state.party.append(char_data)
                st.success("Synced joined players!")
                st.rerun()
            st.markdown("---")

        available_chars = list_characters()
        if available_chars:
            filtered_chars = []
            for char_file in available_chars:
                char_data = load_character(char_file)
                if char_data:
                    if char_data.get("is_npc", False):
                        continue
                    char_ed = char_data.get("dnd_edition", "2014 Edition")
                    is_char_2024 = "2024" in char_ed
                    if is_active_2024 == is_char_2024:
                        filtered_chars.append(char_file)

            if filtered_chars:

                def format_char_filename(fname):
                    return fname.replace(".json", "").replace("_", " ").title()

                chars_to_add = st.multiselect(
                    "Select Character(s) to Add",
                    filtered_chars,
                    format_func=format_char_filename,
                    key="dm_ingest_select",
                )
                if st.button(
                    "Add Selected to Party", key="add_to_party_btn", width="stretch"
                ):
                    if not chars_to_add:
                        st.warning("Please select at least one character.")
                    else:
                        from backend.core.storage import join_campaign

                        added_names = []
                        already_in_party = []

                        for char_file in chars_to_add:
                            char_data = load_character(char_file)
                            if char_data:
                                if "char_id" not in char_data:
                                    char_data["char_id"] = str(uuid.uuid4())[:8]

                                if any(
                                    c.get("char_id") == char_data.get("char_id")
                                    for c in st.session_state.party
                                ):
                                    already_in_party.append(char_data["char_name"])
                                else:
                                    st.session_state.party.append(char_data)
                                    join_campaign(
                                        st.session_state.active_campaign_name, char_file
                                    )
                                    added_names.append(char_data["char_name"])

                        if added_names:
                            st.success(f"Successfully added: {', '.join(added_names)}")
                        if already_in_party:
                            st.warning(
                                f"Already in party: {', '.join(already_in_party)}"
                            )
                        st.rerun()
            else:
                st.info(
                    f"No characters found matching the {'2024 Revision' if is_active_2024 else '2014 Edition'}."
                )

    st.markdown("---")
    if not st.session_state.party:
        st.info("The party is currently empty.")
    else:
        for i, member in enumerate(st.session_state.party):
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 0.5])
                c1.markdown(f"**{member['char_name']}**")
                c1.caption(
                    f"{member['race']} {member['char_class']} (Lv.{member['char_level']})"
                )
                c2.metric("HP", f"{member['hp_max']}")
                c3.metric("AC", f"{member['armor_class']}")
                pp = 10 + calculate_modifier(member["stats"]["WIS"])
                c4.metric("Perc.", f"{pp}")
                if c5.button("🗑️", key=f"rem_party_{i}"):
                    from backend.core.storage import remove_from_campaign

                    char_id = member.get("char_id")
                    char_filename = f"{member['char_name'].replace(' ', '_').lower()}_{char_id}.json"

                    # Remove from the session state party
                    st.session_state.party.pop(i)

                    # Also remove from the campaign storage if it's there
                    remove_from_campaign(
                        st.session_state.active_campaign_name, char_filename
                    )

                    # Update the campaign_party_files in session state to reflect storage change
                    data = load_campaign(st.session_state.active_campaign_name)
                    if data:
                        st.session_state.campaign_party_files = data.get("party", [])

                    st.rerun()


def _render_ai_generators():
    """Renders the random encounter and NPC generator tools."""
    st.subheader("AI Generators")
    gen_type = st.radio("Type", ["Random Encounter", "NPC"], key="ai_gen_type")
    st.markdown("---")

    if gen_type == "Random Encounter":
        col1, col2, col3 = st.columns(3)
        party_size = col1.number_input("Party Size", 1, 10, 4, key="enc_p_size")
        avg_level = col2.number_input("Avg Level", 1, 20, 5, key="enc_p_level")
        difficulty_label = col3.selectbox(
            "Difficulty",
            ["Low (Χαμηλή)", "Medium (Κανονική)", "High (Υψηλή)"],
            index=1,
            key="enc_diff_label",
        )
        difficulty = difficulty_label.split(" ")[0]

        location = st.text_input("Location", "Dungeon", key="enc_loc")

        if st.button("Generate Encounter", key="gen_enc_btn", width="stretch"):
            with st.spinner("Generating Encounter..."):
                st.session_state.encounter_result = generate_random_encounter(
                    party_size,
                    avg_level,
                    location,
                    edition=st.session_state.dnd_edition,
                    difficulty=difficulty,
                )
                st.session_state.riddle_result = None  # Clear previous riddle

        if st.button(
            "✨ Generate Thematic Riddle",
            key="gen_riddle_btn",
            width="stretch",
        ):
            with st.spinner("Crafting a puzzle..."):
                st.session_state.riddle_result = generate_riddle(
                    location, edition=st.session_state.dnd_edition
                )
        if st.session_state.get("encounter_result"):
            res = st.session_state.encounter_result
            if isinstance(res, dict):
                render_themed_markdown(res.get("encounter_text", ""))
                if res.get("monsters"):
                    st.markdown("---")
                    st.markdown("#### 🧟 Monsters in this Encounter:")
                    for m in res["monsters"]:
                        qty = m.get("quantity", 1)
                        st.write(
                            f"- **{m['name']}** (x{qty}) | HP: {m.get('hp')} | AC: {m.get('ac')}"
                        )

                    if st.button(
                        "⚔️ Add Monsters to Initiative",
                        key="add_enc_to_init",
                        width="stretch",
                        type="primary",
                    ):
                        for m in res["monsters"]:
                            qty = m.get("quantity", 1)
                            for i in range(1, qty + 1):
                                name = f"{m['name']} {i}" if qty > 1 else m["name"]
                                # Basic initiative roll based on DEX
                                dex_val = m.get("dex", 10)
                                dex_mod = (dex_val - 10) // 2
                                from backend.utils.dice import quick_roll

                                init_roll, _ = quick_roll(20, dex_mod)

                                st.session_state.initiative_order.append(
                                    {
                                        "id": str(uuid.uuid4())[:8],
                                        "name": name,
                                        "init": init_roll,
                                        "hp": m.get("hp", 10),
                                        "max_hp": m.get("hp", 10),
                                        "ac": m.get("ac", 10),
                                        "dex": dex_val,
                                        "portrait": "https://img.icons8.com/color/96/monster.png",
                                        "conditions": [],
                                        "concentration": False,
                                        "statblock": m.get("statblock_summary", ""),
                                    }
                                )
                        st.session_state.initiative_order.sort(
                            key=lambda x: (x["init"], x["dex"]), reverse=True
                        )
                        st.success("Monsters added to initiative tracker!")
                        st.toast("Check the Initiative Tracker tab.")
                        st.rerun()
                else:
                    st.warning(
                        "No monsters were extracted for this encounter. You'll need to add them manually to initiative."
                    )
            else:
                # Legacy or failed JSON fallback
                render_themed_markdown(res)
                st.warning(
                    "⚠️ This encounter is in 'Legacy Format' or failed to generate monster data. Click 'Generate Encounter' again to enable the Initiative Tracker integration."
                )

        if st.session_state.get("riddle_result"):
            st.markdown("---")
            with st.container(border=True):
                st.markdown("### 🧩 The Oracle's Riddle")
                render_themed_markdown(st.session_state.riddle_result)
                if st.button("🗑️ Clear Riddle", key="clear_riddle_btn"):
                    st.session_state.riddle_result = None
                    st.rerun()
    else:
        npc_concept = st.text_input(
            "Concept", "A sketchy merchant", key="npc_concept_input"
        )
        if st.button("Generate NPC", key="gen_npc_btn"):
            with st.spinner("Forging..."):
                st.session_state.npc_result = generate_npc(
                    npc_concept, edition=st.session_state.dnd_edition
                )
        if st.session_state.get("npc_result"):
            render_themed_markdown(st.session_state.npc_result)


def _render_initiative_tracker():
    """Renders the initiative tracker (Builder & Active)."""
    st.subheader("Initiative Tracker")

    # ENCOUNTER BUILDER (Always accessible for reinforcements)
    with st.expander(
        "🛠️ Encounter Builder / Reinforcements",
        expanded=not st.session_state.get("combat_active", False),
    ):
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1, 1, 1, 1])
            name = c1.text_input(
                "Name", placeholder="e.g. Goblin", key="init_custom_name"
            )
            init = c2.number_input("Init", value=10, key="init_custom_val")
            hp = c3.number_input("HP", value=20, min_value=1, key="init_custom_hp")
            ac = c4.number_input("AC", value=10, min_value=1, key="init_custom_ac")
            dex = c5.number_input("DEX", value=10, min_value=1, key="init_custom_dex")
            qty = c6.number_input(
                "Qty", value=1, min_value=1, max_value=50, key="init_custom_qty"
            )

            b1, b2, b3 = st.columns(3)
            if b1.button("➕ Add Custom", key="add_custom_init_btn", width="stretch"):
                if name:
                    for i in range(1, qty + 1):
                        final_name = f"{name} {i}" if qty > 1 else name
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": final_name,
                                "init": init,
                                "hp": hp,
                                "max_hp": hp,
                                "ac": ac,
                                "dex": dex,
                                "portrait": "https://img.icons8.com/color/96/monster.png",
                                "conditions": [],
                                "concentration": False,
                            }
                        )
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    st.rerun()

            if b2.button(
                "👥 Import Party", key="import_party_init_btn", width="stretch"
            ):
                for member in st.session_state.party:
                    if not any(
                        c.get("name") == member["char_name"]
                        for c in st.session_state.initiative_order
                    ):
                        mod = calculate_modifier(member["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": member["char_name"],
                                "init": 10 + mod,
                                "hp": member.get("hp_max", 10),
                                "max_hp": member.get("hp_max", 10),
                                "ac": member.get("armor_class", 10),
                                "dex": member["stats"].get("DEX", 10),
                                "portrait": member.get("char_portrait"),
                                "conditions": [],
                                "concentration": False,
                            }
                        )
                st.session_state.initiative_order.sort(
                    key=lambda x: (x["init"], x["dex"]), reverse=True
                )
                st.rerun()

            if b3.button("🗑️ Clear All", key="clear_init_btn", width="stretch"):
                st.session_state.initiative_order = []
                st.session_state.combat_active = False
                st.rerun()

        st.markdown("**Load Character:**")
        lc1, lc2, lc3, lc4 = st.columns(
            [2.5, 0.8, 0.8, 0.9], vertical_alignment="bottom"
        )
        init_filtered_chars = []
        active_edition = st.session_state.get("dnd_edition", "2014 Edition")
        is_active_2024 = "2024" in active_edition
        for c_file in list_characters():
            char_data = load_character(c_file)
            if char_data:
                char_ed = char_data.get("dnd_edition", "2014 Edition")
                is_char_2024 = "2024" in char_ed
                if is_active_2024 == is_char_2024:
                    init_filtered_chars.append(c_file)

        char_file = lc1.selectbox(
            "Character", init_filtered_chars, key="load_char_init_sel"
        )
        char_qty = lc2.number_input("Qty", 1, 20, 1, key="load_char_init_qty")
        if lc3.button("Load", key="load_char_init_btn", width="stretch"):
            if char_file:
                data = load_character(char_file)
                if data:
                    for i in range(1, char_qty + 1):
                        final_name = (
                            f"{data['char_name']} {i}"
                            if char_qty > 1
                            else data["char_name"]
                        )
                        mod = calculate_modifier(data["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": final_name,
                                "init": 10 + mod,
                                "hp": data["hp_max"],
                                "max_hp": data["hp_max"],
                                "ac": data["armor_class"],
                                "dex": data["stats"]["DEX"],
                                "portrait": data.get("char_portrait"),
                                "conditions": [],
                                "concentration": False,
                            }
                        )
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    st.rerun()

        if lc4.button("Load All", key="load_all_chars_init_btn", width="stretch"):
            for c_file in init_filtered_chars:
                data = load_character(c_file)
                if data:
                    if not any(
                        c.get("name") == data["char_name"]
                        for c in st.session_state.initiative_order
                    ):
                        mod = calculate_modifier(data["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": data["char_name"],
                                "init": 10 + mod,
                                "hp": data["hp_max"],
                                "max_hp": data["hp_max"],
                                "ac": data["armor_class"],
                                "dex": data["stats"]["DEX"],
                                "portrait": data.get("char_portrait"),
                                "conditions": [],
                                "concentration": False,
                            }
                        )
            st.session_state.initiative_order.sort(
                key=lambda x: (x["init"], x["dex"]), reverse=True
            )
            st.rerun()

    if not st.session_state.get("combat_active", False):
        if st.session_state.initiative_order:
            st.markdown("---")
            st.markdown("#### 📋 Encounter Preview")
            for c in st.session_state.initiative_order:
                with st.container(border=True):
                    cp1, cp2, cp3 = st.columns([1, 4, 1])
                    p_url = c.get("portrait")
                    if not p_url or (
                        not p_url.startswith("http") and not os.path.exists(p_url)
                    ):
                        p_url = "https://img.icons8.com/color/96/monster.png"
                    cp1.image(p_url, width=40)
                    cp2.markdown(f"**{c['name']}**")
                    new_init = cp2.number_input(
                        "Initiative", value=c["init"], key=f"prev_init_{c['id']}"
                    )
                    if new_init != c["init"]:
                        c["init"] = new_init
                        st.session_state.initiative_order.sort(
                            key=lambda x: (x["init"], x["dex"]), reverse=True
                        )
                        st.rerun()

                    cp3.markdown(f"HP: {c['hp']} | AC: {c['ac']}")

            if st.button(
                "⚔️ START COMBAT",
                key="start_combat_btn",
                type="primary",
                width="stretch",
            ):
                st.session_state.combat_active = True
                st.session_state.active_turn_index = 0
                st.rerun()
    else:
        # ACTIVE COMBAT PHASE
        col_t, col_e = st.columns([3, 1])
        col_t.markdown("### ⚔️ Active Combat")
        if col_e.button("🛑 End Combat", key="end_combat_btn"):
            st.session_state.combat_active = False
            st.rerun()

        active = st.session_state.initiative_order[st.session_state.active_turn_index]

        # PREMIUM ACTIVE TURN DISPLAY
        with st.container(border=True):
            act_c1, act_c2 = st.columns([1, 4])
            p_url_active = str(active.get("portrait", ""))
            if (
                not p_url_active
                or p_url_active == "0"
                or p_url_active == "None"
                or (
                    not p_url_active.startswith("http")
                    and not os.path.exists(p_url_active)
                )
            ):
                p_url_active = "https://img.icons8.com/color/96/monster.png"
            act_c1.image(p_url_active, width=100)
            with act_c2:
                st.markdown(f"### CURRENT TURN: **{active['name']}**")
                st.markdown(
                    f"**Initiative:** {active['init']} | **AC:** {active['ac']} | **DEX:** {active['dex']}"
                )
                if st.button(
                    "⏩ NEXT TURN",
                    key="next_turn_btn",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state.active_turn_index = (
                        st.session_state.active_turn_index + 1
                    ) % len(st.session_state.initiative_order)
                    st.rerun()

        st.markdown("---")
        for i, c in enumerate(st.session_state.initiative_order):
            is_turn = i == st.session_state.active_turn_index
            border = "2px solid #ff4b4b" if is_turn else "1px solid #444"
            bg = "rgba(255, 75, 75, 0.1)" if is_turn else "transparent"

            # Sync player stats
            for p in st.session_state.party:
                if p["char_name"] == c["name"]:
                    if p.get("hp_current") is not None:
                        c["hp"] = p["hp_current"]

                    if p.get("conditions") is not None:
                        c["conditions"] = p["conditions"]

                    c["concentration"] = p.get("concentrating_on") is not None
                    if p.get("concentrating_on"):
                        c["concentrating_on"] = p.get("concentrating_on")

            # Default portrait logic
            p_url = str(c.get("portrait", ""))
            if (
                not p_url
                or p_url == "0"
                or p_url == "None"
                or (not p_url.startswith("http") and not os.path.exists(p_url))
            ):
                p_url = "https://img.icons8.com/color/96/monster.png"
            elif not p_url.startswith("http") and not p_url.startswith("data:"):
                p_url = (
                    get_image_base64(p_url)
                    or "https://img.icons8.com/color/96/monster.png"
                )

            conc_html = ""
            if c.get("concentration"):
                conc_text = c.get("concentrating_on") or "Concentrating"
                conc_html = f' <span style="color: #00ffff; margin-left: 10px; font-weight: bold;" title="{conc_text}">🧠</span>'

            with st.container():
                st.html(f"""
<div style="border: {border}; background-color: {bg}; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-family: sans-serif;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center;">
            <img src="{p_url}" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; border: 1px solid #555;">
            <div style="font-size: 1.3em; font-weight: bold; margin-right: 15px; color: #ff4b4b;">{c["init"]}</div>
            <div style="flex-grow: 1;">
                <span style="font-size: 1.1em; font-weight: bold; color: white;">{c["name"]}</span>
                {conc_html}
            </div>
        </div>
        <div style="color: #bbb; font-size: 0.9em;">AC: {c["ac"]} | DEX: {c["dex"]}</div>
    </div>
</div>
""")

                cols = st.columns([1, 1.2, 1.2, 2.5, 0.5])
                new_init = cols[0].number_input(
                    "Init",
                    value=c["init"],
                    key=f"init_act_{c['id']}_{i}",
                    label_visibility="visible",
                )
                if new_init != c["init"]:
                    c["init"] = new_init
                    # Track who is currently active to preserve their turn
                    active_id = st.session_state.initiative_order[
                        st.session_state.active_turn_index
                    ]["id"]
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    # Update active index
                    for idx, item in enumerate(st.session_state.initiative_order):
                        if item["id"] == active_id:
                            st.session_state.active_turn_index = idx
                            break
                    st.rerun()

                new_hp = cols[1].number_input(
                    "HP",
                    value=c["hp"],
                    key=f"hp_act_{c['id']}_{i}",
                    label_visibility="visible",
                )
                if new_hp != c["hp"]:
                    c["hp"] = new_hp

                cols[1].progress(max(0.0, min(1.0, c["hp"] / max(1, c["max_hp"]))))

                hp_adj = cols[2].number_input(
                    "+/- HP",
                    value=0,
                    key=f"hp_adj_{c['id']}_{i}",
                    label_visibility="visible",
                    help="Type negative for damage (e.g. -5) or positive to heal (e.g. 5) and press Enter.",
                )
                if hp_adj != 0:
                    c["hp"] = max(0, c["hp"] + hp_adj)
                    # Sync to player if player
                    for p in st.session_state.party:
                        if p["char_name"] == c["name"]:
                            p["hp_current"] = c["hp"]
                    st.session_state[f"hp_adj_{c['id']}_{i}"] = 0
                    st.rerun()

                c["conditions"] = cols[3].multiselect(
                    "Status",
                    [
                        "Blinded",
                        "Charmed",
                        "Frightened",
                        "Grappled",
                        "Invisible",
                        "Paralyzed",
                        "Poisoned",
                        "Prone",
                        "Restrained",
                        "Stunned",
                        "Unconscious",
                    ],
                    default=c.get("conditions", []),
                    key=f"cond_act_{c['id']}_{i}",
                    label_visibility="visible",
                )

                if cols[4].button("❌", key=f"rem_act_{c['id']}_{i}"):
                    st.session_state.initiative_order.pop(i)
                    if not st.session_state.initiative_order:
                        st.session_state.combat_active = False
                    st.rerun()

                r1, r2, r3, r4 = st.columns([1, 1.3, 1.3, 1.4])
                c["concentration"] = r1.toggle(
                    "Conc.",
                    value=c.get("concentration", False),
                    key=f"conc_act_{c['id']}_{i}",
                )

                if c.get("statblock"):
                    with r2.popover("📜 Stat"):
                        st.caption("Detailed Statblock:")
                        st.markdown(c["statblock"])
                        import re

                        clean_name = re.sub(r"\d+", "", c["name"]).strip()
                        slug = clean_name.lower().replace(" ", "-").replace("'", "")
                        url = f"https://www.dndbeyond.com/monsters/{slug}"
                        st.link_button("🌐 View Beyond", url, use_container_width=True)
                else:
                    r2.write("")

                with r3.popover("🎲 Roll"):
                    d_type = st.selectbox(
                        "Die", [20, 12, 10, 8, 6, 4], key=f"roll_d_{c['id']}_{i}"
                    )
                    mod = st.number_input("Mod", value=0, key=f"roll_m_{c['id']}_{i}")
                    if st.button("Roll", key=f"roll_b_{c['id']}_{i}"):
                        from backend.utils.dice import quick_roll

                        res, raw = quick_roll(d_type, mod)
                        st.session_state.active_roll = {
                            "label": f"{c['name']} - Quick Roll (d{d_type})",
                            "sides": d_type,
                            "raw": raw,
                            "modifier": mod,
                            "total": res,
                            "adv_type": "None",
                        }
                        st.rerun()

                with r4.popover("🖼️ Portrait"):
                    st.caption("Change Portrait:")
                    preview_portrait = p_url
                    if (
                        preview_portrait
                        and not preview_portrait.startswith("http")
                        and not preview_portrait.startswith("data:")
                    ):
                        preview_portrait = get_image_base64(preview_portrait)

                    if preview_portrait:
                        st.image(preview_portrait, width=80)

                    p_upload = st.file_uploader(
                        "Upload Image File",
                        type=["png", "jpg", "jpeg", "webp"],
                        key=f"port_up_{c['id']}_{i}",
                    )
                    p_text = st.text_input(
                        "Or Image URL",
                        value=c.get("portrait") or "",
                        key=f"port_txt_{c['id']}_{i}",
                    )

                    if st.button(
                        "Apply Portrait",
                        key=f"port_apply_{c['id']}_{i}",
                        use_container_width=True,
                    ):
                        target_portrait = None
                        if p_upload:
                            from backend.utils.image_utils import save_custom_portrait

                            file_ext = p_upload.name.split(".")[-1]
                            fname = f"{c['id']}_custom.{file_ext}"
                            target_portrait = save_custom_portrait(
                                p_upload.getbuffer(), fname
                            )
                        elif p_text:
                            target_portrait = p_text

                        if target_portrait:
                            c["portrait"] = target_portrait
                            # Also sync to character records
                            # 1. Active Party
                            for p in st.session_state.party:
                                if p["char_name"] == c["name"]:
                                    p["char_portrait"] = target_portrait
                                    save_character(p)
                            # 2. Campaign NPCs
                            if st.session_state.get("active_campaign_data"):
                                camp_data = st.session_state.active_campaign_data
                                vault_npcs = camp_data.get("vault_npcs", [])
                                for npc_file in vault_npcs:
                                    npc_data = load_character(npc_file)
                                    if npc_data and npc_data["char_name"] == c["name"]:
                                        npc_data["char_portrait"] = target_portrait
                                        save_character(npc_data)
                            st.success("Portrait updated!")
                            st.rerun()


def _render_roll_requests_section(tab_key: str):
    """Renders the private roll request widget for DMs to request and monitor rolls."""
    active_campaign = st.session_state.get("active_campaign_name")
    if not active_campaign:
        return

    camp_data = load_campaign(active_campaign)
    if not camp_data:
        return

    roll_requests = camp_data.get("roll_requests", [])

    # ---------------------------------------------------------
    # Auto-detection of new results (Session State tracked)
    # ---------------------------------------------------------
    if "last_seen_roll_ids" not in st.session_state:
        st.session_state.last_seen_roll_ids = set()

    current_completed_ids = {
        r["id"] for r in roll_requests if r.get("status") == "completed"
    }
    new_results = current_completed_ids - st.session_state.last_seen_roll_ids

    if new_results:
        for rid in new_results:
            req = next((r for r in roll_requests if r["id"] == rid), None)
            if req:
                st.toast(
                    f"🎲 **{req.get('char_name')}** rolled **{req.get('result')}**!"
                )
        st.session_state.last_seen_roll_ids.update(new_results)

    col_header, col_refresh = st.columns([4, 1])
    col_header.markdown("### 🎲 Private Roll Requests")
    if col_refresh.button(
        "🔄 Refresh", key=f"btn_refresh_rolls_{tab_key}", use_container_width=True
    ):
        st.rerun()

    col_req_form, col_req_log = st.columns([1, 1])

    with col_req_form:
        st.markdown("#### Send New Request")
        # 1. Select character from party
        party_members = st.session_state.party
        char_names = [m.get("char_name", "Hero") for m in party_members]

        if not char_names:
            st.warning("No players in party to request rolls from.")
        else:
            target_char_name = st.selectbox(
                "Select Character", char_names, key=f"dm_req_char_{tab_key}"
            )

            # Find the filename for this character
            target_member = next(
                (m for m in party_members if m.get("char_name") == target_char_name),
                None,
            )
            target_filename = ""
            if target_member:
                name = target_member.get("char_name", "unknown")
                cid = target_member.get("char_id", "unknown")
                target_filename = f"{name.replace(' ', '_').lower()}_{cid}.json"

            category = st.radio(
                "Roll Category",
                ["Ability Check", "Saving Throw", "Skill Check"],
                horizontal=True,
                key=f"dm_req_cat_{tab_key}",
            )

            if category == "Ability Check":
                stat_options = [
                    ("Strength (STR)", "STR"),
                    ("Dexterity (DEX)", "DEX"),
                    ("Constitution (CON)", "CON"),
                    ("Intelligence (INT)", "INT"),
                    ("Wisdom (WIS)", "WIS"),
                    ("Charisma (CHA)", "CHA"),
                ]
                selected_stat_label, selected_stat_key = st.selectbox(
                    "Select Ability",
                    stat_options,
                    format_func=lambda x: x[0],
                    key=f"dm_req_stat_ability_{tab_key}",
                )
                roll_type = f"{selected_stat_key} Check"
                stat = selected_stat_key
            elif category == "Saving Throw":
                stat_options = [
                    ("Strength (STR)", "STR"),
                    ("Dexterity (DEX)", "DEX"),
                    ("Constitution (CON)", "CON"),
                    ("Intelligence (INT)", "INT"),
                    ("Wisdom (WIS)", "WIS"),
                    ("Charisma (CHA)", "CHA"),
                ]
                selected_stat_label, selected_stat_key = st.selectbox(
                    "Select Saving Throw",
                    stat_options,
                    format_func=lambda x: x[0],
                    key=f"dm_req_stat_save_{tab_key}",
                )
                roll_type = f"{selected_stat_key} Saving Throw"
                stat = selected_stat_key
            else:
                skill_options = [
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
                selected_skill = st.selectbox(
                    "Select Skill", skill_options, key=f"dm_req_stat_skill_{tab_key}"
                )
                roll_type = f"{selected_skill} Check"
                stat = selected_skill

            reason = st.text_input(
                "Reason / Context (optional)",
                placeholder="e.g. To avoid falling rocks",
                key=f"dm_req_reason_{tab_key}",
            )

            if st.button(
                "📨 Request Private Roll",
                type="primary",
                use_container_width=True,
                key=f"btn_send_dm_req_{tab_key}",
            ):
                if target_filename:
                    success = add_roll_request(
                        active_campaign,
                        target_filename,
                        target_char_name,
                        roll_type,
                        stat,
                        reason,
                    )
                    if success:
                        st.toast(f"Sent roll request to {target_char_name}!")
                        st.rerun()
                    else:
                        st.error("Failed to send roll request.")

    with col_req_log:
        st.markdown("#### Request Log")

        @st.fragment(run_every=5)
        def render_dm_req_log_fragment():
            # Re-load campaign inside fragment to get fresh results
            fresh_camp = load_campaign(active_campaign)
            if not fresh_camp:
                st.info("No active roll requests.")
                return

            fresh_requests = fresh_camp.get("roll_requests", [])

            if not fresh_requests:
                st.info("No active roll requests.")
            else:
                for req in reversed(fresh_requests):
                    status = req.get("status", "pending")
                    char_display = req.get("char_name", "Hero")
                    roll_type_display = req.get("roll_type", "Roll")
                    reason_display = req.get("reason", "")

                    with st.container(border=True):
                        c_info, c_action = st.columns([3, 2])
                        c_info.markdown(
                            f"**{char_display}** Needs: **{roll_type_display}**"
                        )
                        if reason_display:
                            c_info.caption(f'Reason: "{reason_display}"')

                        if status == "pending":
                            c_action.markdown("⏳ **Pending**")
                        elif status == "cancelled":
                            c_action.markdown("🚫 **Cancelled**")
                        else:
                            result_display = req.get("result", "??")
                            c_action.success(f"🎲 **{result_display}**")

        render_dm_req_log_fragment()

        st.write("")
        if st.button(
            "🧹 Clear Request Log",
            use_container_width=True,
            key=f"btn_clear_roll_log_{tab_key}",
        ):
            clear_roll_requests(active_campaign)
            st.success("Roll requests cleared!")
            st.rerun()


def _render_party_dashboard():
    """Renders the high-level party overview."""
    st.subheader("Party Dashboard")
    if not st.session_state.party:
        st.info("Party is empty.")
        return

    cols = st.columns(3)
    for i, member in enumerate(st.session_state.party):
        with cols[i % 3]:
            with st.container(border=True):
                c1, c2 = st.columns([1, 2])
                import os

                portrait = member.get("char_portrait")
                if portrait and os.path.exists(portrait):
                    c1.image(portrait, width=80)
                else:
                    c1.markdown("👤")

                c2.markdown(f"#### {member.get('char_name', 'Hero')}")
                c2.caption(f"{member['race']} {member['char_class']}")

                st.markdown("---")
                s1, s2, s3 = st.columns(3)
                s1.metric("HP", f"{member.get('hp_max')}")
                s2.metric("AC", member.get("armor_class"))
                pp = 10 + calculate_modifier(member["stats"]["WIS"])
                s3.metric("Perc.", f"{pp}")

                st.markdown("**Ability Checks:**")
                r_cols = st.columns(3)
                for j, stat in enumerate(["STR", "DEX", "CON", "INT", "WIS", "CHA"]):
                    mod = calculate_modifier(member["stats"][stat])
                    mod_str = f"+{mod}" if mod >= 0 else str(mod)
                    if r_cols[j % 3].button(
                        f"{stat}\n{mod_str}", key=f"dash_roll_{stat}_{i}"
                    ):
                        from backend.utils.dice import quick_roll

                        res, raw = quick_roll(20, mod)
                        st.session_state.active_roll = {
                            "label": f"{member['char_name']} - {stat} Check",
                            "sides": 20,
                            "raw": raw,
                            "modifier": mod,
                            "total": res,
                            "adv_type": "None",
                        }
                        st.rerun()
