import streamlit as st
import logging

from backend.core.storage import (
    save_character,
)
from backend.core.state_manager import (
    get_character_dict,
)

from views.player._helpers import log_roll

logger = logging.getLogger(__name__)


def _render_features_spells(edit_mode: bool):
    """Renders features and spellcasting sections."""
    st.markdown("#### Features & Traits")
    if edit_mode:
        edited_features_df = st.data_editor(
            st.session_state.features_traits, num_rows="dynamic", key="edit_features"
        )
        if edited_features_df is not None:
            new_features = []
            import pandas as pd

            rows = (
                edited_features_df.iterrows()
                if isinstance(edited_features_df, pd.DataFrame)
                else enumerate(edited_features_df)
            )
            for _, row in rows:
                new_features.append(
                    {
                        "name": row.get("name") or "New Feature",
                        "description": row.get("description") or "",
                        "source": row.get("source"),
                    }
                )
            st.session_state.features_traits = new_features
    else:
        features = st.session_state.get("features_traits", [])
        if features is None:
            features = []
        for f in features:
            name = f.get("name", "Feature")
            desc = f.get("description", "").replace(
                "\n", "  \n"
            )  # Ensure markdown line breaks
            st.markdown(f"**{name}**  \n{desc}")
            st.divider()

    st.markdown("#### Spells")
    if edit_mode:
        cs1, cs2, cs3 = st.columns(3)
        options = ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
        current_ability = st.session_state.spell_ability
        ability_index = (
            options.index(current_ability) if current_ability in options else 0
        )

        st.session_state.spell_ability = cs1.selectbox(
            "Spellcasting Ability",
            options,
            index=ability_index,
        )
        cs2.number_input(
            "Spell Save DC (Derived)",
            0,
            30,
            st.session_state.spell_save_dc,
            disabled=True,
        )
        cs3.text_input(
            "Spell Attack Bonus (Derived)",
            st.session_state.spell_attack_bonus,
            disabled=True,
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
        if edited_spells is not None:
            new_spells = {}
            import pandas as pd

            rows = (
                edited_spells.iterrows()
                if isinstance(edited_spells, pd.DataFrame)
                else enumerate(edited_spells)
            )
            for _, row in rows:
                if row.get("level") and row.get("spell"):
                    lvl = row["level"]
                    if lvl not in new_spells:
                        new_spells[lvl] = []
                    new_spells[lvl].append(row["spell"])
            st.session_state.spells = new_spells
    else:
        # Check if they have any spells
        spells = st.session_state.get("spells", {})
        if hasattr(spells, "model_dump"):
            spells_dict = spells.model_dump()
        elif isinstance(spells, dict):
            spells_dict = spells
        else:
            spells_dict = {}

        has_any_spell = any(spells_dict.get(k) for k in spells_dict)

        if not has_any_spell:
            st.write("No spells known.")
        else:
            if (
                st.session_state.spell_ability
                and st.session_state.spell_ability != "None"
            ):
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Ability", st.session_state.spell_ability)
                sc2.metric("Save DC", st.session_state.spell_save_dc)
                sc3.metric("Attack Bonus", st.session_state.spell_attack_bonus)
                st.markdown("---")

            # Determine if class is a prepared caster
            char_class = str(st.session_state.get("char_class", "")).lower()
            is_prepared_caster = any(
                c in char_class for c in ["wizard", "cleric", "druid", "paladin"]
            )

            # Initialize prepared spells state if missing
            if (
                "prepared_spells" not in st.session_state
                or st.session_state.prepared_spells is None
            ):
                st.session_state.prepared_spells = []

            # Clean list of prepared spells for easy case-insensitive check
            prepared_clean = [
                p.strip().lower() for p in st.session_state.prepared_spells if p
            ]

            if is_prepared_caster:
                view_mode = st.radio(
                    "📖 Spellbook View:",
                    [
                        "⚔️ Prepared Spells (Combat)",
                        "📝 Manage Spellbook (Prepare Spells)",
                    ],
                    horizontal=True,
                    key="spellbook_view_toggle",
                )
            else:
                view_mode = "⚔️ Prepared Spells (Combat)"  # non-prepared casters show everything in combat

            # Load rules repository to get spell details
            from backend.repositories.rules_repository import RulesRepository

            repo = RulesRepository()
            edition = st.session_state.get("dnd_edition", "2014 Edition")
            all_spells = repo.get_all_spells(edition)
            spells_lookup = (
                {s["name"].lower().strip(): s for s in all_spells} if all_spells else {}
            )

            level_keys = [
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
            ]

            # --- SPELL SLOTS UI ---
            spell_slots = st.session_state.get("spell_slots", {})
            if spell_slots and view_mode == "⚔️ Prepared Spells (Combat)":
                st.markdown("##### ⚡ Spell Slots")

                # Concentration Indicator
                if st.session_state.get("concentrating_on"):
                    conc_col1, conc_col2 = st.columns([3, 1])
                    with conc_col1:
                        st.info(
                            f"🧠 **Concentrating on:** {st.session_state.concentrating_on}"
                        )
                    with conc_col2:
                        if st.button(
                            "Drop",
                            key="drop_conc_spells",
                            help="Drop Concentration",
                            use_container_width=True,
                        ):
                            st.session_state.concentrating_on = None
                            save_character(get_character_dict(st.session_state))
                            st.rerun()

                slot_levels = sorted(
                    [k for k in spell_slots.keys() if k.startswith("level_")],
                    key=lambda x: int(x.split("_")[1]),
                )
                valid_slots = [
                    sl for sl in slot_levels if spell_slots[sl].get("max", 0) > 0
                ]

                if valid_slots:
                    # chunk into rows of 4
                    for i in range(0, len(valid_slots), 4):
                        chunk = valid_slots[i : i + 4]
                        cols = st.columns(4)
                        for col_idx, sl_key in enumerate(chunk):
                            sl_num = sl_key.split("_")[1]
                            max_s = spell_slots[sl_key].get("max", 0)
                            used_s = spell_slots[sl_key].get("used", 0)
                            with cols[col_idx]:
                                st.caption(
                                    f"**Level {sl_num}** ({max_s - used_s}/{max_s})"
                                )
                                # Render inline checkboxes
                                slot_cols = st.columns(max_s)
                                for j in range(max_s):
                                    is_used = j < used_s
                                    with slot_cols[j]:
                                        new_used = st.checkbox(
                                            "X",
                                            value=is_used,
                                            key=f"slot_{sl_key}_{j}",
                                            label_visibility="collapsed",
                                        )
                                        if new_used != is_used:
                                            # We need to compute the total used slots based on which ones are checked
                                            # Since Streamlit runs top-to-bottom, we just adjust the counter +1 or -1
                                            if new_used:
                                                spell_slots[sl_key]["used"] = min(
                                                    max_s, used_s + 1
                                                )
                                            else:
                                                spell_slots[sl_key]["used"] = max(
                                                    0, used_s - 1
                                                )
                                            st.session_state.spell_slots = spell_slots
                                            save_character(
                                                get_character_dict(st.session_state)
                                            )
                                            st.rerun()
                    st.markdown("---")

            if view_mode == "📝 Manage Spellbook (Prepare Spells)":
                with st.expander("➕ Add New Spell", expanded=False):
                    add_col1, add_col2 = st.columns([3, 1])
                    all_spell_names = sorted(list(spells_lookup.keys()))
                    with add_col1:
                        new_spell_name = st.selectbox(
                            "Search & Select Spell",
                            [""] + [s.title() for s in all_spell_names],
                            help="Type to search for a spell from the rules.",
                        )
                    with add_col2:
                        st.write("")  # padding
                        st.write("")  # padding
                        if st.button("Add to Spellbook", use_container_width=True):
                            if new_spell_name:
                                lookup_key = new_spell_name.lower().strip()
                                spell_data = spells_lookup.get(lookup_key)
                                if spell_data:
                                    lvl_num = spell_data.get("level", 0)
                                    target_lvl_key = (
                                        "cantrips"
                                        if lvl_num == 0
                                        else f"level_{lvl_num}"
                                    )
                                else:
                                    target_lvl_key = "level_1"  # Fallback

                                if target_lvl_key not in spells_dict:
                                    spells_dict[target_lvl_key] = []
                                if new_spell_name not in spells_dict[target_lvl_key]:
                                    spells_dict[target_lvl_key].append(new_spell_name)
                                    st.session_state.spells = spells_dict
                                    save_character(get_character_dict(st.session_state))
                                    st.rerun()
                st.markdown("---")

            shown_any_level = False

            for lvl_key in level_keys:
                spell_list = spells_dict.get(lvl_key, [])
                if not spell_list:
                    continue

                # Filter spells based on preparation if in combat view
                is_cantrip = lvl_key == "cantrips"
                if (
                    view_mode == "⚔️ Prepared Spells (Combat)"
                    and not is_cantrip
                    and is_prepared_caster
                ):
                    spell_list = [
                        s for s in spell_list if s.strip().lower() in prepared_clean
                    ]
                    if not spell_list:
                        continue

                shown_any_level = True
                lvl_title = lvl_key.title().replace("_", " ")
                st.markdown(f"##### {lvl_title}")

                for s_name in spell_list:
                    s_name_clean = s_name.strip()
                    spell_data = spells_lookup.get(s_name_clean.lower())

                    if spell_data:
                        school = spell_data.get("school", "Unknown").title()
                        lvl_num = spell_data.get("level", 0)
                        lvl_lbl = "Cantrip" if lvl_num == 0 else f"Level {lvl_num}"
                        desc = spell_data.get("description", "")
                        casting_time = spell_data.get("castingTime", "1 action")
                        s_range = spell_data.get("range", "Touch")
                        duration = spell_data.get("duration", "Instantaneous")
                        components = spell_data.get("components", [])
                        material = spell_data.get("material")
                        ritual = spell_data.get("ritual", False)
                        concentration = spell_data.get("concentration", False)
                        classes = spell_data.get("classes", [])
                    else:
                        school = "Unknown"
                        lvl_lbl = (
                            "Cantrip"
                            if lvl_key == "cantrips"
                            else f"Level {lvl_key.split('_')[1]}"
                        )
                        desc = "No description found in the rules database."
                        casting_time = "1 action"
                        s_range = "Unknown"
                        duration = "Instantaneous"
                        components = []
                        material = None
                        ritual = False
                        concentration = False
                        classes = []

                    # Build tags for expander label
                    tags = []
                    if concentration:
                        tags.append("⏱️ Conc")
                    if ritual:
                        tags.append("📜 Rit")
                    # If managing spellbook, indicate if prepared in expander title
                    is_prep = s_name_clean.lower() in prepared_clean
                    if is_prepared_caster and not is_cantrip:
                        if is_prep:
                            tags.append("✅ Prepared")
                        else:
                            tags.append("❌ Unprepared")

                    tags_str = f" ({', '.join(tags)})" if tags else ""
                    expander_label = f"✨ {s_name_clean} ({lvl_lbl} {school}){tags_str}"

                    with st.expander(expander_label):
                        # Preparation Toggle if managing
                        if (
                            is_prepared_caster
                            and not is_cantrip
                            and view_mode == "📝 Manage Spellbook (Prepare Spells)"
                        ):
                            prep_val = st.checkbox(
                                f"Prepare **{s_name_clean}**",
                                value=is_prep,
                                key=f"prep_check_{lvl_key}_{s_name_clean}",
                            )
                            if prep_val != is_prep:
                                if prep_val:
                                    st.session_state.prepared_spells.append(
                                        s_name_clean
                                    )
                                else:
                                    st.session_state.prepared_spells = [
                                        p
                                        for p in st.session_state.prepared_spells
                                        if p.strip().lower() != s_name_clean.lower()
                                    ]
                                # Auto save character state
                                save_character(get_character_dict(st.session_state))
                                st.rerun()

                        # Show description and details
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Casting Time:** {casting_time}")
                            st.markdown(f"**Range:** {s_range}")
                            st.markdown(f"**Duration:** {duration}")
                        with c2:
                            comps_str = (
                                ", ".join([c.upper() for c in components])
                                if components
                                else "None"
                            )
                            st.markdown(f"**Components:** {comps_str}")
                            if material:
                                st.markdown(f"**Materials:** *{material}*")
                            if classes:
                                st.markdown(
                                    f"**Classes:** {', '.join([c.title() for c in classes])}"
                                )

                        st.markdown("---")
                        st.markdown(desc)

                        # Search description for dice formulas to roll
                        import re

                        dice_formulas = re.findall(r"\b\d+d\d+(?:\+\d+)?\b", desc)
                        # deduplicate formulas
                        unique_formulas = []
                        for f in dice_formulas:
                            if f not in unique_formulas:
                                unique_formulas.append(f)

                        # Action Row
                        st.markdown("**Actions:**")
                        cols = st.columns(max(3, len(unique_formulas) + 2))

                        # Button 1: Cast Spell
                        with cols[0]:
                            if st.button(
                                "✨ Cast",
                                key=f"cast_{lvl_key}_{s_name_clean}",
                                use_container_width=True,
                            ):
                                spell_slots_state = st.session_state.get(
                                    "spell_slots", {}
                                )
                                slot_key = lvl_key

                                can_cast = True
                                if not is_cantrip and slot_key in spell_slots_state:
                                    max_s = spell_slots_state[slot_key].get("max", 0)
                                    used_s = spell_slots_state[slot_key].get("used", 0)
                                    if used_s < max_s:
                                        spell_slots_state[slot_key]["used"] += 1
                                        st.session_state.spell_slots = spell_slots_state
                                    else:
                                        can_cast = False
                                        st.toast(
                                            f"No {lvl_lbl} slots remaining!", icon="⚠️"
                                        )

                                if can_cast:
                                    if concentration:
                                        st.session_state.concentrating_on = s_name_clean

                                    save_character(get_character_dict(st.session_state))
                                    log_roll(f"Casted **{s_name_clean}** ({lvl_lbl})!")
                                    st.rerun()

                        # Button 2: Spell Attack (if description mentions spell attack)
                        requires_attack = (
                            "spell attack" in desc.lower()
                            or "spell attack" in casting_time.lower()
                        )
                        with cols[1]:
                            if requires_attack:
                                bonus_str = str(
                                    st.session_state.get("spell_attack_bonus", "+0")
                                ).replace("+", "")
                                try:
                                    bonus = int(bonus_str)
                                except Exception:
                                    bonus = 0
                                if st.button(
                                    "🎯 Attack",
                                    key=f"atk_{lvl_key}_{s_name_clean}",
                                    use_container_width=True,
                                ):
                                    from backend.utils.dice import quick_roll

                                    res, raw = quick_roll(20, bonus)
                                    log_roll(
                                        f"**{s_name_clean}** Spell Attack: **{res}** (d20: {raw} + {bonus})"
                                    )
                                    st.session_state.active_roll = {
                                        "label": f"{s_name_clean} Attack Roll",
                                        "sides": 20,
                                        "raw": raw,
                                        "modifier": bonus,
                                        "total": res,
                                        "adv_type": "None",
                                    }
                                    if raw == 20:
                                        st.balloons()
                                    st.rerun()
                            elif (
                                "saving throw" in desc.lower() or "save" in desc.lower()
                            ):
                                save_dc = st.session_state.get("spell_save_dc", 8)
                                st.caption(f"🛡️ **Save DC:** {save_dc}")

                        # Buttons for rolling dice formulas
                        for idx, formula in enumerate(unique_formulas):
                            with cols[2 + idx]:
                                if st.button(
                                    f"🎲 {formula}",
                                    key=f"roll_{lvl_key}_{s_name_clean}_{formula}",
                                    use_container_width=True,
                                ):
                                    from backend.utils.dice import roll_dice

                                    res = roll_dice(formula)
                                    if "error" in res:
                                        st.error(f"Error rolling dice: {res['error']}")
                                    else:
                                        log_roll(
                                            f"**{s_name_clean}** ({formula}): **{res['total']}** ({res['result_text']})"
                                        )
                                        try:
                                            sides = int(
                                                re.search(r"d(\d+)", formula).group(1)
                                            )
                                        except Exception:
                                            sides = 6
                                        rolls = res.get("rolls", [1])
                                        st.session_state.active_roll = {
                                            "label": f"{s_name_clean} — {formula}",
                                            "sides": sides,
                                            "raw": rolls
                                            if len(rolls) > 1
                                            else rolls[0],
                                            "raw_selected": sum(rolls),
                                            "modifier": res.get("modifier", 0),
                                            "total": res.get("total", 1),
                                            "adv_type": "None",
                                        }
                                        st.rerun()

            if not shown_any_level and view_mode == "⚔️ Prepared Spells (Combat)":
                st.info(
                    "No level 1-9 spells are currently prepared for combat. Switch to 'Manage Spellbook' to prepare your spells."
                )
