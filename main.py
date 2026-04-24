import logging
import uuid
import streamlit as st
from dotenv import load_dotenv
from backend.ai_client import (
    get_build_suggestion,
    forge_character,
    generate_random_encounter,
    generate_npc,
)
from backend.state_manager import (
    init_session_state,
    get_character_dict,
    update_session_from_dict,
)
from backend.calculations import calculate_modifier
from backend.storage import (
    save_character,
    load_character,
    list_characters,
    save_campaign,
    load_campaign,
    list_campaigns,
)
from backend.pdf_exporter import export_character_to_pdf

# ==========================================
# Configure Logging
# ==========================================
# This sets up both console logging and file logging (app_debug.log)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app_debug.log")],
)
logger = logging.getLogger("DnDAssistant")

logger.info("Initializing D&D AI Assistant Application...")

# Load environment variables
load_dotenv()
logger.info("Loaded environment variables.")

# Configure the page
st.set_page_config(
    page_title="D&D AI Assistant",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)
logger.info("Streamlit page configuration set.")

# ==========================================
# Initialize Session State
# ==========================================
init_session_state(st.session_state)


# ==========================================
# Sidebar Navigation
# ==========================================
with st.sidebar:
    st.title("🎲 D&D AI Assistant")
    st.markdown("---")

    view_mode = st.radio(
        "Select Mode:", ["🗡️ Player Dashboard", "🏰 Dungeon Master View"], index=0
    )
    logger.debug(f"View mode selected: {view_mode}")

    st.markdown("---")
    st.subheader("💾 Data Management")

    # Save Character
    if st.button("Save Current Character", use_container_width=True):
        char_data = get_character_dict(st.session_state)
        if save_character(char_data):
            st.toast(f"Saved {st.session_state.char_name}!")
        else:
            st.error("Failed to save.")

    # Load Character
    available_chars = list_characters()
    if available_chars:

        def format_char_filename(fname):
            if fname == "-- Select --":
                return fname
            return fname.replace(".json", "").replace("_", " ").title()

        char_to_load = st.selectbox(
            "Load Character",
            ["-- Select --"] + available_chars,
            format_func=format_char_filename,
        )
        if char_to_load != "-- Select --" and st.button(
            "Load Character", use_container_width=True
        ):
            data = load_character(char_to_load)
            if data:
                update_session_from_dict(st.session_state, data)
                logger.info(f"User loaded character: {char_to_load}")
                st.toast(f"Loaded {char_to_load}!")
                st.rerun()

    st.markdown("---")
    st.subheader("📄 PDF Export")
    if st.button("Generate Character Sheet PDF", use_container_width=True):
        char_data = get_character_dict(st.session_state)

        template_path = "5E_CharacterSheet_Fillable.pdf"
        output_filename = f"{st.session_state.char_name.replace(' ', '_')}_Sheet.pdf"

        import os

        os.makedirs("data/exports", exist_ok=True)
        output_path = f"data/exports/{output_filename}"

        with st.spinner("Generating PDF..."):
            success = export_character_to_pdf(char_data, template_path, output_path)
            if success:
                st.success("PDF Generated successfully!")
                with open(output_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=output_filename,
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.error("Failed to generate PDF. Make sure the template exists.")

    st.markdown("---")
    if st.button("✨ Reset App State", use_container_width=True):
        logger.warning("User initiated App State Reset.")
        st.session_state.clear()
        st.rerun()

# ==========================================
# Main Content
# ==========================================
if view_mode == "🗡️ Player Dashboard":
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Player Dashboard")
    with col2:
        st.write(
            f"👤 **Lv. {st.session_state.char_level} {st.session_state.char_class}**"
        )

    tab1, tab2 = st.tabs(["🛡️ Active Character", "✨ AI Character Creator"])

    with tab1:
        st.markdown(f"### Active Character: **{st.session_state.char_name}**")
        st.write(
            f"{st.session_state.race} | {st.session_state.background} | {st.session_state.alignment}"
        )

        edit_mode = st.toggle("✏️ Edit Mode")

        char_tab1, char_tab2, char_tab3 = st.tabs(
            ["📊 Core Stats & Skills", "⚔️ Combat & Inventory", "✨ Features & Spells"]
        )

        with char_tab1:
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

            if edit_mode:
                c_n, c_c, c_l, c_r = st.columns(4)
                st.session_state.char_name = c_n.text_input(
                    "Name", st.session_state.char_name
                )
                st.session_state.char_class = c_c.text_input(
                    "Class", st.session_state.char_class
                )
                st.session_state.char_level = c_l.number_input(
                    "Level", 1, 20, st.session_state.char_level
                )
                st.session_state.race = c_r.text_input("Race", st.session_state.race)

                c_b, c_a, c_hp, c_ac = st.columns(4)
                st.session_state.background = c_b.text_input(
                    "Background", st.session_state.background
                )
                st.session_state.alignment = c_a.text_input(
                    "Alignment", st.session_state.alignment
                )
                st.session_state.hp_max = c_hp.number_input(
                    "Max HP", 1, 500, st.session_state.hp_max
                )
                st.session_state.armor_class = c_ac.number_input(
                    "Armor Class", 1, 50, st.session_state.armor_class
                )

                st.markdown("#### Ability Scores")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                st.session_state.stats["STR"] = c1.number_input(
                    "STR", 1, 30, st.session_state.stats["STR"]
                )
                st.session_state.stats["DEX"] = c2.number_input(
                    "DEX", 1, 30, st.session_state.stats["DEX"]
                )
                st.session_state.stats["CON"] = c3.number_input(
                    "CON", 1, 30, st.session_state.stats["CON"]
                )
                st.session_state.stats["INT"] = c4.number_input(
                    "INT", 1, 30, st.session_state.stats["INT"]
                )
                st.session_state.stats["WIS"] = c5.number_input(
                    "WIS", 1, 30, st.session_state.stats["WIS"]
                )
                st.session_state.stats["CHA"] = c6.number_input(
                    "CHA", 1, 30, st.session_state.stats["CHA"]
                )

                st.markdown("#### Skills & Saves")
                st.session_state.skills = st.data_editor(
                    st.session_state.skills, num_rows="dynamic", key="edit_skills"
                )
                st.write("Saving Throws:", st.session_state.saving_throws)

            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Max HP", st.session_state.hp_max)
                c2.metric("Armor Class", st.session_state.armor_class)
                c3.metric("Speed", f"{st.session_state.speed} ft")
                c4.metric("Proficiency", f"+{st.session_state.proficiency_bonus}")

                st.markdown("#### Ability Scores")
                c1, c2, c3, c4, c5, c6 = st.columns(6)

                def format_mod(score):
                    mod = calculate_modifier(score)
                    return f"+{mod}" if mod >= 0 else f"{mod}"

                c1.metric(
                    "STR",
                    st.session_state.stats["STR"],
                    format_mod(st.session_state.stats["STR"]),
                )
                c2.metric(
                    "DEX",
                    st.session_state.stats["DEX"],
                    format_mod(st.session_state.stats["DEX"]),
                )
                c3.metric(
                    "CON",
                    st.session_state.stats["CON"],
                    format_mod(st.session_state.stats["CON"]),
                )
                c4.metric(
                    "INT",
                    st.session_state.stats["INT"],
                    format_mod(st.session_state.stats["INT"]),
                )
                c5.metric(
                    "WIS",
                    st.session_state.stats["WIS"],
                    format_mod(st.session_state.stats["WIS"]),
                )
                c6.metric(
                    "CHA",
                    st.session_state.stats["CHA"],
                    format_mod(st.session_state.stats["CHA"]),
                )

                col_sk, col_sv = st.columns(2)
                with col_sk:
                    st.markdown("#### Skills")
                    for k, v in st.session_state.skills.items():
                        st.write(f"**{k}:** {v}")
                with col_sv:
                    st.markdown("#### Saving Throws")
                    st.write(", ".join(st.session_state.saving_throws))

        with char_tab2:
            st.markdown("#### Weapons")
            if edit_mode:
                st.session_state.weapons = st.data_editor(
                    st.session_state.weapons, num_rows="dynamic", key="edit_weapons"
                )
            else:
                for w in st.session_state.weapons:
                    st.write(
                        f"🗡️ **{w.get('name', 'Unknown')}** | Atk: {w.get('attack_bonus', '+0')} | Dmg: {w.get('damage', '1d4')}"
                    )

            st.markdown("#### Equipment")
            if edit_mode:
                st.session_state.equipment = st.data_editor(
                    [{"item": e} for e in st.session_state.equipment],
                    num_rows="dynamic",
                    key="edit_equip",
                )
                st.session_state.equipment = [
                    i["item"] for i in st.session_state.equipment if "item" in i
                ]
            else:
                st.write(", ".join(st.session_state.equipment))

        with char_tab3:
            st.markdown("#### Features & Traits")
            if edit_mode:
                st.session_state.features_traits = st.data_editor(
                    st.session_state.features_traits,
                    num_rows="dynamic",
                    key="edit_features",
                )
            else:
                for f in st.session_state.features_traits:
                    st.write(f"**{f.get('name', '')}:** {f.get('description', '')}")

            st.markdown("#### Spells")
            if edit_mode:
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

        st.markdown("---")
        st.subheader("🤖 AI Build Suggestions")
        st.info(st.session_state.build_suggestion)

        if st.button("Generate New Build Suggestion"):
            logger.info("User requested a new AI Build Suggestion.")
            with st.spinner("Consulting the AI for build options..."):
                st.session_state.build_suggestion = get_build_suggestion(
                    st.session_state.char_level,
                    st.session_state.char_class,
                    st.session_state.char_name,
                    st.session_state.stats,
                )
                st.rerun()

    with tab2:
        st.markdown("### Forge a New Hero")
        st.write(
            "Select your core character pillars or let the AI decide, and provide any additional flavor to forge your hero!"
        )

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            forge_race = st.selectbox(
                "Race",
                [
                    "AI Choice",
                    "Human",
                    "Elf",
                    "Dwarf",
                    "Halfling",
                    "Dragonborn",
                    "Tiefling",
                    "Half-Orc",
                    "Gnome",
                ],
            )
        with col_b:
            forge_class = st.selectbox(
                "Class",
                [
                    "AI Choice",
                    "Fighter",
                    "Wizard",
                    "Rogue",
                    "Cleric",
                    "Paladin",
                    "Ranger",
                    "Barbarian",
                    "Bard",
                    "Warlock",
                    "Monk",
                    "Druid",
                    "Sorcerer",
                ],
            )
        with col_c:
            forge_background = st.selectbox(
                "Background",
                [
                    "AI Choice",
                    "Acolyte",
                    "Criminal",
                    "Folk Hero",
                    "Noble",
                    "Soldier",
                    "Sage",
                    "Charlatan",
                    "Entertainer",
                ],
            )

        concept = st.text_area(
            "Additional Flavor / Concept:",
            "A grumpy baker who uses a massive rolling pin as a weapon.",
        )
        target_level = st.number_input(
            "Target Level", min_value=1, max_value=20, value=1
        )

        if st.button("Generate Character", type="primary"):
            logger.info(
                f"User requested AI Character Forge: Race={forge_race}, Class={forge_class}, Level={target_level}, Flavor={concept}"
            )
            with st.spinner("Rolling stats and forging character..."):
                result = forge_character(
                    target_level, forge_race, forge_class, forge_background, concept
                )

                if result and "char_name" in result:
                    # Assign a new unique ID for a newly forged character
                    result["char_id"] = str(uuid.uuid4())[:8]
                    logger.info(
                        f"Successfully generated and parsed new character: {result.get('char_name')}"
                    )
                    update_session_from_dict(st.session_state, result)

                    st.session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get recommendations for your newly forged character!"
                    st.success(
                        f"Successfully forged and equipped **{st.session_state.char_name}**!"
                    )
                    st.rerun()
                else:
                    logger.error(
                        "Character generation failed or returned invalid JSON structure."
                    )
                    st.error(
                        "Failed to generate character. The AI did not return the expected format."
                    )


else:
    st.title("Dungeon Master Workspace")
    st.markdown("### Active Campaign: **The Sunless Citadel**")

    dm_tab1, dm_tab2, dm_tab3 = st.tabs(
        ["📝 Campaign Notes", "👥 Party Tracker", "🎲 AI Generators"]
    )

    with dm_tab1:
        st.subheader("Session Logs & Lore")

        # Campaign Loader
        camp_list = list_campaigns()
        if camp_list:
            selected_camp = st.selectbox("Load Campaign", ["-- Select --"] + camp_list)
            if selected_camp != "-- Select --" and st.button(
                "Load Campaign", use_container_width=True
            ):
                data = load_campaign(selected_camp)
                if data:
                    st.session_state.campaign_notes = data.get("notes", "")
                    logger.info(f"Loaded campaign notes: {selected_camp}")
                    st.toast(f"Loaded campaign: {selected_camp}")
                    st.rerun()

        st.session_state.campaign_notes = st.text_area(
            "Notes:", st.session_state.campaign_notes, height=300
        )

        col_cname, col_csave = st.columns([3, 1], vertical_alignment="bottom")
        camp_name = col_cname.text_input("Campaign Name", "The Sunless Citadel")
        if col_csave.button("Save Notes", type="primary", use_container_width=True):
            if save_campaign(camp_name, st.session_state.campaign_notes):
                logger.info(f"DM saved campaign notes for {camp_name}.")
                st.success("Notes saved to local storage!")
            else:
                st.error("Failed to save.")

    with dm_tab2:
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
                if st.button("Add to Party", use_container_width=True):
                    char_data = load_character(char_to_add)
                    if char_data:
                        # Ensure ID is present for legacy characters
                        if "char_id" not in char_data:
                            char_data["char_id"] = str(uuid.uuid4())[:8]

                        # Check if already in party
                        if any(
                            c.get("char_id") == char_data.get("char_id")
                            for c in st.session_state.party
                        ):
                            st.warning(
                                f"{char_data['char_name']} is already in the party."
                            )
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
            q_concept = st.text_input(
                "Concept", "A mysterious traveler", key="q_concept"
            )

            if st.button("Forge & Add", use_container_width=True):
                with st.spinner("Forging..."):
                    result = forge_character(
                        q_level, q_race, q_class, "AI Choice", q_concept
                    )
                    if result:
                        result["char_id"] = str(uuid.uuid4())[:8]
                        st.session_state.party.append(result)
                        st.success(f"Forged and added {result['char_name']}!")
                        st.rerun()

        st.markdown("---")

        # --- Display Section ---
        if not st.session_state.party:
            st.info("The party is currently empty. Add characters above!")
        else:
            for i, member in enumerate(st.session_state.party):
                with st.container(border=True):
                    col_info, col_stats, col_action = st.columns([3, 4, 1])

                    with col_info:
                        st.markdown(f"**{member['char_name']}**")
                        st.caption(
                            f"{member['race']} {member['char_class']} (Lv. {member['char_level']})"
                        )

                    with col_stats:
                        pp = 10 + calculate_modifier(member["stats"]["WIS"])
                        st.write(
                            f"❤️ HP: {member['hp_max']} | 🛡️ AC: {member['armor_class']} | 👁️ PP: {pp}"
                        )

                    with col_action:
                        char_id = member.get("char_id", f"legacy_{i}")
                        if st.button("❌", key=f"remove_{char_id}_{i}"):
                            st.session_state.party.pop(i)
                            st.rerun()

    with dm_tab3:
        st.subheader("AI Encounter & NPC Generator")

        gen_type = st.radio(
            "What do you need to generate?", ["Random Encounter", "NPC"]
        )
        logger.debug(f"DM Generator type selected: {gen_type}")
        st.markdown("---")

        if gen_type == "Random Encounter":
            col1, col2 = st.columns(2)
            party_size = col1.number_input("Party Size", 1, 10, 4)
            avg_level = col2.number_input("Average Party Level", 1, 20, 5)
            location = st.text_input(
                "Location / Environment", "deep underground in a goblin warren"
            )

            if st.button("Generate Random Encounter"):
                logger.info(
                    f"User requested Random Encounter for {party_size} players at level {avg_level} in '{location}'."
                )
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
                logger.info(
                    f"User requested NPC generation with concept: {npc_concept}"
                )
                with st.spinner("Forging NPC..."):
                    st.session_state.npc_result = generate_npc(npc_concept)

            if st.session_state.npc_result:
                st.info(st.session_state.npc_result)
