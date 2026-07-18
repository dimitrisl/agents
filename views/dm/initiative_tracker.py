import streamlit as st
import logging
import uuid
import os
from backend.core.storage import (
    load_campaign,
    list_characters,
    load_character,
    save_character,
    add_roll_request,
    clear_roll_requests,
)
from backend.utils.ui_utils import (
    get_image_base64,
)
from backend.services.mechanics_service import get_modifier as calculate_modifier


logger = logging.getLogger("DnDAssistant.DMView")


def _render_initiative_tracker():
    """Renders the initiative tracker (Builder & Active)."""
    st.subheader("Initiative Tracker")

    # ENCOUNTER BUILDER (Always accessible for reinforcements)
    with st.expander(
        "🛠️ Encounter Builder / Reinforcements",
        expanded=not st.session_state.get("combat_active", False),
    ):
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1, 1, 1, 1])
            name = c1.text_input(
                "Name", placeholder="e.g. Goblin", key="init_custom_name"
            )
            init = c2.number_input("Init", value=10, key="init_custom_val")
            hp = c3.number_input("HP", value=20, min_value=1, key="init_custom_hp")
            ac = c4.number_input("AC", value=10, min_value=1, key="init_custom_ac")
            dex = c5.number_input("DEX", value=10, min_value=1, key="init_custom_dex")
            qty = c6.number_input(
                "Qty", value=1, min_value=1, max_value=50, key="init_custom_qty"
            )

            b1, b2, b3 = st.columns(3)
            if b1.button("➕ Add Custom", key="add_custom_init_btn", width="stretch"):
                if name:
                    for i in range(1, qty + 1):
                        final_name = f"{name} {i}" if qty > 1 else name
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": final_name,
                                "init": init,
                                "hp": hp,
                                "max_hp": hp,
                                "ac": ac,
                                "dex": dex,
                                "portrait": "https://img.icons8.com/color/96/monster.png",
                                "conditions": [],
                                "concentration": False,
                            }
                        )
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    st.rerun()

            if b2.button(
                "👥 Import Party", key="import_party_init_btn", width="stretch"
            ):
                for member in st.session_state.party:
                    if not any(
                        c.get("name") == member["char_name"]
                        for c in st.session_state.initiative_order
                    ):
                        mod = calculate_modifier(member["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": member["char_name"],
                                "init": 10 + mod,
                                "hp": member.get("hp_max", 10),
                                "max_hp": member.get("hp_max", 10),
                                "ac": member.get("armor_class", 10),
                                "dex": member["stats"].get("DEX", 10),
                                "portrait": member.get("char_portrait"),
                                "conditions": [],
                                "concentration": False,
                            }
                        )
                st.session_state.initiative_order.sort(
                    key=lambda x: (x["init"], x["dex"]), reverse=True
                )
                st.rerun()

            if b3.button("🗑️ Clear All", key="clear_init_btn", width="stretch"):
                st.session_state.initiative_order = []
                st.session_state.combat_active = False
                st.rerun()

        st.markdown("**Load Character:**")
        lc1, lc2, lc3, lc4 = st.columns(
            [2.5, 0.8, 0.8, 0.9], vertical_alignment="bottom"
        )
        init_filtered_chars = []
        active_edition = st.session_state.get("dnd_edition", "2014 Edition")
        is_active_2024 = "2024" in active_edition
        for c_file in list_characters():
            char_data = load_character(c_file)
            if char_data:
                char_ed = char_data.get("dnd_edition", "2014 Edition")
                is_char_2024 = "2024" in char_ed
                if is_active_2024 == is_char_2024:
                    init_filtered_chars.append(c_file)

        char_file = lc1.selectbox(
            "Character", init_filtered_chars, key="load_char_init_sel"
        )
        char_qty = lc2.number_input("Qty", 1, 20, 1, key="load_char_init_qty")
        if lc3.button("Load", key="load_char_init_btn", width="stretch"):
            if char_file:
                data = load_character(char_file)
                if data:
                    for i in range(1, char_qty + 1):
                        final_name = (
                            f"{data['char_name']} {i}"
                            if char_qty > 1
                            else data["char_name"]
                        )
                        mod = calculate_modifier(data["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": final_name,
                                "init": 10 + mod,
                                "hp": data["hp_max"],
                                "max_hp": data["hp_max"],
                                "ac": data["armor_class"],
                                "dex": data["stats"]["DEX"],
                                "portrait": data.get("char_portrait"),
                                "conditions": [],
                                "concentration": False,
                            }
                        )
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    st.rerun()

        if lc4.button("Load All", key="load_all_chars_init_btn", width="stretch"):
            for c_file in init_filtered_chars:
                data = load_character(c_file)
                if data:
                    if not any(
                        c.get("name") == data["char_name"]
                        for c in st.session_state.initiative_order
                    ):
                        mod = calculate_modifier(data["stats"]["DEX"])
                        st.session_state.initiative_order.append(
                            {
                                "id": str(uuid.uuid4())[:8],
                                "name": data["char_name"],
                                "init": 10 + mod,
                                "hp": data["hp_max"],
                                "max_hp": data["hp_max"],
                                "ac": data["armor_class"],
                                "dex": data["stats"]["DEX"],
                                "portrait": data.get("char_portrait"),
                                "conditions": [],
                                "concentration": False,
                            }
                        )
            st.session_state.initiative_order.sort(
                key=lambda x: (x["init"], x["dex"]), reverse=True
            )
            st.rerun()

    if not st.session_state.get("combat_active", False):
        if st.session_state.initiative_order:
            st.markdown("---")
            st.markdown("#### 📋 Encounter Preview")
            for c in st.session_state.initiative_order:
                with st.container(border=True):
                    cp1, cp2, cp3 = st.columns([1, 4, 1])
                    p_url = c.get("portrait")
                    if not p_url or (
                        not p_url.startswith("http") and not os.path.exists(p_url)
                    ):
                        p_url = "https://img.icons8.com/color/96/monster.png"
                    cp1.image(p_url, width=40)
                    cp2.markdown(f"**{c['name']}**")
                    new_init = cp2.number_input(
                        "Initiative", value=c["init"], key=f"prev_init_{c['id']}"
                    )
                    if new_init != c["init"]:
                        c["init"] = new_init
                        st.session_state.initiative_order.sort(
                            key=lambda x: (x["init"], x["dex"]), reverse=True
                        )
                        st.rerun()

                    cp3.markdown(f"HP: {c['hp']} | AC: {c['ac']}")

            if st.button(
                "⚔️ START COMBAT",
                key="start_combat_btn",
                type="primary",
                width="stretch",
            ):
                st.session_state.combat_active = True
                st.session_state.active_turn_index = 0
                st.rerun()
    else:
        # ACTIVE COMBAT PHASE
        col_t, col_e = st.columns([3, 1])
        col_t.markdown("### ⚔️ Active Combat")
        if col_e.button("🛑 End Combat", key="end_combat_btn"):
            st.session_state.combat_active = False
            st.rerun()

        active = st.session_state.initiative_order[st.session_state.active_turn_index]

        # PREMIUM ACTIVE TURN DISPLAY
        with st.container(border=True):
            act_c1, act_c2 = st.columns([1, 4])
            p_url_active = str(active.get("portrait", ""))
            if (
                not p_url_active
                or p_url_active == "0"
                or p_url_active == "None"
                or (
                    not p_url_active.startswith("http")
                    and not os.path.exists(p_url_active)
                )
            ):
                p_url_active = "https://img.icons8.com/color/96/monster.png"
            act_c1.image(p_url_active, width=100)
            with act_c2:
                st.markdown(f"### CURRENT TURN: **{active['name']}**")
                st.markdown(
                    f"**Initiative:** {active['init']} | **AC:** {active['ac']} | **DEX:** {active['dex']}"
                )
                if st.button(
                    "⏩ NEXT TURN",
                    key="next_turn_btn",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state.active_turn_index = (
                        st.session_state.active_turn_index + 1
                    ) % len(st.session_state.initiative_order)
                    st.rerun()

        st.markdown("---")
        for i, c in enumerate(st.session_state.initiative_order):
            is_turn = i == st.session_state.active_turn_index
            border = "2px solid #ff4b4b" if is_turn else "1px solid #444"
            bg = "rgba(255, 75, 75, 0.1)" if is_turn else "transparent"

            # Sync player stats
            for p in st.session_state.party:
                if p["char_name"] == c["name"]:
                    if p.get("hp_current") is not None:
                        c["hp"] = p["hp_current"]

                    if p.get("conditions") is not None:
                        c["conditions"] = p["conditions"]

                    c["concentration"] = p.get("concentrating_on") is not None
                    if p.get("concentrating_on"):
                        c["concentrating_on"] = p.get("concentrating_on")

            # Default portrait logic
            p_url = str(c.get("portrait", ""))
            if (
                not p_url
                or p_url == "0"
                or p_url == "None"
                or (not p_url.startswith("http") and not os.path.exists(p_url))
            ):
                p_url = "https://img.icons8.com/color/96/monster.png"
            elif not p_url.startswith("http") and not p_url.startswith("data:"):
                p_url = (
                    get_image_base64(p_url)
                    or "https://img.icons8.com/color/96/monster.png"
                )

            conc_html = ""
            if c.get("concentration"):
                conc_text = c.get("concentrating_on") or "Concentrating"
                conc_html = f' <span style="color: #00ffff; margin-left: 10px; font-weight: bold;" title="{conc_text}">🧠</span>'

            with st.container():
                st.html(f"""
<div style="border: {border}; background-color: {bg}; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-family: sans-serif;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center;">
            <img src="{p_url}" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; border: 1px solid #555;">
            <div style="font-size: 1.3em; font-weight: bold; margin-right: 15px; color: #ff4b4b;">{c["init"]}</div>
            <div style="flex-grow: 1;">
                <span style="font-size: 1.1em; font-weight: bold; color: white;">{c["name"]}</span>
                {conc_html}
            </div>
        </div>
        <div style="color: #bbb; font-size: 0.9em;">AC: {c["ac"]} | DEX: {c["dex"]}</div>
    </div>
</div>
""")

                cols = st.columns([1, 1.2, 1.2, 2.5, 0.5])
                new_init = cols[0].number_input(
                    "Init",
                    value=c["init"],
                    key=f"init_act_{c['id']}_{i}",
                    label_visibility="visible",
                )
                if new_init != c["init"]:
                    c["init"] = new_init
                    # Track who is currently active to preserve their turn
                    active_id = st.session_state.initiative_order[
                        st.session_state.active_turn_index
                    ]["id"]
                    st.session_state.initiative_order.sort(
                        key=lambda x: (x["init"], x["dex"]), reverse=True
                    )
                    # Update active index
                    for idx, item in enumerate(st.session_state.initiative_order):
                        if item["id"] == active_id:
                            st.session_state.active_turn_index = idx
                            break
                    st.rerun()

                new_hp = cols[1].number_input(
                    "HP",
                    value=c["hp"],
                    key=f"hp_act_{c['id']}_{i}",
                    label_visibility="visible",
                )
                if new_hp != c["hp"]:
                    c["hp"] = new_hp

                cols[1].progress(max(0.0, min(1.0, c["hp"] / max(1, c["max_hp"]))))

                hp_adj = cols[2].number_input(
                    "+/- HP",
                    value=0,
                    key=f"hp_adj_{c['id']}_{i}",
                    label_visibility="visible",
                    help="Type negative for damage (e.g. -5) or positive to heal (e.g. 5) and press Enter.",
                )
                if hp_adj != 0:
                    c["hp"] = max(0, c["hp"] + hp_adj)
                    # Sync to player if player
                    for p in st.session_state.party:
                        if p["char_name"] == c["name"]:
                            p["hp_current"] = c["hp"]
                    st.session_state[f"hp_adj_{c['id']}_{i}"] = 0
                    st.rerun()

                c["conditions"] = cols[3].multiselect(
                    "Status",
                    [
                        "Blinded",
                        "Charmed",
                        "Frightened",
                        "Grappled",
                        "Invisible",
                        "Paralyzed",
                        "Poisoned",
                        "Prone",
                        "Restrained",
                        "Stunned",
                        "Unconscious",
                    ],
                    default=c.get("conditions", []),
                    key=f"cond_act_{c['id']}_{i}",
                    label_visibility="visible",
                )

                if cols[4].button("❌", key=f"rem_act_{c['id']}_{i}"):
                    st.session_state.initiative_order.pop(i)
                    if not st.session_state.initiative_order:
                        st.session_state.combat_active = False
                    st.rerun()

                r1, r2, r3, r4 = st.columns([1, 1.3, 1.3, 1.4])
                c["concentration"] = r1.toggle(
                    "Conc.",
                    value=c.get("concentration", False),
                    key=f"conc_act_{c['id']}_{i}",
                )

                if c.get("statblock"):
                    with r2.popover("📜 Stat"):
                        st.caption("Detailed Statblock:")
                        st.markdown(c["statblock"])
                        import re

                        clean_name = re.sub(r"\d+", "", c["name"]).strip()
                        slug = clean_name.lower().replace(" ", "-").replace("'", "")
                        url = f"https://www.dndbeyond.com/monsters/{slug}"
                        st.link_button("🌐 View Beyond", url, use_container_width=True)
                else:
                    r2.write("")

                with r3.popover("🎲 Roll"):
                    d_type = st.selectbox(
                        "Die", [20, 12, 10, 8, 6, 4], key=f"roll_d_{c['id']}_{i}"
                    )
                    mod = st.number_input("Mod", value=0, key=f"roll_m_{c['id']}_{i}")
                    if st.button("Roll", key=f"roll_b_{c['id']}_{i}"):
                        from backend.utils.dice import quick_roll

                        res, raw = quick_roll(d_type, mod)
                        st.session_state.active_roll = {
                            "label": f"{c['name']} - Quick Roll (d{d_type})",
                            "sides": d_type,
                            "raw": raw,
                            "modifier": mod,
                            "total": res,
                            "adv_type": "None",
                        }
                        st.rerun()

                with r4.popover("🖼️ Portrait"):
                    st.caption("Change Portrait:")
                    preview_portrait = p_url
                    if (
                        preview_portrait
                        and not preview_portrait.startswith("http")
                        and not preview_portrait.startswith("data:")
                    ):
                        preview_portrait = get_image_base64(preview_portrait)

                    if preview_portrait:
                        st.image(preview_portrait, width=80)

                    p_upload = st.file_uploader(
                        "Upload Image File",
                        type=["png", "jpg", "jpeg", "webp"],
                        key=f"port_up_{c['id']}_{i}",
                    )
                    p_text = st.text_input(
                        "Or Image URL",
                        value=c.get("portrait") or "",
                        key=f"port_txt_{c['id']}_{i}",
                    )

                    if st.button(
                        "Apply Portrait",
                        key=f"port_apply_{c['id']}_{i}",
                        use_container_width=True,
                    ):
                        target_portrait = None
                        if p_upload:
                            from backend.utils.image_utils import save_custom_portrait

                            file_ext = p_upload.name.split(".")[-1]
                            fname = f"{c['id']}_custom.{file_ext}"
                            target_portrait = save_custom_portrait(
                                p_upload.getbuffer(), fname
                            )
                        elif p_text:
                            target_portrait = p_text

                        if target_portrait:
                            c["portrait"] = target_portrait
                            # Also sync to character records
                            # 1. Active Party
                            for p in st.session_state.party:
                                if p["char_name"] == c["name"]:
                                    p["char_portrait"] = target_portrait
                                    save_character(p)
                            # 2. Campaign NPCs
                            if st.session_state.get("active_campaign_data"):
                                camp_data = st.session_state.active_campaign_data
                                vault_npcs = camp_data.get("vault_npcs", [])
                                for npc_file in vault_npcs:
                                    npc_data = load_character(npc_file)
                                    if npc_data and npc_data["char_name"] == c["name"]:
                                        npc_data["char_portrait"] = target_portrait
                                        save_character(npc_data)
                            st.success("Portrait updated!")
                            st.rerun()


def _render_roll_requests_section(tab_key: str):
    """Renders the private roll request widget for DMs to request and monitor rolls."""
    active_campaign = st.session_state.get("active_campaign_name")
    if not active_campaign:
        return

    camp_data = load_campaign(active_campaign)
    if not camp_data:
        return

    roll_requests = camp_data.get("roll_requests", [])

    # ---------------------------------------------------------
    # Auto-detection of new results (Session State tracked)
    # ---------------------------------------------------------
    if "last_seen_roll_ids" not in st.session_state:
        st.session_state.last_seen_roll_ids = set()

    current_completed_ids = {
        r["id"] for r in roll_requests if r.get("status") == "completed"
    }
    new_results = current_completed_ids - st.session_state.last_seen_roll_ids

    if new_results:
        for rid in new_results:
            req = next((r for r in roll_requests if r["id"] == rid), None)
            if req:
                st.toast(
                    f"🎲 **{req.get('char_name')}** rolled **{req.get('result')}**!"
                )
        st.session_state.last_seen_roll_ids.update(new_results)

    col_header, col_refresh = st.columns([4, 1])
    col_header.markdown("### 🎲 Private Roll Requests")
    if col_refresh.button(
        "🔄 Refresh", key=f"btn_refresh_rolls_{tab_key}", use_container_width=True
    ):
        st.rerun()

    col_req_form, col_req_log = st.columns([1, 1])

    with col_req_form:
        st.markdown("#### Send New Request")
        # 1. Select character from party
        party_members = st.session_state.party
        char_names = [m.get("char_name", "Hero") for m in party_members]

        if not char_names:
            st.warning("No players in party to request rolls from.")
        else:
            target_char_name = st.selectbox(
                "Select Character", char_names, key=f"dm_req_char_{tab_key}"
            )

            # Find the filename for this character
            target_member = next(
                (m for m in party_members if m.get("char_name") == target_char_name),
                None,
            )
            target_filename = ""
            if target_member:
                name = target_member.get("char_name", "unknown")
                cid = target_member.get("char_id", "unknown")
                target_filename = f"{name.replace(' ', '_').lower()}_{cid}.json"

            category = st.radio(
                "Roll Category",
                ["Ability Check", "Saving Throw", "Skill Check"],
                horizontal=True,
                key=f"dm_req_cat_{tab_key}",
            )

            if category == "Ability Check":
                stat_options = [
                    ("Strength (STR)", "STR"),
                    ("Dexterity (DEX)", "DEX"),
                    ("Constitution (CON)", "CON"),
                    ("Intelligence (INT)", "INT"),
                    ("Wisdom (WIS)", "WIS"),
                    ("Charisma (CHA)", "CHA"),
                ]
                selected_stat_label, selected_stat_key = st.selectbox(
                    "Select Ability",
                    stat_options,
                    format_func=lambda x: x[0],
                    key=f"dm_req_stat_ability_{tab_key}",
                )
                roll_type = f"{selected_stat_key} Check"
                stat = selected_stat_key
            elif category == "Saving Throw":
                stat_options = [
                    ("Strength (STR)", "STR"),
                    ("Dexterity (DEX)", "DEX"),
                    ("Constitution (CON)", "CON"),
                    ("Intelligence (INT)", "INT"),
                    ("Wisdom (WIS)", "WIS"),
                    ("Charisma (CHA)", "CHA"),
                ]
                selected_stat_label, selected_stat_key = st.selectbox(
                    "Select Saving Throw",
                    stat_options,
                    format_func=lambda x: x[0],
                    key=f"dm_req_stat_save_{tab_key}",
                )
                roll_type = f"{selected_stat_key} Saving Throw"
                stat = selected_stat_key
            else:
                skill_options = [
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
                selected_skill = st.selectbox(
                    "Select Skill", skill_options, key=f"dm_req_stat_skill_{tab_key}"
                )
                roll_type = f"{selected_skill} Check"
                stat = selected_skill

            reason = st.text_input(
                "Reason / Context (optional)",
                placeholder="e.g. To avoid falling rocks",
                key=f"dm_req_reason_{tab_key}",
            )

            is_secret = st.checkbox(
                "🔒 Make Roll Secret (Hide result from player)",
                value=False,
                key=f"dm_req_secret_{tab_key}",
            )

            if st.button(
                "📨 Request Private Roll",
                type="primary",
                use_container_width=True,
                key=f"btn_send_dm_req_{tab_key}",
            ):
                if target_filename:
                    success = add_roll_request(
                        active_campaign,
                        target_filename,
                        target_char_name,
                        roll_type,
                        stat,
                        reason,
                        is_secret=is_secret,
                    )
                    if success:
                        st.toast(f"Sent roll request to {target_char_name}!")
                        st.rerun()
                    else:
                        st.error("Failed to send roll request.")

    with col_req_log:
        st.markdown("#### Request Log")

        @st.fragment(run_every=5)
        def render_dm_req_log_fragment():
            # Re-load campaign inside fragment to get fresh results
            fresh_camp = load_campaign(active_campaign)
            if not fresh_camp:
                st.info("No active roll requests.")
                return

            fresh_requests = fresh_camp.get("roll_requests", [])

            if not fresh_requests:
                st.info("No active roll requests.")
            else:
                for req in reversed(fresh_requests):
                    status = req.get("status", "pending")
                    char_display = req.get("char_name", "Hero")
                    roll_type_display = req.get("roll_type", "Roll")
                    reason_display = req.get("reason", "")
                    is_sec = req.get("is_secret", False)
                    sec_tag = " 🔒 [SECRET]" if is_sec else ""

                    with st.container(border=True):
                        c_info, c_action = st.columns([3, 2])
                        c_info.markdown(
                            f"**{char_display}** Needs: **{roll_type_display}**{sec_tag}"
                        )
                        if reason_display:
                            c_info.caption(f'Reason: "{reason_display}"')

                        if status == "pending":
                            c_action.markdown("⏳ **Pending**")
                        elif status == "cancelled":
                            c_action.markdown("🚫 **Cancelled**")
                        else:
                            result_display = req.get("result", "??")
                            c_action.success(f"🎲 **{result_display}**")

        render_dm_req_log_fragment()

        st.write("")
        if st.button(
            "🧹 Clear Request Log",
            use_container_width=True,
            key=f"btn_clear_roll_log_{tab_key}",
        ):
            clear_roll_requests(active_campaign)
            st.success("Roll requests cleared!")
            st.rerun()
