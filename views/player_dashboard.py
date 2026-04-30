import streamlit as st
import logging
import uuid
from backend.ai_client import get_build_suggestion, forge_character
from backend.storage import (
    save_character,
    load_character,
    list_characters,
    delete_character,
)
from backend.state_manager import (
    get_character_dict,
    update_session_from_dict,
)
from backend.calculations import calculate_modifier
from backend.pdf_exporter import export_character_to_pdf
from backend.ui_utils import render_character_header
from backend.image_utils import generate_portrait_url
from backend.constants import (
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
)

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
            if st.button(label, width="stretch"):
                st.session_state.player_view = (
                    "forge" if st.session_state.player_view == "sheet" else "sheet"
                )
                st.rerun()
        with col3:
            if st.button("🔄 Exit Hero", width="stretch"):
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
        subclass=st.session_state.get("subclass"),
    )
    st.caption(f"📜 Ruleset: {st.session_state.dnd_edition}")

    edit_col1, edit_col2, edit_col3 = st.columns([3, 1, 1])
    edit_mode = edit_col1.toggle("✏️ Edit Mode")

    if edit_col2.button("🎨 Portrait", width="stretch"):
        with st.spinner("Forging visual identity..."):
            char_data = get_character_dict(st.session_state)
            st.session_state.char_portrait = generate_portrait_url(char_data)
            st.rerun()

    if st.session_state.char_portrait:
        with st.expander("🖼️ Portrait Preview", expanded=False):
            st.image(st.session_state.char_portrait, width="stretch")

    if edit_mode:
        if edit_col3.button("💾 Save", width="stretch"):
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
                edition=st.session_state.dnd_edition,
            )
            st.rerun()

    st.markdown("---")
    st.subheader("📄 PDF Export")

    char_dict = get_character_dict(st.session_state)
    template_path = "5E_CharacterSheet_Fillable.pdf"

    def get_pdf_bytes(data):
        return export_character_to_pdf(data, template_path)

    pdf_bytes = get_pdf_bytes(char_dict)

    if pdf_bytes:
        st.download_button(
            label="📥 Download Character PDF",
            data=pdf_bytes,
            file_name=f"{char_dict['char_name']}_Sheet.pdf",
            mime="application/pdf",
            width="stretch",
        )
    else:
        st.error("Failed to generate PDF. Please ensure the template is present.")


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
        st.session_state.subclass = c_c.text_input(
            "Subclass", getattr(st.session_state, "subclass", "")
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
            name = f.get("name", "Feature")
            desc = f.get("description", "").replace(
                "\n", "  \n"
            )  # Ensure markdown line breaks
            st.markdown(f"**{name}**  \n{desc}")
            st.divider()

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
        use_rolled = st.toggle(
            "🎲 Use Rolled Stats (instead of Standard Array)", value=False
        )

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
                    gender=forge_gender,
                    stats_mode="rolled" if use_rolled else "standard",
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
                st.session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get recommendations for your newly forged character!"
                st.rerun()

            if c_btn2.button("❌ Discard", width="stretch"):
                st.session_state.temp_forged_char = None
                st.rerun()
