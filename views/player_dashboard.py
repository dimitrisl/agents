import streamlit as st
import logging
import uuid
from backend.ai_client import get_build_suggestion, forge_character
from backend.storage import save_character, load_character, list_characters
from backend.state_manager import (
    get_character_dict,
    update_session_from_dict,
    calculate_modifier,
)
from backend.pdf_exporter import export_character_to_pdf
from backend.ui_utils import render_character_header
from backend.image_utils import generate_portrait_url

logger = logging.getLogger("DnDAssistant.PlayerView")


def render_player_dashboard(accent_color: str):
    """Renders the main Player Dashboard view."""
    if not st.session_state.character_active:
        render_selection_screen()
    else:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.title("Player Dashboard")
        with col2:
            label = (
                "✨ Forge Hero"
                if st.session_state.player_view == "sheet"
                else "🛡️ View Sheet"
            )
            if st.button(label, use_container_width=True):
                st.session_state.player_view = (
                    "forge" if st.session_state.player_view == "sheet" else "sheet"
                )
                st.rerun()
        with col3:
            if st.button("🔄 Exit Hero", use_container_width=True):
                st.session_state.character_active = False
                st.rerun()

        if st.session_state.player_view == "sheet":
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
        available_chars = list_characters()
        if available_chars:

            def format_char_filename(fname):
                return fname.replace(".json", "").replace("_", " ").title()

            selected_file = st.selectbox(
                "Select Hero",
                available_chars,
                format_func=format_char_filename,
                key="selection_load",
            )
            if st.button("Equip Character", type="primary", use_container_width=True):
                char_data = load_character(selected_file)
                if char_data:
                    update_session_from_dict(st.session_state, char_data)
                    st.toast(f"Equipped {st.session_state.char_name}!")
                    st.rerun()
        else:
            st.info("No saved heroes found in the vault.")

    with col_forge:
        st.subheader("✨ Forge a New Hero")
        st.write("Let AI assist you in creating a brand new legendary character.")
        if st.button("Go to Character Forge", use_container_width=True):
            st.session_state.character_active = True
            st.session_state.player_view = "forge"
            st.rerun()


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
    )

    edit_col1, edit_col2, edit_col3 = st.columns([3, 1, 1])
    edit_mode = edit_col1.toggle("✏️ Edit Mode")

    if edit_col2.button("🎨 Portrait", use_container_width=True):
        with st.spinner("Forging visual identity..."):
            char_data = get_character_dict(st.session_state)
            st.session_state.char_portrait = generate_portrait_url(char_data)
            st.rerun()

    if st.session_state.char_portrait:
        with st.expander("🖼️ Portrait Preview", expanded=False):
            st.image(st.session_state.char_portrait, use_container_width=True)

    if edit_mode:
        if edit_col3.button("💾 Save", use_container_width=True):
            char_data = get_character_dict(st.session_state)
            if save_character(char_data):
                st.toast("Changes saved!")
            else:
                st.error("Save failed.")

    char_tab1, char_tab2, char_tab3 = st.tabs(
        ["📊 Core Stats & Skills", "⚔️ Combat & Inventory", "✨ Features & Spells"]
    )

    with char_tab1:
        _render_core_stats(edit_mode)

    with char_tab2:
        _render_combat_inventory(edit_mode)

    with char_tab3:
        _render_features_spells(edit_mode)

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

    st.markdown("---")
    st.subheader("📄 PDF Export")

    # Generate & Download in one click via cached data function
    char_dict = get_character_dict(st.session_state)
    template_path = "5E_CharacterSheet_Fillable.pdf"

    @st.cache_data(show_spinner="Generating PDF...")
    def get_pdf_bytes(data):
        import os

        os.makedirs("data/exports", exist_ok=True)
        output_filename = f"temp_{data['char_id']}.pdf"
        output_path = f"data/exports/{output_filename}"
        export_character_to_pdf(data, template_path, output_path)
        with open(output_path, "rb") as f:
            return f.read()

    st.download_button(
        label="📄 Generate & Download Character Sheet PDF",
        data=get_pdf_bytes(char_dict),
        file_name=f"{st.session_state.char_name.replace(' ', '_')}_Sheet.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


def _render_core_stats(edit_mode: bool):
    """Renders backstory, personality, ability scores, and skills."""
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
    if edit_mode:
        c_n, c_c, c_l, c_r = st.columns(4)
        st.session_state.char_name = c_n.text_input("Name", st.session_state.char_name)
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

        c_hd, c_pass = st.columns(2)
        st.session_state.hit_dice = c_hd.text_input(
            "Hit Dice", st.session_state.hit_dice
        )
        st.session_state.passive_perception = c_pass.number_input(
            "Passive Perception", 0, 30, st.session_state.passive_perception
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

        col_sk, col_sv = st.columns(2)
        with col_sk:
            st.markdown("#### Skills")
            for k, v in st.session_state.skills.items():
                st.write(f"**{k}:** {v}")
        with col_sv:
            st.markdown("#### Saving Throws")
            st.write(", ".join(st.session_state.saving_throws))


def _render_combat_inventory(edit_mode: bool):
    """Renders weapons and equipment sections."""
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


def _render_features_spells(edit_mode: bool):
    """Renders features and spellcasting sections."""
    st.markdown("#### Features & Traits")
    if edit_mode:
        st.session_state.features_traits = st.data_editor(
            st.session_state.features_traits, num_rows="dynamic", key="edit_features"
        )
    else:
        for f in st.session_state.features_traits:
            st.write(f"**{f.get('name', '')}:** {f.get('description', '')}")

    st.markdown("#### Spells")
    if edit_mode:
        cs1, cs2, cs3 = st.columns(3)
        st.session_state.spell_ability = cs1.selectbox(
            "Spellcasting Ability",
            ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
            index=["STR", "DEX", "CON", "INT", "WIS", "CHA"].index(
                st.session_state.spell_ability
            ),
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


def render_character_creator():
    """Renders the AI Character Forge interface."""
    st.markdown("### Forge a New Hero")
    st.write(
        "Select your core character pillars or let the AI decide, and provide any additional flavor to forge your hero!"
    )

    with st.container(border=True):
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
            placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon.",
        )
        use_rolled = st.toggle(
            "🎲 Use Rolled Stats (instead of Standard Array)", value=False
        )
        target_level = st.number_input(
            "Target Level", min_value=1, max_value=20, value=1
        )
        custom_name = st.text_input(
            "Character Name (Optional)", placeholder="Leave blank to let AI choose..."
        )

    if st.session_state.temp_forged_char is None:
        if st.button("Generate Character", type="primary", use_container_width=True):
            logger.info(
                f"User requested AI Character Forge: Name={custom_name}, Race={forge_race}, Class={forge_class}, Level={target_level}, Flavor={concept}"
            )
            with st.spinner("Rolling stats and forging character..."):
                result = forge_character(
                    target_level,
                    forge_race,
                    forge_class,
                    forge_background,
                    concept,
                    stats_mode="rolled" if use_rolled else "standard",
                    char_name=custom_name if custom_name else None,
                )
                if result and "char_name" in result:
                    st.session_state.temp_forged_char = result
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
                st.markdown(
                    f"**Class:** {char['char_class']} (Level {char['char_level']})"
                )
                st.markdown(
                    f"**Race:** {char['race']} | **Background:** {char['background']}"
                )
                st.markdown(f"**Backstory Snippet:** {char['backstory'][:200]}...")
            with col_p2:
                st.markdown("**Stats:**")
                stats_str = " | ".join([f"{k}:{v}" for k, v in char["stats"].items()])
                st.write(stats_str)

            if st.button("🎨 Generate AI Portrait Preview", use_container_width=True):
                with st.spinner("Forging visual identity..."):
                    portrait_url = generate_portrait_url(char)
                    # Use a temp state for forge preview
                    st.session_state.temp_portrait = portrait_url
                    st.rerun()

            if "temp_portrait" in st.session_state and st.session_state.temp_portrait:
                st.image(
                    st.session_state.temp_portrait,
                    caption="Character Portrait Preview",
                    use_container_width=True,
                )

            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button(
                "✅ Accept & Equip Hero", use_container_width=True, type="primary"
            ):
                char["char_id"] = str(uuid.uuid4())[:8]
                update_session_from_dict(st.session_state, char)
                # Apply the temp portrait if it was generated
                if "temp_portrait" in st.session_state:
                    st.session_state.char_portrait = st.session_state.temp_portrait
                    st.session_state.temp_portrait = None

                if save_character(get_character_dict(st.session_state)):
                    logger.info(f"Auto-saved new character: {char['char_name']}")
                st.session_state.temp_forged_char = None
                st.session_state.player_view = "sheet"
                st.session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get recommendations for your newly forged character!"

                st.success(
                    f"Successfully equipped and saved **{st.session_state.char_name}**!"
                )
                st.rerun()

            if c_btn2.button("❌ Discard", use_container_width=True):
                st.session_state.temp_forged_char = None
                st.rerun()
