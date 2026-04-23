import logging
import streamlit as st
from dotenv import load_dotenv
from backend.ai_client import generate_ai_response, generate_ai_json
from backend.storage import (
    save_character,
    load_character,
    list_characters,
    save_campaign,
    load_campaign,
    list_campaigns,
)

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
if "char_name" not in st.session_state:
    logger.debug("Initializing default session state variables.")
    st.session_state.char_name = "Eldred the Valiant"
    st.session_state.char_class = "Paladin"
    st.session_state.char_level = 5
    st.session_state.stats = {
        "STR": 18,
        "DEX": 12,
        "CON": 15,
        "INT": 10,
        "WIS": 14,
        "CHA": 16,
    }
    st.session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get an AI recommendation based on your current stats!"
    st.session_state.encounter_result = ""
    st.session_state.campaign_notes = "The Party enters the lower levels. You need to prepare encounters for the Goblin warren."
    st.session_state.npc_result = ""


def calculate_modifier(score):
    return (score - 10) // 2


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
        char_data = {
            "char_name": st.session_state.char_name,
            "char_class": st.session_state.char_class,
            "char_level": st.session_state.char_level,
            "stats": st.session_state.stats,
        }
        if save_character(char_data):
            st.toast(f"Saved {st.session_state.char_name}!")
        else:
            st.error("Failed to save.")

    # Load Character
    available_chars = list_characters()
    if available_chars:
        char_to_load = st.selectbox(
            "Load Character", ["-- Select --"] + available_chars
        )
        if char_to_load != "-- Select --" and st.button(
            "Load Character", use_container_width=True
        ):
            data = load_character(char_to_load)
            if data:
                st.session_state.char_name = data.get("char_name", "Unknown")
                st.session_state.char_class = data.get("char_class", "Commoner")
                st.session_state.char_level = data.get("char_level", 1)
                if "stats" in data:
                    st.session_state.stats = data["stats"]
                logger.info(f"User loaded character: {char_to_load}")
                st.toast(f"Loaded {char_to_load}!")
                st.rerun()

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
        edit_mode = st.toggle("✏️ Edit Character")

        if edit_mode:
            logger.debug("User entered Character Edit Mode.")
            st.markdown("### Edit Character Details")
            col_n, col_c, col_l = st.columns([2, 2, 1])
            st.session_state.char_name = col_n.text_input(
                "Name", st.session_state.char_name
            )
            st.session_state.char_class = col_c.text_input(
                "Class", st.session_state.char_class
            )
            st.session_state.char_level = col_l.number_input(
                "Level", min_value=1, max_value=20, value=st.session_state.char_level
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

        else:
            st.markdown(f"### Active Character: **{st.session_state.char_name}**")
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

        st.markdown("---")
        st.subheader("🤖 AI Build Suggestions")
        st.info(st.session_state.build_suggestion)

        if st.button("Generate New Build Suggestion"):
            logger.info("User requested a new AI Build Suggestion.")
            with st.spinner("Consulting the AI for build options..."):
                prompt = f"""
                I am playing a Level {st.session_state.char_level} {st.session_state.char_class} in D&D 5e named {st.session_state.char_name}.
                Stats: STR {st.session_state.stats["STR"]}, DEX {st.session_state.stats["DEX"]}, CON {st.session_state.stats["CON"]},
                INT {st.session_state.stats["INT"]}, WIS {st.session_state.stats["WIS"]}, CHA {st.session_state.stats["CHA"]}.
                Give me a very short, 2-sentence creative build or multiclass suggestion for my next level up based on these specific stats.
                """
                st.session_state.build_suggestion = generate_ai_response(prompt)
                st.rerun()

    with tab2:
        st.markdown("### Forge a New Hero")
        st.write(
            "Describe your ideal character concept below. The AI will design their Level 1 starting stats, class, and name, and automatically equip them in your dashboard!"
        )

        concept = st.text_area(
            "Character Concept:",
            "A grumpy dwarven baker who uses a massive rolling pin as a weapon.",
        )

        if st.button("Generate Character", type="primary"):
            logger.info(f"User requested AI Character Forge with concept: {concept}")
            with st.spinner("Rolling stats and forging character..."):
                prompt = f"""
                Create a level 1 D&D 5e character based on this concept: "{concept}"
                You must assign them a balanced array of 6 ability scores that fit their class and race optimally.

                Output the character strictly as a JSON object with exactly the following schema:
                {{
                    "char_name": "Name of the character",
                    "char_class": "Class (e.g., Fighter, Wizard)",
                    "stats": {{
                        "STR": 15, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10
                    }}
                }}
                """

                result = generate_ai_json(prompt)

                if result and "char_name" in result:
                    logger.info(
                        f"Successfully generated and parsed new character: {result.get('char_name')}"
                    )
                    st.session_state.char_name = result.get("char_name", "Unknown")
                    st.session_state.char_class = result.get("char_class", "Commoner")
                    st.session_state.char_level = 1

                    if "stats" in result:
                        st.session_state.stats = result["stats"]

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
        st.subheader("Integrated Player Characters")
        st.info(
            "In a full backend setup, this would sync from a database. For now, it tracks the Active Character directly from the Player Dashboard."
        )
        st.write(f"**Name:** {st.session_state.char_name}")
        st.write(
            f"**Class/Level:** {st.session_state.char_class} (Lv. {st.session_state.char_level})"
        )

        passive_perception = 10 + calculate_modifier(st.session_state.stats["WIS"])
        st.write(f"**Passive Perception:** {passive_perception}")

        st.markdown("#### Ability Scores")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("STR", st.session_state.stats["STR"])
        c2.metric("DEX", st.session_state.stats["DEX"])
        c3.metric("CON", st.session_state.stats["CON"])
        c4.metric("INT", st.session_state.stats["INT"])
        c5.metric("WIS", st.session_state.stats["WIS"])
        c6.metric("CHA", st.session_state.stats["CHA"])

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
                    prompt = f"""
                    Generate a short, flavorful random encounter for a D&D 5e party of {party_size} level {avg_level} characters.
                    The setting is {location}.
                    Include the monsters, a brief description of the environment, and a small twist.
                    Format it nicely using markdown. Keep it under 150 words.
                    """
                    st.session_state.encounter_result = generate_ai_response(prompt)

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
                    prompt = f"""
                    Create a D&D 5e NPC based on: "{npc_concept}".
                    Include their Name, Race, Appearance, Personality Trait, and a secret they are hiding.
                    Format nicely with Markdown. Keep it brief and punchy.
                    """
                    st.session_state.npc_result = generate_ai_response(prompt)

            if st.session_state.npc_result:
                st.info(st.session_state.npc_result)
