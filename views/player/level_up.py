import streamlit as st
import logging

from backend.services.forge_service import (
    analyze_level_up,
)
from backend.services.rules_service import (
    analyze_feat,
)
from backend.core.state_manager import (
    get_character_dict,
)
from backend.services.mechanics_service import (
    get_level_up_vitals,
    check_progression_features,
)
from backend.core.constants import (
    EDITION_2014,
    EDITION_2024,
)

from views.player._helpers import trigger_sync

logger = logging.getLogger(__name__)


def run_level_up_wizard():
    """Manual-first guide for leveling up with optional AI support and preview/revert."""
    target_lv = st.session_state.char_level + 1

    # Initialize Temp State for Level Up if not present
    if "lv_up_temp" not in st.session_state:
        st.session_state.lv_up_temp = {
            "hp_inc": 0,
            "hp_method": "Fixed (Average)",
            "asi_feat_choice": "Ability Score Improvement",
            "stats_raised": [],
            "selected_feat": None,
            "new_features": [],
            "ai_consulted": False,
            "selected_spells": [],
            "selected_spells_data": [],
        }

    temp = st.session_state.lv_up_temp

    st.markdown(f"### Elevating to Level {target_lv}")

    # STEP 1: Vitals (HP)
    st.markdown("#### 💓 Step 1: Vital Stats")

    vitals = get_level_up_vitals(
        st.session_state.char_class,
        st.session_state.char_level,
        st.session_state.stats.get("CON", 10),
        st.session_state.dnd_edition,
        st.session_state.get("features_traits", []),
    )

    die_size = vitals["die_size"]
    con_mod = vitals["con_mod"]
    avg_hp = vitals["average_hp_gain"]

    hp_col1, hp_col2 = st.columns([1, 1])
    temp["hp_method"] = hp_col1.radio(
        "HP Increase Method:",
        ["Fixed (Average)", "Roll for it!"],
        horizontal=True,
        index=0 if temp["hp_method"] == "Fixed (Average)" else 1,
    )

    if temp["hp_method"] == "Fixed (Average)":
        temp["hp_inc"] = avg_hp
        hp_col2.info(f"Adding average HP: **+{avg_hp}**")
    else:
        if "lv_up_hp_roll" not in st.session_state:
            extra_hp = vitals.get("hp_bonus_per_level", 0)
            total_bonus = con_mod + extra_hp
            bonus_str = f" + {total_bonus}" if total_bonus != 0 else ""
            if hp_col2.button(f"🎲 Roll 1d{die_size}{bonus_str}"):
                import random

                roll = random.randint(1, die_size)
                st.session_state.lv_up_hp_roll = max(1, roll + total_bonus)
                st.rerun()
        if "lv_up_hp_roll" in st.session_state:
            temp["hp_inc"] = st.session_state.lv_up_hp_roll
            hp_col2.success(f"🎲 Rolled: **+{temp['hp_inc']}**")
            if hp_col2.button("🔄 Re-roll"):
                del st.session_state.lv_up_hp_roll
                st.rerun()

    # STEP 2: ASI or Feat (Backend driven)
    progression = check_progression_features(
        st.session_state.char_class, target_lv, st.session_state.dnd_edition
    )
    is_asi_level = progression["is_asi_level"]

    if is_asi_level:
        st.markdown("---")
        st.markdown("#### ⚖️ Step 2: Ability Score Improvement or Feat")
        temp["asi_feat_choice"] = st.radio(
            "Choose your benefit:",
            ["Ability Score Improvement", "Feat"],
            horizontal=True,
        )

        if temp["asi_feat_choice"] == "Ability Score Improvement":
            st.info(
                "💡 **Tip:** To increase a single ability score by **+2**, select the same stat in both dropdowns."
            )
            col_s1, col_s2 = st.columns(2)
            s1 = col_s1.selectbox(
                "Stat 1 (+1)", ["STR", "DEX", "CON", "INT", "WIS", "CHA"], key="asi_s1"
            )
            s2 = col_s2.selectbox(
                "Stat 2 (+1)", ["STR", "DEX", "CON", "INT", "WIS", "CHA"], key="asi_s2"
            )
            temp["stats_raised"] = [s1, s2]

            # Validate that stats do not exceed 20
            current_stats = st.session_state.stats
            raised_stats = {}
            for stat in temp["stats_raised"]:
                raised_stats[stat] = raised_stats.get(stat, 0) + 1

            for stat, increase in raised_stats.items():
                current_val = current_stats.get(stat, 10)
                if current_val + increase > 20:
                    st.warning(
                        f"⚠️ **Rule Warning:** Increasing {stat} from {current_val} to {current_val + increase} exceeds the standard D&D limit of **20**."
                    )
        else:
            from backend.repositories.rules_repository import RulesRepository

            rules_repo = RulesRepository()
            all_feats = rules_repo.get_all_feats(st.session_state.dnd_edition)
            feat_map = {f["name"]: f for f in all_feats}
            feat_names = list(feat_map.keys())

            temp["selected_feat"] = st.selectbox("Select Feat:", options=feat_names)

            # --- Prerequisite Validation ---
            selected_feat_data = feat_map.get(temp["selected_feat"], {})
            prereqs = selected_feat_data.get("prerequisites", {})
            if isinstance(prereqs, dict):
                prereq_warnings = []
                min_lvl = prereqs.get("min_level", 0)
                if min_lvl > 0 and target_lv < min_lvl:
                    prereq_warnings.append(
                        f"Requires **Level {min_lvl}+** (you will be Level {target_lv})"
                    )
                stat_reqs = prereqs.get("stat_requirements", {})
                current_stats = st.session_state.stats
                for stat_key, min_val in stat_reqs.items():
                    char_val = current_stats.get(stat_key, 10)
                    if char_val < min_val:
                        prereq_warnings.append(
                            f"Requires **{stat_key} {min_val}+** (yours is {char_val})"
                        )
                other_reqs = prereqs.get("other", [])
                if other_reqs:
                    prereq_warnings.append(
                        f"Other requirements: {', '.join(other_reqs)}"
                    )
                if prereq_warnings:
                    st.warning(
                        "⚠️ **Prerequisite Warning:**\n- " + "\n- ".join(prereq_warnings)
                    )

            # --- Sync Feat Mechanics ---
            if st.button("🔍 Sync Feat Mechanics"):
                with st.spinner(
                    f"Consulting the Oracle about {temp['selected_feat']}..."
                ):
                    analysis = analyze_feat(
                        temp["selected_feat"], st.session_state.dnd_edition
                    )
                    temp["feat_analysis"] = analysis

                    # Apply automated HP bonuses (e.g. Tough)
                    hp_per_lvl = analysis.get("hp_bonus_per_level", 0)
                    if hp_per_lvl > 0:
                        extra_hp = hp_per_lvl * target_lv
                        temp["hp_inc"] += extra_hp
                        st.success(
                            f"📈 Applied +{extra_hp} HP from {temp['selected_feat']}!"
                        )

                    # Suggest stat bonus
                    if analysis.get("has_stat_choice"):
                        st.info(
                            f"💡 This feat allows a +1 to: {', '.join(analysis.get('stat_choice_options', []))}"
                        )
                    elif any(v > 0 for v in analysis.get("stat_bonus", {}).values()):
                        bonus_stats = [
                            k
                            for k, v in analysis.get("stat_bonus", {}).items()
                            if v > 0
                        ]
                        st.success(
                            f"💡 This feat gives a +1 to: {', '.join(bonus_stats)}"
                        )

            # Support for Feats that provide an Ability Score Increase (+1)
            feat_desc = feat_map.get(temp["selected_feat"], {}).get("description", "")
            has_stat_increase = (
                "increase your" in feat_desc.lower()
                and "score by 1" in feat_desc.lower()
            )

            # Determine index for the selectbox
            default_index = 0  # "None"
            if "feat_analysis" in temp:
                analysis = temp["feat_analysis"]
                bonus_stats = [
                    k for k, v in analysis.get("stat_bonus", {}).items() if v > 0
                ]
                if bonus_stats:
                    stat_options = ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
                    if bonus_stats[0] in stat_options:
                        default_index = stat_options.index(bonus_stats[0])

            if has_stat_increase or st.session_state.dnd_edition == EDITION_2024:
                feat_stat = st.selectbox(
                    "Feat Stat Bonus (+1):",
                    ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"],
                    index=default_index,
                    key="feat_stat_bonus",
                    help="Some feats (like Resilient) allow you to increase an ability score by 1. Select the stat here.",
                )
                temp["feat_stat_bonus"] = feat_stat if feat_stat != "None" else None
            else:
                # For feats like Tough that have NO stat bonus, we hide the selector
                temp["feat_stat_bonus"] = None

            # Show description of selected feat
            if temp["selected_feat"]:
                selected_feat_data = feat_map.get(temp["selected_feat"])
                if selected_feat_data:
                    with st.expander("Feat Details", expanded=False):
                        desc = selected_feat_data.get(
                            "description", "No description available."
                        )
                        st.write(desc)

                        # Removed AI completion button to avoid meta-text
                    temp["selected_feat_desc"] = selected_feat_data.get(
                        "description", ""
                    )

    # STEP 2b: Choose Subclass (Required if level up crosses the subclass choice level)
    edition = st.session_state.get("dnd_edition", "2014 Edition")
    char_class = st.session_state.get("char_class", "Fighter")
    subclass_level = 3
    if edition == EDITION_2014:
        sub_lvls = {
            "Cleric": 1,
            "Sorcerer": 1,
            "Warlock": 1,
            "Wizard": 2,
            "Druid": 2,
        }
        subclass_level = sub_lvls.get(char_class, 3)

    current_subclass = st.session_state.get("subclass")
    needs_subclass = False
    if not current_subclass or current_subclass == "None":
        if target_lv >= subclass_level:
            needs_subclass = True

    if needs_subclass:
        st.markdown("---")
        st.markdown("#### 🎭 Step 2b: Choose Subclass")
        from backend.core.constants import SUBCLASSES_2014, SUBCLASSES_2024

        subclass_map = SUBCLASSES_2024 if edition == EDITION_2024 else SUBCLASSES_2014
        subclass_options = subclass_map.get(char_class, [])
        if subclass_options:
            temp["chosen_subclass"] = st.selectbox(
                f"Choose your {char_class} Subclass:",
                subclass_options,
                key="lv_up_chosen_subclass",
                index=subclass_options.index(temp.get("chosen_subclass"))
                if temp.get("chosen_subclass") in subclass_options
                else 0,
            )
        else:
            st.warning(f"No subclasses defined in the static library for {char_class}.")
            temp["chosen_subclass"] = None
    else:
        temp["chosen_subclass"] = None

    # STEP 2c: Class Features Unlocked (Static rules database)
    st.markdown("---")
    st.markdown("#### 🛡️ Step 2c: Class Features Unlocked")
    from backend.services.rules_service import get_static_class_features

    static_features = get_static_class_features(char_class, target_lv, edition)
    if static_features:
        st.write("You automatically unlock the following feature(s) at this level:")
        for feat in static_features:
            st.markdown(f"**{feat.get('name')}**")
            st.write(feat.get("description"))
            # Ensure static features are added to new_features
            existing_names = [f.get("name") for f in temp.get("new_features", [])]
            if feat.get("name") not in existing_names:
                temp.setdefault("new_features", []).append(feat)
    else:
        st.write("No new base class features unlocked at this level.")

    # STEP 3: Learn Spells (Optional)
    st.markdown("---")
    st.markdown("#### 🔮 Step 3: Learn Spells (Optional)")

    from backend.repositories.rules_repository import RulesRepository

    rules_repo = RulesRepository()
    edition = st.session_state.get("dnd_edition", "2014 Edition")
    all_spells = rules_repo.get_all_spells(edition)

    if all_spells:
        char_class_lower = str(st.session_state.get("char_class", "")).lower()
        subclass_lower = str(st.session_state.get("subclass", "")).lower()

        # Calculate maximum spell level slot appropriate for target level
        is_full = any(
            c in char_class_lower
            for c in ["wizard", "cleric", "druid", "sorcerer", "bard", "warlock"]
        )
        is_half = any(c in char_class_lower for c in ["paladin", "ranger", "artificer"])
        is_third = any(
            s in subclass_lower for s in ["eldritch knight", "arcane trickster"]
        )

        if is_full:
            max_lvl = (target_lv + 1) // 2
        elif is_half:
            max_lvl = (target_lv + 3) // 4
        elif is_third:
            max_lvl = (target_lv + 5) // 6
        else:
            max_lvl = 1  # Allow cantrips / 1st level spells for generic feats

        max_lvl = min(9, max(0, max_lvl))

        if "wizard" in char_class_lower:
            rec = "2 new Wizard spells"
        elif any(
            c in char_class_lower for c in ["sorcerer", "bard", "warlock", "ranger"]
        ):
            rec = "1 new spell"
        elif any(c in char_class_lower for c in ["cleric", "druid", "paladin"]):
            rec = (
                "access to all class spells of your levels (add any you wish to track)"
            )
        elif is_third:
            rec = "1 new Wizard spell"
        else:
            rec = "spells if granted by a Feat (e.g. Magic Initiate)"

        lvl_str = "Cantrips" if max_lvl == 0 else f"up to Level {max_lvl}"
        st.info(
            f"📚 **Class Rules Guide:** As a Level {target_lv} {st.session_state.get('char_class', '').title()}, you can learn/add spells of **{lvl_str}**. Standard rules recommendation: **{rec}**."
        )

        # Checkbox to include Cantrips
        include_cantrips = st.checkbox(
            "Show Cantrips (Level 0)",
            value=False,
            help="Cantrips are normally only learned at specific levels according to your class progression table.",
        )

        # Hide any spells that exceed the maximum castable level, and filter out cantrips unless checked
        min_lvl = 0 if include_cantrips else 1
        all_spells = [s for s in all_spells if min_lvl <= s.get("level", 0) <= max_lvl]

        class_spells = [
            s
            for s in all_spells
            if char_class_lower in [c.lower() for c in s.get("classes", [])]
        ]

        # Radio to toggle list
        spell_filter = st.radio(
            "Show spells for:",
            ["My Class Spells Only", "All Spells"],
            horizontal=True,
            key="lv_up_spell_filter",
        )

        available_spells = (
            class_spells
            if (spell_filter == "My Class Spells Only" and class_spells)
            else all_spells
        )
        # Sort spells by level, then name
        available_spells = sorted(
            available_spells,
            key=lambda x: (x.get("level", 0), x.get("name", "").lower()),
        )

        option_labels = []
        option_map = {}
        for s in available_spells:
            lvl = s.get("level", 0)
            lvl_lbl = "Cantrip" if lvl == 0 else f"Level {lvl}"
            label = f"[{lvl_lbl}] {s['name']}"
            option_labels.append(label)
            option_map[label] = s

        temp["selected_spells"] = st.multiselect(
            "Select spells to add to your spellbook:",
            options=option_labels,
            default=temp.get("selected_spells", []),
        )

        temp["selected_spells_data"] = [
            {"name": option_map[lbl]["name"], "level": option_map[lbl].get("level", 0)}
            for lbl in temp["selected_spells"]
            if lbl in option_map
        ]

        # Rule Validation Warning for spell count
        num_selected = len(temp["selected_spells_data"])
        limit = 0
        if "wizard" in char_class_lower:
            limit = 2
        elif any(
            c in char_class_lower for c in ["sorcerer", "bard", "warlock", "ranger"]
        ):
            limit = 1
        elif is_third:
            limit = 1

        if limit > 0 and num_selected > limit:
            st.warning(
                f"⚠️ **Rule Limit Warning:** You have selected {num_selected} spells, but your class progression table only allows learning {limit} new spell{'s' if limit > 1 else ''} at this level. (You can still proceed if your DM permitted additional spells/feats)."
            )
    else:
        st.write("No spells found in the rules database.")

    # STEP 4: AI Enrichment (Optional)
    st.markdown("---")
    st.markdown("#### ✨ Step 4: Consult the Oracle (Optional)")
    if not temp["ai_consulted"]:
        if st.button("🔮 Ask AI for Features & Suggestions"):
            with st.spinner("Oracle is analyzing your path..."):
                char_data = get_character_dict(st.session_state)

                # Prepare context for AI based on manual choices
                user_choices_context = {
                    "HP Increase": f"+{temp['hp_inc']} ({temp['hp_method']})",
                }
                if is_asi_level:
                    if temp["asi_feat_choice"] == "Ability Score Improvement":
                        user_choices_context["Benefit Chosen"] = (
                            f"ASI (+1 to {', '.join(temp['stats_raised'])})"
                        )
                    else:
                        user_choices_context["Benefit Chosen"] = (
                            f"Feat: {temp['selected_feat']}"
                        )

                analysis = analyze_level_up(
                    char_data, user_choices=user_choices_context
                )
                if analysis:
                    temp["new_features"] = analysis.get("automatic_changes", [])
                    temp["suggestions"] = analysis.get("suggestions", [])
                    temp["ai_consulted"] = True
                    st.rerun()
    else:
        st.success("Oracle has spoken. New features and suggestions loaded.")
        for feat in temp["new_features"]:
            with st.expander(f"🔹 {feat.get('name')}"):
                st.write(feat.get("description"))

    # STEP 5: PREVIEW
    st.markdown("---")
    st.markdown("#### 🛡️ Step 5: Level Up Preview")
    prev_col1, prev_col2 = st.columns(2)

    # Calculate preview stats
    prev_hp = st.session_state.hp_max + temp["hp_inc"]
    prev_stats = st.session_state.stats.copy()
    if temp["asi_feat_choice"] == "Ability Score Improvement":
        for s in temp["stats_raised"]:
            prev_stats[s] = prev_stats.get(s, 10) + 1

    prev_col1.metric("Max HP", f"{prev_hp}", delta=f"+{temp['hp_inc']}")
    if is_asi_level:
        if temp["asi_feat_choice"] == "Ability Score Improvement":
            stats_display = ", ".join([f"{s}+1" for s in temp["stats_raised"]])
            prev_col2.metric("Stats Boost", stats_display)
        elif temp["selected_feat"]:
            feat_info = temp["selected_feat"]
            if temp.get("feat_stat_bonus"):
                feat_info += f" (+1 {temp['feat_stat_bonus']})"
            prev_col2.metric("New Feat", feat_info)

    if temp.get("selected_spells_data"):
        st.markdown(
            f"**🔮 Spells to Learn:** {', '.join([s['name'] for s in temp['selected_spells_data']])}"
        )

    st.markdown("---")

    # FINAL ACTIONS
    col_fin1, col_fin2 = st.columns(2)

    if col_fin1.button("🔥 Finalize Ascension", width="stretch", type="primary"):
        # APPLY CHANGES
        st.session_state.char_level = target_lv
        st.session_state.hp_max = prev_hp

        # Apply Stats
        st.session_state.stats = prev_stats
        if temp["asi_feat_choice"] == "Feat" and temp.get("feat_stat_bonus"):
            stat = temp["feat_stat_bonus"]
            st.session_state.stats[stat] = st.session_state.stats.get(stat, 10) + 1

        # Add feat if chosen
        if temp["asi_feat_choice"] == "Feat" and temp["selected_feat"]:
            st.session_state.features_traits.append(
                {
                    "name": f"Feat: {temp['selected_feat']}",
                    "description": temp.get(
                        "selected_feat_desc", "Selected during manual level up."
                    ),
                }
            )

        # Add selected spells to known list
        spells = st.session_state.get("spells", {})
        if hasattr(spells, "model_dump"):
            spells_dict = spells.model_dump()
        elif isinstance(spells, dict):
            spells_dict = spells
        else:
            spells_dict = {}

        for s_info in temp.get("selected_spells_data", []):
            name = s_info["name"]
            lvl = s_info["level"]
            lvl_key = "cantrips" if lvl == 0 else f"level_{lvl}"
            if lvl_key not in spells_dict:
                spells_dict[lvl_key] = []
            if name not in spells_dict[lvl_key]:
                spells_dict[lvl_key].append(name)

        st.session_state.spells = spells_dict

        # Apply subclass if selected
        if temp.get("chosen_subclass"):
            st.session_state.subclass = temp["chosen_subclass"]

        # Add unlocked features (both static class features and AI enrichment)
        current_feat_names = [f.get("name") for f in st.session_state.features_traits]
        for feat in temp.get("new_features", []):
            if feat.get("name") not in current_feat_names:
                st.session_state.features_traits.append(feat)

        # Cleanup
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll

        trigger_sync()
        st.success(f"Ascension Complete! Level {target_lv} reached.")
        st.rerun()

    if col_fin2.button("↩️ Discard & Revert", width="stretch"):
        del st.session_state.lv_up_temp
        if "lv_up_hp_roll" in st.session_state:
            del st.session_state.lv_up_hp_roll
        st.rerun()
