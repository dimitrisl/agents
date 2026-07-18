import streamlit as st
import logging

from backend.core.storage import (
    save_character,
)
from backend.core.state_manager import (
    get_character_dict,
)
from backend.services.mechanics_service import (
    get_modifier as calculate_modifier,
)

from views.player._helpers import log_roll, safe_int

logger = logging.getLogger(__name__)


def _render_core_stats(edit_mode: bool):
    """Renders ability scores, core attributes, and skills."""
    if edit_mode:
        c_n, c_c, c_l, c_r = st.columns(4)
        st.session_state.char_name = c_n.text_input(
            "Name", value=st.session_state.char_name, disabled=True
        )
        st.session_state.char_class = c_c.text_input(
            "Class", value=st.session_state.char_class, disabled=True
        )
        st.session_state.subclass = c_c.text_input(
            "Subclass", value=st.session_state.subclass or "", disabled=True
        )
        st.session_state.char_level = c_l.number_input(
            "Level", 1, 20, value=st.session_state.char_level, disabled=True
        )
        st.session_state.race = c_r.text_input(
            "Race", value=st.session_state.race, disabled=True
        )

        c_b, c_a, c_hp, c_ac = st.columns(4)
        st.session_state.background = c_b.text_input(
            "Background", value=st.session_state.background, disabled=True
        )
        st.session_state.alignment = c_a.text_input(
            "Alignment", value=st.session_state.alignment
        )
        c_hp.number_input(
            "Max HP (Derived)", 1, 500, value=st.session_state.hp_max, disabled=True
        )
        c_ac.number_input(
            "Armor Class (Derived)",
            1,
            50,
            value=st.session_state.armor_class,
            disabled=True,
        )

        c_hd, c_pass = st.columns(2)
        c_hd.text_input(
            "Hit Dice (Derived)", value=st.session_state.hit_dice or "", disabled=True
        )
        c_pass.number_input(
            "Passive Perception (Derived)",
            0,
            30,
            value=st.session_state.passive_perception,
            disabled=True,
        )

        st.markdown("#### Ability Scores")
        c1, c2, c3, c4, c5, c6 = st.columns(6)

        def stat_input(col, label, key):
            current_val = st.session_state.stats.get(key, 10)
            col.number_input(
                label,
                min_value=1,
                max_value=30,
                value=int(current_val),
                key=f"stat_val_{key}",
            )

        # Ensure temp keys exist
        for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            if f"stat_val_{k}" not in st.session_state:
                st.session_state[f"stat_val_{k}"] = st.session_state.stats[k]

        stat_input(c1, "STR", "STR")
        stat_input(c2, "DEX", "DEX")
        stat_input(c3, "CON", "CON")
        stat_input(c4, "INT", "INT")
        stat_input(c5, "WIS", "WIS")
        stat_input(c6, "CHA", "CHA")

        st.markdown("#### Skills & Proficiencies")

        # Create a list of all 18 standard skills
        standard_skills = [
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

        import pandas as pd

        # Build a DataFrame for the editor
        skill_data = []
        for sk in standard_skills:
            skill_data.append(
                {
                    "Skill": sk,
                    "Bonus": st.session_state.skills.get(sk, 0),
                    "Proficient": sk in st.session_state.skill_proficiencies,
                    "Expert": sk in getattr(st.session_state, "skill_expertise", []),
                }
            )

        df_skills = pd.DataFrame(skill_data)

        edited_df = st.data_editor(
            df_skills,
            column_config={
                "Proficient": st.column_config.CheckboxColumn("P", help="Proficient?"),
                "Expert": st.column_config.CheckboxColumn("E", help="Expertise?"),
                "Bonus": st.column_config.NumberColumn(
                    "Bonus", disabled=True, help="Automatically calculated"
                ),
            },
            disabled=["Skill"],
            hide_index=True,
            use_container_width=True,
            key="skill_data_editor",
        )

        # Sync back to session state
        if st.session_state.get("skill_data_editor"):
            new_skills = {}
            new_profs = []
            new_exps = []
            for _, row in edited_df.iterrows():
                new_skills[row["Skill"]] = row["Bonus"]
                if row["Proficient"]:
                    new_profs.append(row["Skill"])
                if row["Expert"]:
                    new_exps.append(row["Skill"])

            st.session_state.skills = new_skills
            st.session_state.skill_proficiencies = new_profs
            st.session_state.skill_expertise = new_exps

        st.session_state.saving_throws = st.multiselect(
            "Saving Throw Proficiencies",
            options=["STR", "DEX", "CON", "INT", "WIS", "CHA"],
            default=st.session_state.saving_throws,
        )
    else:
        # --- COMBAT & STATUS ---
        st.markdown("### ⚔️ Combat & Status")
        col_hp, col_cond, col_rest = st.columns([1.5, 2, 1])

        with col_hp:
            hp_curr = st.session_state.get("hp_current")
            if hp_curr is None:
                hp_curr = st.session_state.hp_max
                st.session_state.hp_current = hp_curr

            st.markdown(f"**HP:** `{hp_curr}` / `{st.session_state.hp_max}`")
            hp_bar_pct = max(0.0, min(1.0, hp_curr / max(1, st.session_state.hp_max)))
            st.progress(hp_bar_pct)

            hc1, hc2 = st.columns([1, 1])

            def _apply_dmg_callback():
                dmg = st.session_state.get("dmg_val", 0)
                if dmg > 0:
                    curr = st.session_state.get(
                        "hp_current", st.session_state.get("hp_max", 10)
                    )
                    st.session_state.hp_current = max(0, curr - dmg)
                    st.session_state.dmg_val = 0
                    save_character(get_character_dict(st.session_state))

            def _apply_heal_callback():
                heal = st.session_state.get("heal_val", 0)
                if heal > 0:
                    curr = st.session_state.get(
                        "hp_current", st.session_state.get("hp_max", 10)
                    )
                    m_hp = st.session_state.get("hp_max", 10)
                    st.session_state.hp_current = min(m_hp, curr + heal)
                    st.session_state.heal_val = 0
                    save_character(get_character_dict(st.session_state))

            with hc1:
                st.number_input("Damage", min_value=0, step=1, key="dmg_val")
                st.button(
                    "🩸 Apply Dmg",
                    on_click=_apply_dmg_callback,
                    use_container_width=True,
                )

            with hc2:
                st.number_input("Heal", min_value=0, step=1, key="heal_val")
                st.button(
                    "💚 Apply Heal",
                    on_click=_apply_heal_callback,
                    use_container_width=True,
                )

        with col_cond:
            curr_cond = st.session_state.get("conditions", [])
            new_cond = st.multiselect(
                "Active Conditions",
                options=[
                    "Blinded",
                    "Charmed",
                    "Deafened",
                    "Frightened",
                    "Grappled",
                    "Incapacitated",
                    "Invisible",
                    "Paralyzed",
                    "Petrified",
                    "Poisoned",
                    "Prone",
                    "Restrained",
                    "Stunned",
                    "Unconscious",
                    "Exhaustion",
                ],
                default=curr_cond,
                key="player_conditions",
            )
            if new_cond != curr_cond:
                st.session_state.conditions = new_cond
                save_character(get_character_dict(st.session_state))
                st.rerun()

        with col_rest:
            st.markdown("**Camp & Rest**")

            # Short Rest Popover
            with st.popover("⛺ Short Rest", use_container_width=True):
                st.markdown("### Short Rest")
                st.write("Spend Hit Dice to regain HP.")

                total_hd = st.session_state.char_level
                used_hd = st.session_state.get("hit_dice_used", 0)
                available_hd = max(0, total_hd - used_hd)

                st.write(f"Available Hit Dice: **{available_hd} / {total_hd}**")

                if available_hd > 0:
                    hd_to_spend = st.number_input(
                        "Number of Hit Dice to spend",
                        min_value=1,
                        max_value=available_hd,
                        value=1,
                        step=1,
                        key="short_rest_hd_count",
                    )

                    if st.button(
                        "Roll & Heal", type="primary", use_container_width=True
                    ):
                        import random
                        from backend.services.mechanics_service import get_modifier

                        con_score = st.session_state.stats.get("CON", 10)
                        con_mod = get_modifier(con_score)

                        # Get hit die size (e.g. "d8" or "d10")
                        hit_die_str = st.session_state.get("hit_dice", "d8")
                        try:
                            # Extract number after 'd'
                            die_size = int(hit_die_str.lower().split("d")[-1])
                        except Exception:
                            die_size = 8

                        rolls = [
                            random.randint(1, die_size) for _ in range(hd_to_spend)
                        ]
                        roll_sum = sum(rolls)
                        con_bonus = con_mod * hd_to_spend
                        total_healed = max(0, roll_sum + con_bonus)

                        old_hp = st.session_state.hp_current
                        new_hp = min(st.session_state.hp_max, old_hp + total_healed)
                        st.session_state.hp_current = new_hp
                        st.session_state.hit_dice_used = used_hd + hd_to_spend

                        # Add roll to roll history log
                        roll_msg = f"Short Rest: Spent {hd_to_spend}d{die_size} + {con_bonus} CON. Rolled {rolls}. Healed {total_healed} HP."
                        if "roll_history" not in st.session_state:
                            st.session_state.roll_history = []
                        st.session_state.roll_history.insert(0, roll_msg)

                        save_character(get_character_dict(st.session_state))
                        st.success(
                            f"Healed for {total_healed} HP! ({old_hp} ➡️ {new_hp})"
                        )

                        # Class-specific resource restoration
                        char_class = st.session_state.get("char_class", "").lower()
                        if "warlock" in char_class:
                            slots = st.session_state.get("spell_slots", {})
                            for lvl, data in slots.items():
                                data["used"] = 0
                            st.session_state.spell_slots = slots
                            st.info("🔮 Pact Magic spell slots restored!")

                        st.rerun()
                else:
                    st.warning("No Hit Dice remaining.")

            # Trance / Long Rest selection
            is_elf = "elf" in str(st.session_state.get("race", "")).lower()
            if is_elf:
                rest_label = "🧘 Elven Trance"
                rest_toast = "Trance completed! 4 hours of meditation restored HP, Hit Dice, and Spell Slots."
            else:
                rest_label = "🔥 Long Rest"
                rest_toast = (
                    "Long Rest completed! HP, Hit Dice, and Spell Slots restored."
                )

            if st.button(rest_label, type="primary", use_container_width=True):
                st.session_state.hp_current = st.session_state.hp_max
                st.session_state.hit_dice_used = max(
                    0,
                    st.session_state.get("hit_dice_used", 0)
                    - max(1, st.session_state.char_level // 2),
                )
                slots = st.session_state.get("spell_slots", {})
                for lvl, data in slots.items():
                    data["used"] = 0
                st.session_state.spell_slots = slots
                save_character(get_character_dict(st.session_state))
                st.toast(rest_toast)
                st.rerun()

        st.markdown("---")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Max HP", st.session_state.hp_max)
        c2.metric("Armor Class", st.session_state.armor_class)
        init_mod = st.session_state.get("initiative_modifier") or 0
        c3.metric("Initiative", f"{'+' if init_mod >= 0 else ''}{init_mod}")
        c4.metric("Speed", f"{st.session_state.speed} ft")
        c5.metric("Proficiency", f"+{st.session_state.proficiency_bonus}")

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
            # Add the roll button below the visual box
            if st.button("🎲 Roll", key=f"p_roll_{label}"):
                from backend.utils.dice import quick_roll

                res, raw = quick_roll(20, mod)
                log_roll(f"**{label}** Check: **{res}** (d20: {raw}, Mod: {mod_str})")
                st.session_state.active_roll = {
                    "label": f"{label} Check",
                    "sides": 20,
                    "raw": raw,
                    "modifier": mod,
                    "total": res,
                    "adv_type": "None",
                }
                st.rerun()

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

        st.markdown("<br>", unsafe_allow_html=True)
        # Add a global Custom Roll for players too
        with st.popover("🎲 Custom / Damage Roll", width="stretch"):
            st.markdown("### Custom Roll")

            # Extract relevant dice for this character
            relevant_dice = {20}  # Always include d20

            # 1. Hit Die
            try:
                hd_size = int(st.session_state.hit_dice.lower().split("d")[-1])
                relevant_dice.add(hd_size)
            except Exception:
                pass

            # 2. Weapon Dice
            import re

            from backend.services.mechanics_service import rebuild_damage_formula

            for w in st.session_state.weapons:
                dmg = str(
                    w.get("damage")
                    or rebuild_damage_formula(
                        w.get("damage_dice"), w.get("damage_bonus")
                    )
                )
                found = re.findall(r"d(\d+)", dmg)
                for d in found:
                    relevant_dice.add(int(d))

            # 3. Spell Dice (Quick scan of descriptions/names)
            # This is a bit more complex but we can scan the spells
            for lvl_spells in st.session_state.spells.values():
                for s in lvl_spells:
                    found = re.findall(r"d(\d+)", s)
                    for d in found:
                        relevant_dice.add(int(d))

            # Sort and format for display
            dice_options = sorted(list(relevant_dice), reverse=True)
            if not any(d in dice_options for d in [12, 10, 8, 6, 4]):
                # Fallback if character is empty/new
                dice_options = [20, 12, 10, 8, 6, 4]

            pd_c1, pd_c2, pd_c3, pd_c4 = st.columns([1, 1, 1, 1])
            p_dtype = pd_c1.selectbox("Dice", dice_options, index=0)

            # Ability Modifier Picker
            abilities = ["None", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
            p_ability = pd_c2.selectbox("Ability", abilities, index=0)

            # Skill Modifier Picker
            skill_list = ["None"] + sorted(
                list(st.session_state.get("skills", {}).keys())
            )
            p_skill = pd_c3.selectbox("Skill", skill_list, index=0)

            p_extra = pd_c4.number_input("Bonus", value=0)
            st.caption(
                "Note: Skill bonuses usually include their relevant ability modifier."
            )

            p_adv = st.radio(
                "Advantage?",
                ["None", "Advantage", "Disadvantage"],
                horizontal=True,
                key="custom_roll_adv",
            )

            if st.button(
                "Roll!", type="primary", width="stretch", key="custom_roll_btn"
            ):
                from backend.utils.dice import quick_roll

                # Calculate total modifier
                total_mod = p_extra
                mod_parts = []
                if p_extra != 0:
                    mod_parts.append(f"{p_extra}")

                if p_ability != "None":
                    a_mod = calculate_modifier(st.session_state.stats[p_ability])
                    total_mod += a_mod
                    mod_parts.append(f"{p_ability}({'+' if a_mod >= 0 else ''}{a_mod})")

                if p_skill != "None":
                    s_mod = st.session_state.skills[p_skill]
                    total_mod += s_mod
                    mod_parts.append(f"{p_skill}({'+' if s_mod >= 0 else ''}{s_mod})")

                mod_desc = " + ".join(mod_parts) if mod_parts else "0"

                if p_adv == "None":
                    res, raw = quick_roll(p_dtype, total_mod)
                    msg = f"**Custom Roll ({p_dtype})**: **{res}** (raw: {raw} + {mod_desc})"
                    log_roll(msg)
                    st.session_state.active_roll = {
                        "label": f"Custom Roll (d{p_dtype})",
                        "sides": p_dtype,
                        "raw": raw,
                        "modifier": total_mod,
                        "total": res,
                        "adv_type": "None",
                    }
                    st.rerun()
                else:
                    r1, raw1 = quick_roll(p_dtype, total_mod)
                    r2, raw2 = quick_roll(p_dtype, total_mod)
                    final = max(r1, r2) if p_adv == "Advantage" else min(r1, r2)
                    msg = f"**{p_adv} ({p_dtype})**: **{final}** (Rolls: {r1}, {r2} | Mod: {mod_desc})"
                    log_roll(msg)
                    st.session_state.active_roll = {
                        "label": f"Custom Roll with {p_adv}",
                        "sides": p_dtype,
                        "raw": [raw1, raw2],
                        "raw_selected": raw1
                        if (p_adv == "Advantage" and raw1 >= raw2)
                        or (p_adv == "Disadvantage" and raw1 <= raw2)
                        else raw2,
                        "modifier": total_mod,
                        "total": final,
                        "adv_type": p_adv,
                    }
                    st.rerun()

        col_sk, col_sv = st.columns(2)
        with col_sk:
            st.markdown("#### Skills")
            skills = st.session_state.get("skills", {})
            if skills is None:
                skills = {}
            for k, v in skills.items():
                indicator = ""
                if k in st.session_state.skill_proficiencies:
                    indicator = "● "
                if k in getattr(st.session_state, "skill_expertise", []):
                    indicator = "★ "

                sc1, sc2 = st.columns([4, 1])
                sc1.write(f"{indicator}**{k}:** {v}")
                if sc2.button("🎲", key=f"roll_skill_{k}"):
                    from backend.utils.dice import quick_roll

                    res, raw = quick_roll(20, v)
                    log_roll(f"**{k}** Check: **{res}** (d20: {raw} + {v})")
                    st.session_state.active_roll = {
                        "label": f"{k} Check",
                        "sides": 20,
                        "raw": raw,
                        "modifier": v,
                        "total": res,
                        "adv_type": "None",
                    }
                    st.rerun()
        with col_sv:
            st.markdown("#### Saving Throws")
            saves = st.session_state.get("saving_throw_values", {})
            if saves is None:
                saves = {}
            for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                prof = stat in st.session_state.saving_throws
                indicator = "● " if prof else "○ "

                total_sv = saves.get(
                    stat, calculate_modifier(st.session_state.stats[stat])
                )

                svc1, svc2 = st.columns([4, 1])
                svc1.write(f"{indicator}**{stat}:** {total_sv}")
                if svc2.button("🎲", key=f"roll_sv_{stat}"):
                    from backend.utils.dice import quick_roll

                    res, raw = quick_roll(20, total_sv)
                    log_roll(
                        f"**{stat}** Saving Throw: **{res}** (d20: {raw} + {total_sv})"
                    )
                    st.session_state.active_roll = {
                        "label": f"{stat} Saving Throw",
                        "sides": 20,
                        "raw": raw,
                        "modifier": total_sv,
                        "total": res,
                        "adv_type": "None",
                    }
                    st.rerun()

    st.markdown("---")
    st.markdown("#### ✨ Heroic Advancements (Feats & ASI)")
    if edit_mode:
        edited_adv_df = st.data_editor(
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
        if edited_adv_df is not None:
            new_advancements = []
            import pandas as pd

            rows = (
                edited_adv_df.iterrows()
                if isinstance(edited_adv_df, pd.DataFrame)
                else enumerate(edited_adv_df)
            )
            for _, row in rows:
                new_advancements.append(
                    {
                        "level": safe_int(row.get("level"), 1),
                        "type": row.get("type") or "Feat",
                        "name": row.get("name") or "New Advancement",
                        "description": row.get("description") or "",
                    }
                )
            st.session_state.advancements = new_advancements
    else:
        if not st.session_state.advancements:
            st.write("No advancements recorded.")
        else:
            for adv in st.session_state.advancements:
                st.write(
                    f"🔹 **Lv.{adv.get('level', '?')} {adv.get('type', '')}:** {adv.get('name', '')} — *{adv.get('description', '')}*"
                )
