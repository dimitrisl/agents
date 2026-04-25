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
from backend.state_manager import calculate_modifier

logger = logging.getLogger("DnDAssistant.DMView")


def render_dm_workspace():
    """Renders the main Dungeon Master Workspace view."""
    st.title("Dungeon Master Workspace")
    st.markdown("### Active Campaign: **The Sunless Citadel**")

    dm_tab1, dm_tab2, dm_tab3 = st.tabs(
        ["📝 Campaign Notes", "👥 Party Tracker", "🎲 AI Generators"]
    )

    with dm_tab1:
        _render_campaign_notes()

    with dm_tab2:
        _render_party_tracker()

    with dm_tab3:
        _render_ai_generators()


def _render_campaign_notes():
    """Renders the session logs and campaign management tools."""
    st.subheader("Session Logs & Lore")
    st.session_state.campaign_notes = st.text_area(
        "Enter your session notes, plot hooks, and lore details here:",
        st.session_state.campaign_notes,
        height=300,
    )

    with st.container(border=True):
        st.markdown("#### Load/Save Campaign")
        camp_list = list_campaigns()
        if camp_list:
            selected_camp = st.selectbox("Load Campaign", ["-- Select --"] + camp_list)
            if selected_camp != "-- Select --" and st.button(
                "Load Campaign", width="stretch"
            ):
                data = load_campaign(selected_camp)
                if data:
                    st.session_state.campaign_notes = data.get("notes", "")
                    logger.info(f"Loaded campaign notes: {selected_camp}")
                    st.toast(f"Loaded campaign: {selected_camp}")
                    st.rerun()

        col_cname, col_csave = st.columns([3, 1], vertical_alignment="bottom")
        camp_name = col_cname.text_input("Campaign Name", "The Sunless Citadel")
        if col_csave.button("Save Notes", type="primary", width="stretch"):
            if save_campaign(camp_name, st.session_state.campaign_notes):
                st.toast("Notes saved!")
            else:
                st.error("Failed to save.")

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
        q_race = st.selectbox(
            "Race",
            [
                "AI Choice",
                "Human",
                "Elf",
                "Dwarf",
                "Halfling",
                "Dragonborn",
                "Tiefling",
            ],
            key="q_race",
        )
        q_class = st.selectbox(
            "Class",
            ["AI Choice", "Fighter", "Wizard", "Rogue", "Cleric", "Paladin"],
            key="q_class",
        )
        q_level = st.number_input("Level", 1, 20, 1, key="q_level")
        q_name = st.text_input(
            "Name (Optional)", placeholder="Let AI decide...", key="q_name"
        )
        q_concept = st.text_input(
            "Concept",
            placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon.",
            key="q_concept",
        )

        if st.button("Forge & Add", width="stretch"):
            with st.spinner("Forging..."):
                result = forge_character(
                    q_level,
                    q_race,
                    q_class,
                    "AI Choice",
                    q_concept,
                    char_name=q_name if q_name else None,
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
                        f"{member['race']} {member['char_class']} (Lv.{member['char_level']})"
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
                    party_size, avg_level, location
                )
        if st.session_state.encounter_result:
            st.success(st.session_state.encounter_result)
    else:
        npc_concept = st.text_input(
            "NPC Concept", "A sketchy merchant selling magical rings"
        )
        if st.button("Generate NPC"):
            with st.spinner("Forging NPC..."):
                st.session_state.npc_result = generate_npc(npc_concept)
        if st.session_state.npc_result:
            st.info(st.session_state.npc_result)
