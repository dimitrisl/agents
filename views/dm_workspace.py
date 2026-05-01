import streamlit as st
import logging
import uuid
from backend.ai_client import (
    forge_character,
    generate_session_prep,
    generate_npc,
    generate_random_encounter,
)
from backend.storage import (
    save_campaign,
    load_campaign,
    list_campaigns,
    list_characters,
    load_character,
)
from backend.image_utils import generate_portrait_url
from backend.calculations import calculate_modifier
from backend.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    SPECIES_2024,
    CLASSES_2024,
    ALIGNMENTS,
)

logger = logging.getLogger("DnDAssistant.DMView")


def render_dm_workspace():
    """Renders the main Dungeon Master Workspace view."""
    st.title("Dungeon Master Workspace")

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
        if col_close.button("🚪 Close Campaign", width="stretch"):
            st.session_state.active_campaign_name = None
            st.rerun()

        dm_tab1, dm_tab2, dm_tab3, dm_tab4 = st.tabs(
            [
                "📝 Campaign Notes",
                "👥 Party Tracker",
                "🎲 AI Generators",
                "⚔️ Initiative Tracker",
            ]
        )

        with dm_tab1:
            _render_campaign_notes()

        with dm_tab2:
            _render_party_tracker()

        with dm_tab3:
            _render_ai_generators()

        with dm_tab4:
            _render_initiative_tracker()


def _render_campaign_selection():
    """Renders the screen to load or create a campaign."""
    with st.container(border=True):
        st.subheader("Load Existing Campaign")
        camp_list = list_campaigns()
        if camp_list:
            selected_camp = st.selectbox("Select Campaign", camp_list)
            if st.button("Load Campaign", type="primary"):
                data = load_campaign(selected_camp)
                if data:
                    st.session_state.campaign_notes = data.get("notes", "")
                    st.session_state.active_campaign_name = selected_camp
                    logger.info(f"Loaded campaign: {selected_camp}")
                    st.toast(f"Loaded campaign: {selected_camp}")
                    st.rerun()
        else:
            st.write("No saved campaigns found.")

    with st.container(border=True):
        st.subheader("Start New Campaign")
        new_camp_name = st.text_input(
            "Campaign Name", placeholder="e.g., Curse of Strahd"
        )
        if st.button("Create Campaign"):
            if new_camp_name:
                st.session_state.active_campaign_name = new_camp_name
                st.session_state.campaign_notes = ""
                # Initialize an empty save file
                save_campaign(new_camp_name, "")
                st.rerun()
            else:
                st.warning("Please enter a campaign name.")


def _render_campaign_notes():
    """Renders the session logs and campaign management tools."""
    st.subheader("Session Logs & Lore")

    with st.expander("➕ Log New Session", expanded=False):
        new_log = st.text_area(
            "What happened in this session?", height=150, key="new_session_log"
        )
        if st.button("Append to Campaign Notes", type="primary"):
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d")
            st.session_state.campaign_notes += (
                f"\n\n--- Session: {timestamp} ---\n{new_log}"
            )
            st.toast("Session log appended!")
            st.rerun()

    st.session_state.campaign_notes = st.text_area(
        "Full Master Lore & Notes:",
        st.session_state.campaign_notes,
        height=400,
    )

    with st.container(border=True):
        st.markdown("#### Save Campaign")
        if st.button("💾 Save Notes", type="primary", width="stretch"):
            if save_campaign(
                st.session_state.active_campaign_name, st.session_state.campaign_notes
            ):
                st.toast("Notes saved successfully!")
            else:
                st.error("Failed to save notes.")

    st.markdown("---")
    st.subheader("✨ AI Session Prep")
    if st.button("Generate Next Session Prep", width="stretch"):
        party_info = (
            ", ".join(
                [
                    f"{c['char_name']} ({c['race']} {c['char_class']} Lv.{c['char_level']})"
                    for c in st.session_state.party
                ]
            )
            if st.session_state.party
            else "No party members loaded."
        )
        with st.spinner("Brainstorming plot hooks..."):
            st.session_state.session_prep_result = generate_session_prep(
                st.session_state.campaign_notes, party_info
            )

    if st.session_state.session_prep_result:
        st.info(st.session_state.session_prep_result)


def _render_party_tracker():
    """Renders the player character ingestion and tracking tools."""
    st.subheader("Party Management")

    # --- Ingestion Section ---
    with st.expander("📥 Ingest Characters from Storage", expanded=False):
        available_chars = list_characters()
        if available_chars:

            def format_char_filename(fname):
                return fname.replace(".json", "").replace("_", " ").title()

            char_to_add = st.selectbox(
                "Select Character to Add",
                available_chars,
                format_func=format_char_filename,
                key="dm_ingest_select",
            )
            if st.button("Add to Party", width="stretch"):
                char_data = load_character(char_to_add)
                if char_data:
                    if "char_id" not in char_data:
                        char_data["char_id"] = str(uuid.uuid4())[:8]
                    if any(
                        c.get("char_id") == char_data.get("char_id")
                        for c in st.session_state.party
                    ):
                        st.warning(f"{char_data['char_name']} is already in the party.")
                    else:
                        st.session_state.party.append(char_data)
                        st.success(f"Added {char_data['char_name']} to the party!")
                        st.rerun()
        else:
            st.write("No saved characters found.")

    # --- Quick Forge Section ---
    with st.expander("✨ AI Quick Forge (New Party Member)", expanded=False):
        q_edition = st.session_state.dnd_edition

        if q_edition == EDITION_2014:
            q_race_options = RACES_2014
            q_class_options = CLASSES_2014
        else:
            q_race_options = SPECIES_2024
            q_class_options = CLASSES_2024

        q_race = st.selectbox(
            "Race/Species",
            ["AI Choice"] + q_race_options,
            key="q_race",
        )
        q_class = st.selectbox(
            "Class",
            ["AI Choice"] + q_class_options,
            key="q_class",
        )
        q_level = st.number_input("Level", 1, 20, 1, key="q_level")
        q_concept = st.text_input(
            "Concept",
            placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon.",
            key="q_concept",
        )
        q_alignment = st.selectbox(
            "Alignment", ["AI Choice"] + ALIGNMENTS, key="q_alignment"
        )

        if st.button("Forge & Add", width="stretch"):
            with st.spinner("Forging..."):
                result = forge_character(
                    q_level,
                    q_race,
                    q_class,
                    "AI Choice",
                    q_concept,
                    alignment=q_alignment,
                    edition=q_edition,
                )
                if result:
                    result["char_id"] = str(uuid.uuid4())[:8]
                    st.session_state.party.append(result)
                    st.success(f"Forged and added {result['char_name']}!")
                    st.rerun()

    st.markdown("---")
    if not st.session_state.party:
        st.info("The party is currently empty. Add characters above!")
    else:
        for i, member in enumerate(st.session_state.party):
            with st.container(border=True):
                c_info, c_hp, c_ac, c_pp, c_act = st.columns([3, 1.5, 1.5, 1.5, 0.8])
                with c_info:
                    st.markdown(f"**{member['char_name']}**")
                    st.caption(
                        f"{member['race']} {member['char_class']} (Lv.{member['char_level']}) • {member.get('dnd_edition', '2014 Edition')}"
                    )
                with c_hp:
                    st.metric("HP", f"{member['hp_max']}")
                with c_ac:
                    st.metric("AC", f"{member['armor_class']}")
                with c_pp:
                    pp = 10 + calculate_modifier(member["stats"]["WIS"])
                    st.metric("Passive Perc.", f"{pp}")
                with c_act:
                    char_id = member.get("char_id", f"legacy_{i}")
                    if st.button("🗑️", key=f"remove_{char_id}_{i}"):
                        st.session_state.party.pop(i)
                        st.rerun()


def _render_ai_generators():
    """Renders the random encounter and NPC generator tools."""
    st.subheader("AI Encounter & NPC Generator")
    gen_type = st.radio("What do you need to generate?", ["Random Encounter", "NPC"])
    st.markdown("---")

    if gen_type == "Random Encounter":
        col1, col2 = st.columns(2)
        party_size = col1.number_input("Party Size", 1, 10, 4)
        avg_level = col2.number_input("Average Party Level", 1, 20, 5)
        location = st.text_input(
            "Location / Environment", "deep underground in a goblin warren"
        )

        if st.button("Generate Random Encounter"):
            with st.spinner("Generating encounter..."):
                st.session_state.encounter_result = generate_random_encounter(
                    party_size,
                    avg_level,
                    location,
                    edition=st.session_state.dnd_edition,
                )
        if st.session_state.encounter_result:
            st.success(st.session_state.encounter_result)
    else:
        npc_concept = st.text_input(
            "NPC Concept", "A sketchy merchant selling magical rings"
        )
        if st.button("Generate NPC"):
            with st.spinner("Forging NPC..."):
                st.session_state.npc_result = generate_npc(
                    npc_concept, edition=st.session_state.dnd_edition
                )
        if st.session_state.npc_result:
            st.info(st.session_state.npc_result)


def _render_initiative_tracker():
    """Renders a dynamic combat initiative tracker with a 2-phase UI (Builder & Active)."""
    st.subheader("Initiative Tracker")

    # PHASE 1: ENCOUNTER BUILDER
    if not st.session_state.get("combat_active", False):
        st.markdown("### 🛠️ Step 1: Build Encounter")
        st.info(
            "Add characters and monsters to the initiative order. When you're ready, click 'Start Combat'."
        )

        with st.container(border=True):
            col_add1, col_add2, col_add3, col_add4, col_add5 = st.columns(
                [2, 1, 1, 1, 1]
            )
            with col_add1:
                new_combatant = st.text_input("Name", key="init_new_name")
            with col_add2:
                new_init = st.number_input("Initiative", value=10, key="init_new_val")
            with col_add3:
                new_hp = st.number_input("HP", value=20, min_value=1, key="init_new_hp")
            with col_add4:
                new_ac = st.number_input("AC", value=10, min_value=1, key="init_new_ac")
            with col_add5:
                new_dex = st.number_input(
                    "DEX", value=10, min_value=1, key="init_new_dex"
                )

            c_btn1, c_btn2, c_btn3 = st.columns(3)
            if c_btn1.button("➕ Add Custom", width="stretch"):
                if new_combatant:
                    st.session_state.initiative_order.append(
                        {
                            "id": str(uuid.uuid4())[:8],
                            "name": new_combatant,
                            "init": new_init,
                            "hp": new_hp,
                            "max_hp": new_hp,
                            "ac": new_ac,
                            "dex": new_dex,
                            "portrait": None,
                        }
                    )
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    st.rerun()

            if c_btn2.button("👥 Import Party", width="stretch"):
                for member in st.session_state.party:
                    if not any(
                        c.get("name") == member["char_name"]
                        for c in st.session_state.initiative_order
                    ):
                        dex_mod = calculate_modifier(member["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": member["char_name"],
                                "init": 10 + dex_mod,
                                "hp": member["hp_max"],
                                "max_hp": member["hp_max"],
                                "ac": member["armor_class"],
                                "dex": member["stats"]["DEX"],
                                "portrait": member.get("char_portrait")
                                or generate_portrait_url(member),
                            }
                        )
                st.session_state.initiative_order.sort(
                    key=lambda x: (x["init"], x["dex"]), reverse=True
                )
                st.rerun()

            if c_btn3.button("🗑️ Clear Tracker", width="stretch"):
                st.session_state.initiative_order = []
                st.rerun()

            st.markdown("---")
            st.markdown("**Load Saved Character:**")
            available_chars = list_characters()
            if available_chars:

                def format_char_filename(fname):
                    return fname.replace(".json", "").replace("_", " ").title()

                c_load1, c_load2, c_load3 = st.columns(
                    [3, 1, 1], vertical_alignment="bottom"
                )
                char_to_add = c_load1.selectbox(
                    "Select Character",
                    available_chars,
                    format_func=format_char_filename,
                    key="init_ingest_select",
                    label_visibility="collapsed",
                )
                c_char_init = c_load2.number_input(
                    "Initiative", value=10, key="init_ingest_val"
                )
                if c_load3.button("Add", width="stretch"):
                    char_data = load_character(char_to_add)
                    if char_data:
                        if not any(
                            c.get("name") == char_data["char_name"]
                            for c in st.session_state.initiative_order
                        ):
                            st.session_state.initiative_order.append(
                                {
                                    "id": str(uuid.uuid4())[:8],
                                    "name": char_data["char_name"],
                                    "init": c_char_init,
                                    "hp": char_data["hp_max"],
                                    "max_hp": char_data["hp_max"],
                                    "ac": char_data["armor_class"],
                                    "dex": char_data["stats"]["DEX"],
                                    "portrait": char_data.get("char_portrait")
                                    or generate_portrait_url(char_data),
                                }
                            )
                            st.session_state.initiative_order.sort(
                                key=lambda x: (x["init"], x["dex"]), reverse=True
                            )
                            st.success(f"Added {char_data['char_name']}!")
                            st.rerun()
                        else:
                            st.warning(
                                f"{char_data['char_name']} is already in initiative."
                            )
            else:
                st.write("No saved characters found.")

        # Show simple list of added combatants
        if st.session_state.initiative_order:
            st.markdown("#### Pending Combatants")
            for c in st.session_state.initiative_order:
                img_tag = (
                    f'<img src="{c["portrait"]}" style="width: 30px; height: 30px; border-radius: 50%; margin-right: 10px; object-fit: cover; vertical-align: middle;">'
                    if c.get("portrait")
                    else ""
                )
                st.markdown(
                    f'<div style="margin-bottom: 8px;">{img_tag} <b>{c["init"]}</b> | {c["name"]} <span style="color: #bbb; font-size: 0.9em;">(HP: {c["hp"]}, AC: {c["ac"]}, DEX: {c["dex"]})</span></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            if st.button("⚔️ START COMBAT", type="primary", use_container_width=True):
                st.session_state.combat_active = True
                st.session_state.active_turn_index = 0
                st.rerun()

    # PHASE 2: ACTIVE COMBAT
    else:
        if not st.session_state.initiative_order:
            st.session_state.combat_active = False
            st.rerun()

        col_title, col_end = st.columns([3, 1], vertical_alignment="center")
        col_title.markdown("### ⚔️ Active Combat")
        if col_end.button("🛑 End Combat", width="stretch"):
            st.session_state.combat_active = False
            st.session_state.initiative_order = []
            st.session_state.active_turn_index = 0
            st.rerun()

        st.markdown("---")

        # Turn Controls
        t_col1, t_col2 = st.columns([4, 1], vertical_alignment="center")
        with t_col1:
            active_combatant = st.session_state.initiative_order[
                st.session_state.active_turn_index
            ]
            st.markdown(f"#### Active Turn: **{active_combatant['name']}**")
        with t_col2:
            if st.button("⏩ Next Turn", type="primary", width="stretch"):
                st.session_state.active_turn_index = (
                    st.session_state.active_turn_index + 1
                ) % len(st.session_state.initiative_order)
                st.rerun()

        st.markdown("---")

        # Render the list
        for i, c in enumerate(st.session_state.initiative_order):
            border_color = (
                "#ff4b4b" if i == st.session_state.active_turn_index else "#444"
            )
            bg_color = (
                "rgba(255, 75, 75, 0.1)"
                if i == st.session_state.active_turn_index
                else "transparent"
            )

            st.markdown(
                f"""
<div style="border: 2px solid {border_color}; background-color: {bg_color}; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
<div style="display: flex; align-items: center;">
{f'<img src="{c["portrait"]}" style="width: 50px; height: 50px; border-radius: 50%; margin-right: 15px; object-fit: cover;">' if c.get("portrait") else ""}
<div style="flex-grow: 1;">
<h4 style="margin: 0;">{c["init"]} | {c["name"]}</h4>
<span style="font-size: 0.9em; color: #bbb;">AC: <b>{c.get("ac", "?")}</b> | DEX: <b>{c.get("dex", "?")}</b></span>
</div>
</div>
</div>
""",
                unsafe_allow_html=True,
            )

            c1, c2, c3, c4 = st.columns([1, 1, 1, 0.5])

            new_hp_val = c1.number_input(
                "Current HP", value=c["hp"], key=f"hp_{c['id']}"
            )
            if new_hp_val != c["hp"]:
                c["hp"] = new_hp_val

            c2.progress(max(0.0, min(1.0, c["hp"] / max(1, c["max_hp"]))))

            if c4.button("❌", key=f"rem_{c['id']}"):
                st.session_state.initiative_order.pop(i)
                if len(st.session_state.initiative_order) == 0:
                    st.session_state.combat_active = False
                    st.session_state.active_turn_index = 0
                elif st.session_state.active_turn_index >= len(
                    st.session_state.initiative_order
                ):
                    st.session_state.active_turn_index = 0
                st.rerun()
