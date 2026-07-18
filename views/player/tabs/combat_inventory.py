import streamlit as st
import logging


from views.player._helpers import log_roll, get_item_effect, trigger_sync

logger = logging.getLogger(__name__)


def _render_combat_inventory(edit_mode: bool):
    """Renders weapons and equipment sections."""
    st.markdown("#### Weapons")
    if edit_mode:
        import pandas as pd

        if "weapons_df_editor" not in st.session_state:
            st.session_state.weapons_df_editor = pd.DataFrame(st.session_state.weapons)

        st.data_editor(
            st.session_state.weapons_df_editor,
            num_rows="dynamic",
            key="edit_weapons",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Weapon Name", width="large"),
                "magic_bonus": st.column_config.NumberColumn(
                    "Magic Bonus (+X)",
                    width="small",
                    help="Magic bonus (e.g. +1, +2)",
                    step=1,
                    min_value=0,
                    max_value=100,
                ),
                "attack_bonus": st.column_config.TextColumn(
                    "To Hit", width="small", help="Attack bonus e.g. +5, -1"
                ),
                "damage_dice": st.column_config.TextColumn(
                    "Damage Dice", width="medium", help="Damage dice e.g. 1d8 slashing"
                ),
                "damage_bonus": st.column_config.TextColumn(
                    "Dmg Bonus", width="small", help="Damage bonus e.g. +3, -1"
                ),
                "is_custom": st.column_config.CheckboxColumn(
                    "Custom",
                    width="small",
                    help="Lock manual To Hit & Damage, skip auto-sync",
                ),
                "properties": st.column_config.TextColumn(
                    "Properties",
                    width="medium",
                    help="Properties (e.g., Finesse, Light, Versatile)",
                ),
                "damage": None,
                "ability_modifier": None,
            },
        )
        w_add_btn, w_add_qty = st.columns([5, 1])
        with w_add_qty:
            qty = st.number_input(
                "Qty", 1, 10, 1, key="add_weapon_qty", label_visibility="collapsed"
            )
        with w_add_btn:
            if st.button("➕ Add New Weapon(s)", use_container_width=True):
                trigger_sync()
                for _ in range(qty):
                    st.session_state.weapons.append(
                        {
                            "name": "New Weapon",
                            "magic_bonus": 0,
                            "attack_bonus": "+0",
                            "damage_dice": "1d4",
                            "damage_bonus": "+0",
                            "properties": "",
                            "range": "",
                            "is_custom": False,
                        }
                    )
                if "weapons_df_editor" in st.session_state:
                    del st.session_state["weapons_df_editor"]
                st.rerun()

    else:
        weapons = st.session_state.get("weapons", [])
        if weapons is None:
            weapons = []
        for i, w in enumerate(weapons):
            with st.container(border=True):
                # Row 1: weapon name
                w_name_col, w_roll1, w_roll2 = st.columns([3, 1, 1])
                w_name_col.markdown(f"🗡️ **{w.get('name', 'Unknown')}**")

                # Row 2: To Hit and Damage as separate labeled cells
                info_col1, info_col2, info_col3 = st.columns([1, 2, 1])
                info_col1.markdown(f"**To Hit**  \n`{w.get('attack_bonus', '+0')}`")
                info_col2.markdown(
                    f"**Damage Dice**  \n`{w.get('damage_dice', w.get('damage', '1d4'))}`"
                )
                info_col3.markdown(f"**Dmg Bonus**  \n`{w.get('damage_bonus', '+0')}`")

                # Show properties and range if present
                extra_info = []
                if w.get("properties"):
                    extra_info.append(f"**Properties:** {w.get('properties')}")
                if w.get("range"):
                    extra_info.append(f"**Range:** {w.get('range')}")
                if extra_info:
                    st.caption(" • ".join(extra_info))

                if w_roll1.button("🎯 To Hit", key=f"atk_{i}", width="stretch"):
                    from backend.utils.dice import quick_roll

                    atk_bonus_str = str(w.get("attack_bonus", "+0")).replace("+", "")
                    try:
                        atk_bonus = int(atk_bonus_str)
                    except (ValueError, TypeError):
                        atk_bonus = 0

                    global_atk = getattr(st.session_state, "global_attack_bonus", 0)
                    total_atk = atk_bonus + global_atk
                    res, raw = quick_roll(20, total_atk)

                    bonus_text = f"{atk_bonus}"
                    if global_atk:
                        bonus_text = f"{total_atk} ({atk_bonus} + {global_atk} Global)"

                    log_roll(
                        f"**{w.get('name')}** To Hit: **{res}** (d20: {raw} + {bonus_text})"
                    )
                    st.session_state.active_roll = {
                        "label": f"{w.get('name')} Attack Roll",
                        "sides": 20,
                        "raw": raw,
                        "modifier": total_atk,
                        "total": res,
                        "adv_type": "None",
                    }
                    if raw == 20:
                        st.balloons()
                    st.rerun()

                if w_roll2.button("💥 Dmg", key=f"dmg_{i}", width="stretch"):
                    from backend.utils.dice import roll_dice
                    import re
                    from backend.services.mechanics_service import (
                        rebuild_damage_formula,
                    )

                    dmg_str = w.get("damage") or rebuild_damage_formula(
                        w.get("damage_dice"), w.get("damage_bonus")
                    )
                    global_dmg = getattr(st.session_state, "global_damage_bonus", 0)
                    if global_dmg:
                        dmg_str = f"{dmg_str} + {global_dmg}"

                    res = roll_dice(dmg_str)
                    if "error" in res:
                        st.error(f"Error rolling damage: {res['error']}")
                    else:
                        log_roll(
                            f"**{w.get('name')}** Damage: **{res['total']}** ({res['result_text']})"
                        )
                        try:
                            sides = int(re.search(r"d(\d+)", dmg_str).group(1))
                        except Exception:
                            sides = 6

                        rolls = res.get("rolls", [1])
                        st.session_state.active_roll = {
                            "label": f"{w.get('name')} Damage",
                            "sides": sides,
                            "raw": rolls if len(rolls) > 1 else rolls[0],
                            "raw_selected": sum(rolls),
                            "modifier": res.get("modifier", 0),
                            "total": res.get("total", 1),
                            "adv_type": "None",
                        }
                        st.rerun()

    # 5.5e Weapon Masteries
    if st.session_state.dnd_edition == "2024 Revision (5.5e)":
        st.markdown("#### ⚔️ Weapon Masteries")
        if edit_mode:
            from backend.core.constants import WEAPON_MASTERIES_2024

            st.session_state.weapon_masteries = st.multiselect(
                "Mastered Properties:",
                options=WEAPON_MASTERIES_2024,
                default=st.session_state.weapon_masteries,
            )
        else:
            if st.session_state.weapon_masteries:
                cols = st.columns(len(st.session_state.weapon_masteries))
                for idx, mastery in enumerate(st.session_state.weapon_masteries):
                    with cols[idx]:
                        st.info(f"**{mastery}**")
            else:
                st.write("No weapon masteries unlocked.")

    st.markdown("#### Equipment")
    import pandas as pd
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _rules_repo.get_all_items()

    # Standardize equipment format (List of Dicts)
    current_equip = []
    attuned_count = 0
    equipment = st.session_state.get("equipment", [])
    if equipment is None:
        equipment = []
    for e in equipment:
        if isinstance(e, dict):
            item_name = e.get("name", "")
            item_data = next(
                (i for i in all_items if i["name"].lower() == item_name.lower()), None
            )

            display_ac = e.get("ac_bonus", 0)
            if display_ac == 0 and item_data:
                if "ac_base" in item_data:
                    display_ac = item_data["ac_base"]
                elif "ac_bonus" in item_data:
                    display_ac = item_data["ac_bonus"]

            item_dict = {
                "Item": item_name,
                "Equipped": e.get("equipped", False),
                "Attuned": e.get("attuned", False),
                "AC": display_ac,
                "Mod 1": e.get("mod1", "None"),
                "Val 1": e.get("val1", 0),
                "Mod 2": e.get("mod2", "None"),
                "Val 2": e.get("val2", 0),
            }
            current_equip.append(item_dict)
            if e.get("attuned", False):
                attuned_count += 1
        else:
            # Handle string/object fallbacks
            name = e if isinstance(e, str) else getattr(e, "name", "Unknown Item")
            current_equip.append(
                {
                    "Item": name,
                    "Equipped": False,
                    "Attuned": False,
                    "AC": 0,
                    "Mod 1": "None",
                    "Val 1": 0,
                    "Mod 2": "None",
                    "Val 2": 0,
                }
            )

    if edit_mode:
        # --- Inventory Header with Stats ---
        col_inv1, col_inv2 = st.columns([2, 2])
        att_color = "red" if attuned_count > 3 else "green"
        col_inv1.markdown(f"📊 **Attunement:** :{att_color}[{attuned_count} / 3]")
        col_inv2.markdown(f"🛡️ **Total AC:** {st.session_state.armor_class}")

        st.caption(
            "💡 **Tip:** Manually set bonuses (e.g., ATK, STR, HP) in the Mod/Val columns."
        )

        equip_df = pd.DataFrame(current_equip)
        if equip_df.empty:
            equip_df = pd.DataFrame(
                columns=["Item", "Equipped", "AC", "Mod 1", "Val 1", "Mod 2", "Val 2"]
            )

        attr_options = [
            "None",
            "STR",
            "DEX",
            "CON",
            "INT",
            "WIS",
            "CHA",
            "HP",
            "SPD",
            "INIT",
            "ATK",
            "DMG",
            "SAVES",
        ]

        if "equip_df_editor" not in st.session_state:
            st.session_state.equip_df_editor = equip_df

        st.data_editor(
            st.session_state.equip_df_editor,
            num_rows="dynamic",
            key="edit_equip_table",
            use_container_width=True,
            column_config={
                "Item": st.column_config.TextColumn("Item", width="large"),
                "Equipped": st.column_config.CheckboxColumn("Equipped", width="small"),
                "Attuned": st.column_config.CheckboxColumn("Attuned", width="small"),
                "AC": st.column_config.NumberColumn("AC", width="small"),
                "Mod 1": st.column_config.SelectboxColumn(
                    "Mod 1", options=attr_options, width="medium"
                ),
                "Val 1": st.column_config.NumberColumn("Val 1", width="small"),
                "Mod 2": st.column_config.SelectboxColumn(
                    "Mod 2", options=attr_options, width="medium"
                ),
                "Val 2": st.column_config.NumberColumn("Val 2", width="small"),
            },
        )
        e_add_btn, e_add_qty = st.columns([5, 1])
        with e_add_qty:
            qty = st.number_input(
                "Qty", 1, 10, 1, key="add_item_qty", label_visibility="collapsed"
            )
        with e_add_btn:
            if st.button("➕ Add New Item(s)", width="stretch"):
                # To add an item, we must trigger sync to save pending edits first,
                # then append the new item and rerun.
                trigger_sync()
                for _ in range(qty):
                    st.session_state.equipment.append(
                        {
                            "name": "New Item",
                            "equipped": False,
                            "attuned": False,
                            "ac_bonus": 0,
                            "mod1": "None",
                            "val1": 0,
                            "mod2": "None",
                            "val2": 0,
                        }
                    )
                if "equip_df_editor" in st.session_state:
                    del st.session_state["equip_df_editor"]
                st.rerun()
    else:
        if current_equip:
            display_data = []
            for e in current_equip:
                manual_desc = []
                if e["AC"]:
                    manual_desc.append(f"+{e['AC']} AC")
                if e["Mod 1"] != "None":
                    manual_desc.append(f"+{e['Val 1']} {e['Mod 1']}")
                if e["Mod 2"] != "None":
                    manual_desc.append(f"+{e['Val 2']} {e['Mod 2']}")

                kb_effect = get_item_effect(e["Item"])
                final_effect = kb_effect
                if manual_desc:
                    final_effect = f"{kb_effect} | Custom: {', '.join(manual_desc)}"

                display_data.append(
                    {
                        "Equipped": "✅" if e["Equipped"] else "❌",
                        "Item": e["Item"],
                        "Effect": final_effect,
                    }
                )
            st.table(display_data)
        else:
            st.write("Inventory is empty.")
