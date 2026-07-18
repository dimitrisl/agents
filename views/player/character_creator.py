import streamlit as st
import logging

import uuid
import os
from backend.services.forge_service import (
    forge_character,
    forge_character_manual,
)
from backend.core.state_manager import (
    get_character_dict,
    update_session_from_dict,
)
from backend.services.mechanics_service import (
    get_modifier as calculate_modifier,
)
from backend.utils.image_utils import generate_portrait_url
from backend.core.constants import (
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
    ALIGNMENTS,
)

from views.player._helpers import trigger_sync

logger = logging.getLogger(__name__)


def render_character_creator():
    """Renders the AI Character Forge and Manual Character Builder interfaces with dynamic edition-based options."""
    st.markdown("### Forge a New Hero")

    if st.session_state.temp_forged_char is None:
        tab_ai, tab_manual = st.tabs(
            ["✨ AI Character Forge", "🛠️ Manual Character Builder"]
        )

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

        with tab_ai:
            st.write(
                "Choose your D&D edition first, then select your core pillars or let the AI decide!"
            )
            with st.container(border=True):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    forge_race = st.selectbox(
                        race_label,
                        ["AI Choice"] + race_options,
                        key="forge_race_ai",
                    )
                with col_b:
                    forge_class = st.selectbox(
                        "Class",
                        ["AI Choice"] + class_options,
                        key="forge_class_ai",
                    )
                with col_c:
                    forge_background = st.selectbox(
                        "Background",
                        ["AI Choice"] + bg_options,
                        key="forge_background_ai",
                    )

                col_lvl, col_g, col_sub = st.columns(3)
                with col_lvl:
                    forge_level = st.number_input(
                        "Target Level",
                        min_value=1,
                        max_value=20,
                        value=1,
                        key="forge_level_ai",
                    )
                with col_g:
                    forge_gender_selected = st.selectbox(
                        "Gender",
                        ["AI Choice"] + GENDERS,
                        key="forge_gender_selected_ai",
                    )
                    if forge_gender_selected == "Other":
                        forge_gender = st.text_input(
                            "Specify Gender",
                            placeholder="e.g. Agender, Fluid",
                            key="forge_gender_other_ai",
                        )
                    else:
                        forge_gender = forge_gender_selected

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
                        forge_subclass = st.selectbox(
                            "Subclass", subclass_options, key="forge_subclass_ai"
                        )
                    else:
                        st.info("Subclass unlocks at higher levels.")
                        forge_subclass = None

                concept = st.text_area(
                    "Additional Flavor / Concept:",
                    placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon.",
                    height=100,
                    key="concept_ai",
                )
                col_name, col_align, col_rolled = st.columns([2, 1, 1])
                with col_name:
                    forge_name = st.text_input(
                        "Character Name (optional)",
                        placeholder="AI Choice",
                        key="forge_name_ai",
                    )
                with col_align:
                    forge_alignment = st.selectbox(
                        "Alignment",
                        ["AI Choice"] + ALIGNMENTS,
                        key="forge_alignment_ai",
                    )
                with col_rolled:
                    use_rolled = st.toggle(
                        "🎲 Use Rolled Stats",
                        value=False,
                        help="Roll 4d6 and drop the lowest die for each of the six ability scores (Classic D&D Method). If disabled, standard array (15, 14, 13, 12, 10, 8) will be used.",
                        key="use_rolled_ai",
                    )

                if use_rolled:
                    st.info(
                        "**Classic Rolling Method (4d6 drop lowest):**  \n"
                        "The AI will simulate rolling four 6-sided dice for each ability score and discarding the lowest value. "
                        "This typically results in a more organic (and often more powerful) stat array than the Standard Array, "
                        "but carries the risk of lower-than-average scores."
                    )

            if st.button(
                "Generate Character",
                type="primary",
                width="stretch",
                key="ai_submit_button",
            ):
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
                        name=forge_name if forge_name.strip() else "AI Choice",
                        gender=forge_gender,
                        stats_mode="rolled" if use_rolled else "standard",
                        alignment=forge_alignment,
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

        with tab_manual:
            st.write(
                "Build your character step-by-step manually. The system will handle all the rules calculations!"
            )
            with st.container(border=True):
                # 1. Basic Info
                col_m_name, col_m_level, col_m_gender = st.columns([2, 1, 1])
                with col_m_name:
                    manual_name = st.text_input(
                        "Character Name", value="New Hero", key="manual_name"
                    )
                with col_m_level:
                    manual_level = st.number_input(
                        "Level", min_value=1, max_value=20, value=1, key="manual_level"
                    )
                with col_m_gender:
                    manual_gender_selected = st.selectbox(
                        "Gender", GENDERS, key="manual_gender_selected"
                    )
                    if manual_gender_selected == "Other":
                        manual_gender = st.text_input(
                            "Specify Gender",
                            placeholder="e.g. Agender, Fluid",
                            key="manual_gender_other",
                        )
                    else:
                        manual_gender = manual_gender_selected

                # 2. Pillars
                col_m_race, col_m_class, col_m_bg = st.columns(3)
                with col_m_race:
                    manual_race = st.selectbox(
                        f"{race_label}", race_options, key="manual_race"
                    )
                with col_m_class:
                    manual_class = st.selectbox(
                        "Class", class_options, key="manual_class"
                    )
                with col_m_bg:
                    manual_background = st.selectbox(
                        "Background", bg_options, key="manual_background"
                    )

                col_m_align, col_m_sub = st.columns(2)
                with col_m_align:
                    manual_alignment = st.selectbox(
                        "Alignment", ALIGNMENTS, key="manual_alignment"
                    )

                # Subclass Logic
                manual_subclass_options = ["None"]
                show_manual_subclass = False

                # 2024 rules: Subclass always at level 3
                if forge_edition == EDITION_2024:
                    if manual_level >= 3:
                        show_manual_subclass = True
                        manual_subclass_options += subclass_map.get(manual_class, [])
                # 2014 rules: Subclass level varies
                else:
                    sub_lvls = {
                        "Cleric": 1,
                        "Sorcerer": 1,
                        "Warlock": 1,
                        "Wizard": 2,
                        "Druid": 2,
                    }
                    req_lvl = sub_lvls.get(manual_class, 3)
                    if manual_level >= req_lvl:
                        show_manual_subclass = True
                        manual_subclass_options += subclass_map.get(manual_class, [])

                with col_m_sub:
                    if show_manual_subclass:
                        manual_subclass = st.selectbox(
                            "Subclass", manual_subclass_options, key="manual_subclass"
                        )
                    else:
                        st.info("Subclass unlocks at higher levels.")
                        manual_subclass = "None"

                # Concept
                manual_concept = st.text_area(
                    "Additional Flavor / Concept / Backstory Idea:",
                    placeholder="E.g., A dwarf blacksmith who wants to find the legendary forge of his ancestors.",
                    height=100,
                    key="manual_concept",
                )

                st.markdown("---")
                st.markdown("#### 🎲 Base Ability Scores")
                stat_method = st.selectbox(
                    "Ability Score Allocation Method",
                    [
                        "Standard Array (15, 14, 13, 12, 10, 8)",
                        "Roll for Stats (4d6 drop lowest)",
                        "Manual Entry / Custom",
                    ],
                    key="manual_stat_method",
                )

                if stat_method.startswith("Standard Array"):
                    col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
                    val_options = [15, 14, 13, 12, 10, 8]
                    with col_s1:
                        s_str = st.selectbox(
                            "STR", val_options, index=0, key="manual_arr_str"
                        )
                    with col_s2:
                        s_dex = st.selectbox(
                            "DEX", val_options, index=1, key="manual_arr_dex"
                        )
                    with col_s3:
                        s_con = st.selectbox(
                            "CON", val_options, index=2, key="manual_arr_con"
                        )
                    with col_s4:
                        s_int = st.selectbox(
                            "INT", val_options, index=3, key="manual_arr_int"
                        )
                    with col_s5:
                        s_wis = st.selectbox(
                            "WIS", val_options, index=4, key="manual_arr_wis"
                        )
                    with col_s6:
                        s_cha = st.selectbox(
                            "CHA", val_options, index=5, key="manual_arr_cha"
                        )

                    stats_assigned = [s_str, s_dex, s_con, s_int, s_wis, s_cha]
                    is_stat_valid = len(set(stats_assigned)) == 6
                    if not is_stat_valid:
                        st.warning(
                            "⚠️ Each standard array value (15, 14, 13, 12, 10, 8) must be assigned to exactly one ability score."
                        )

                elif stat_method.startswith("Roll for Stats"):
                    if st.button(
                        "🎲 Roll 6 Stats (4d6 drop lowest)", key="manual_roll_button"
                    ):
                        import random

                        rolled = []
                        for _ in range(6):
                            rolls = [random.randint(1, 6) for _ in range(4)]
                            rolls.sort()
                            rolled.append(sum(rolls[1:]))
                        st.session_state.manual_rolled_stats = rolled

                    if "manual_rolled_stats" in st.session_state:
                        rolled_vals = st.session_state.manual_rolled_stats
                        st.write(
                            f"Rolled Scores: **{', '.join(map(str, sorted(rolled_vals, reverse=True)))}**"
                        )

                        col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
                        with col_s1:
                            s_str = st.selectbox(
                                "STR", rolled_vals, index=0, key="manual_roll_str"
                            )
                        with col_s2:
                            s_dex = st.selectbox(
                                "DEX", rolled_vals, index=1, key="manual_roll_dex"
                            )
                        with col_s3:
                            s_con = st.selectbox(
                                "CON", rolled_vals, index=2, key="manual_roll_con"
                            )
                        with col_s4:
                            s_int = st.selectbox(
                                "INT", rolled_vals, index=3, key="manual_roll_int"
                            )
                        with col_s5:
                            s_wis = st.selectbox(
                                "WIS", rolled_vals, index=4, key="manual_roll_wis"
                            )
                        with col_s6:
                            s_cha = st.selectbox(
                                "CHA", rolled_vals, index=5, key="manual_roll_cha"
                            )

                        stats_assigned = [s_str, s_dex, s_con, s_int, s_wis, s_cha]
                        from collections import Counter

                        is_stat_valid = Counter(stats_assigned) == Counter(rolled_vals)
                        if not is_stat_valid:
                            st.warning(
                                "⚠️ Please assign each rolled score exactly once."
                            )
                    else:
                        st.info(
                            "Click the button above to roll your six ability scores."
                        )
                        is_stat_valid = False
                        s_str = s_dex = s_con = s_int = s_wis = s_cha = 10

                else:
                    col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
                    with col_s1:
                        s_str = st.number_input(
                            "STR",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_str",
                        )
                    with col_s2:
                        s_dex = st.number_input(
                            "DEX",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_dex",
                        )
                    with col_s3:
                        s_con = st.number_input(
                            "CON",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_con",
                        )
                    with col_s4:
                        s_int = st.number_input(
                            "INT",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_int",
                        )
                    with col_s5:
                        s_wis = st.number_input(
                            "WIS",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_wis",
                        )
                    with col_s6:
                        s_cha = st.number_input(
                            "CHA",
                            min_value=3,
                            max_value=30,
                            value=10,
                            key="manual_custom_cha",
                        )
                    is_stat_valid = True

                st.markdown("##### 📈 Ability Score Adjustments (Race / Background)")
                st.write(
                    "Apply D&D racial or background bonuses (+2 to one stat, +1 to another, or +1 to three stats)."
                )

                col_adj1, col_adj2, col_adj3 = st.columns(3)
                with col_adj1:
                    adj_plus_2 = st.selectbox(
                        "+2 Bonus to:",
                        ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                        index=0,
                        key="manual_adj_plus_2",
                    )
                with col_adj2:
                    adj_plus_1 = st.selectbox(
                        "+1 Bonus to:",
                        ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                        index=0,
                        key="manual_adj_plus_1",
                    )
                with col_adj3:
                    adj_plus_1_alt = st.selectbox(
                        "Alternative +1 Bonus to:",
                        ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                        index=0,
                        key="manual_adj_plus_1_alt",
                    )

                # Calculate final stats
                final_str = (
                    s_str
                    + (2 if adj_plus_2 == "STR" else 0)
                    + (1 if adj_plus_1 == "STR" else 0)
                    + (1 if adj_plus_1_alt == "STR" else 0)
                )
                final_dex = (
                    s_dex
                    + (2 if adj_plus_2 == "DEX" else 0)
                    + (1 if adj_plus_1 == "DEX" else 0)
                    + (1 if adj_plus_1_alt == "DEX" else 0)
                )
                final_con = (
                    s_con
                    + (2 if adj_plus_2 == "CON" else 0)
                    + (1 if adj_plus_1 == "CON" else 0)
                    + (1 if adj_plus_1_alt == "CON" else 0)
                )
                final_int = (
                    s_int
                    + (2 if adj_plus_2 == "INT" else 0)
                    + (1 if adj_plus_1 == "INT" else 0)
                    + (1 if adj_plus_1_alt == "INT" else 0)
                )
                final_wis = (
                    s_wis
                    + (2 if adj_plus_2 == "WIS" else 0)
                    + (1 if adj_plus_1 == "WIS" else 0)
                    + (1 if adj_plus_1_alt == "WIS" else 0)
                )
                final_cha = (
                    s_cha
                    + (2 if adj_plus_2 == "CHA" else 0)
                    + (1 if adj_plus_1 == "CHA" else 0)
                    + (1 if adj_plus_1_alt == "CHA" else 0)
                )

                st.markdown("**Final Ability Scores (Base + Adjustments):**")

                def display_stat(label, val):
                    mod = calculate_modifier(val)
                    mod_str = f"+{mod}" if mod >= 0 else str(mod)
                    return f"**{label}**: {val} ({mod_str})"

                st.write(
                    " | ".join(
                        [
                            display_stat("STR", final_str),
                            display_stat("DEX", final_dex),
                            display_stat("CON", final_con),
                            display_stat("INT", final_int),
                            display_stat("WIS", final_wis),
                            display_stat("CHA", final_cha),
                        ]
                    )
                )

                st.markdown("---")
                st.markdown("#### 🛡️ Proficiencies & Spellcasting")

                # Saving Throws (class-suggested defaults)
                class_saves = {
                    "Barbarian": ["STR", "CON"],
                    "Bard": ["DEX", "CHA"],
                    "Cleric": ["WIS", "CHA"],
                    "Druid": ["INT", "WIS"],
                    "Fighter": ["STR", "CON"],
                    "Monk": ["STR", "DEX"],
                    "Paladin": ["WIS", "CHA"],
                    "Ranger": ["STR", "DEX"],
                    "Rogue": ["DEX", "INT"],
                    "Sorcerer": ["CON", "CHA"],
                    "Warlock": ["WIS", "CHA"],
                    "Wizard": ["INT", "WIS"],
                    "Artificer": ["CON", "INT"],
                }
                default_saves = class_saves.get(manual_class, [])
                manual_saves = st.multiselect(
                    "Saving Throw Proficiencies",
                    ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
                    default=default_saves,
                    key=f"manual_saves_{manual_class}",
                )

                # Skill Proficiencies
                all_skills_list = [
                    "Athletics",
                    "Acrobatics",
                    "Sleight of Hand",
                    "Stealth",
                    "Arcana",
                    "History",
                    "Investigation",
                    "Nature",
                    "Religion",
                    "Animal Handling",
                    "Insight",
                    "Medicine",
                    "Perception",
                    "Survival",
                    "Deception",
                    "Intimidation",
                    "Performance",
                    "Persuasion",
                ]
                st.write(
                    "💡 *Tip: Classes typically grant 2 skill proficiencies (Rogue grants 4, Bard/Ranger grant 3) and Backgrounds typically grant 2.*"
                )
                manual_skills = st.multiselect(
                    "Skill Proficiencies",
                    all_skills_list,
                    default=[],
                    key="manual_skills",
                )

                # Spellcasting Ability
                class_spell_abilities = {
                    "Wizard": "INT",
                    "Artificer": "INT",
                    "Cleric": "WIS",
                    "Druid": "WIS",
                    "Ranger": "WIS",
                    "Bard": "CHA",
                    "Paladin": "CHA",
                    "Sorcerer": "CHA",
                    "Warlock": "CHA",
                }
                default_spell_ability = class_spell_abilities.get(manual_class, "None")
                manual_spell_ability = st.selectbox(
                    "Spellcasting Ability Modifier",
                    ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                    index=["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"].index(
                        default_spell_ability
                    ),
                    key=f"manual_spell_ability_{manual_class}",
                )

            submit_disabled = not is_stat_valid or not manual_name.strip()
            if st.button(
                "Create Character",
                type="primary",
                width="stretch",
                disabled=submit_disabled,
                key="manual_submit_button",
            ):
                final_stats_dict = {
                    "STR": final_str,
                    "DEX": final_dex,
                    "CON": final_con,
                    "INT": final_int,
                    "WIS": final_wis,
                    "CHA": final_cha,
                }
                with st.spinner("Compiling rules and manual forge..."):
                    result = forge_character_manual(
                        target_level=manual_level,
                        race=manual_race,
                        char_class=manual_class,
                        background=manual_background,
                        subclass=manual_subclass if manual_subclass != "None" else None,
                        alignment=manual_alignment,
                        gender=manual_gender,
                        name=manual_name,
                        base_stats=final_stats_dict,
                        skill_proficiencies=manual_skills,
                        saving_throws=manual_saves,
                        spell_ability=manual_spell_ability
                        if manual_spell_ability != "None"
                        else None,
                        concept=manual_concept,
                        edition=forge_edition,
                    )
                    if result and "char_name" in result:
                        result["char_portrait"] = generate_portrait_url(result)
                        st.session_state.temp_forged_char = result
                        st.session_state.temp_portrait = result["char_portrait"]
                        st.rerun()
                    else:
                        st.error(
                            "Failed to generate character. Please check inputs and try again."
                        )
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
                    portrait_url = generate_portrait_url(char, force=True)
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
                trigger_sync()
                if "temp_portrait" in st.session_state:
                    st.session_state.char_portrait = st.session_state.temp_portrait
                    st.session_state.temp_portrait = None

                saved_dict = get_character_dict(st.session_state)
                logger.info(f"Auto-saved new character: {char['char_name']}")
                st.session_state.last_saved_char = saved_dict.copy()
                st.session_state.temp_forged_char = None
                st.session_state.player_view = "sheet"
                st.session_state.edit_mode = True
                st.rerun()

            if c_btn2.button("❌ Discard", width="stretch"):
                # Clean up the portrait if discarded
                if (
                    "temp_portrait" in st.session_state
                    and st.session_state.temp_portrait
                ):
                    try:
                        if os.path.exists(st.session_state.temp_portrait):
                            os.remove(st.session_state.temp_portrait)
                            logger.info(
                                f"Cleaned up discarded portrait: {st.session_state.temp_portrait}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to clean up discarded portrait: {e}")

                st.session_state.temp_forged_char = None
                st.session_state.temp_portrait = None
                st.rerun()
