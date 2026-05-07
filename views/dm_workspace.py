import streamlit as st
import logging
import uuid
from backend.ai_client import (
    forge_character,
    generate_session_prep,
    generate_npc,
    generate_random_encounter,
    generate_riddle,
)
from backend.storage import (
    save_campaign,
    load_campaign,
    list_campaigns,
    list_characters,
    load_character,
)
from backend.image_utils import generate_portrait_url
from backend.calculations import calculate_modifier
from backend.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    SPECIES_2024,
    CLASSES_2024,
)

logger = logging.getLogger("DnDAssistant.DMView")


def render_dm_workspace():
    """Renders the main Dungeon Master Workspace view."""
    st.title("Dungeon Master Workspace")

    if not st.session_state.get("active_campaign_name"):
        st.info(
            "👋 Welcome to the Dungeon Master Workspace! Please select or create a Campaign to begin."
        )
        _render_campaign_selection()
    else:
        col_title, col_close = st.columns([4, 1], vertical_alignment="center")
        col_title.markdown(
            f"### Active Campaign: **{st.session_state.active_campaign_name}**"
        )
        if col_close.button(
            "🚪 Close Campaign", key="close_camp_btn", use_container_width=True
        ):
            st.session_state.active_campaign_name = None
            st.rerun()

        dm_tab1, dm_tab2, dm_tab3, dm_tab4, dm_tab5 = st.tabs(
            [
                "📝 Campaign Notes",
                "👥 Party Manager",
                "📊 Party Dashboard",
                "🎲 AI Generators",
                "⚔️ Initiative Tracker",
            ]
        )

        with dm_tab1:
            _render_campaign_notes()

        with dm_tab2:
            _render_party_tracker()

        with dm_tab3:
            _render_party_dashboard()

        with dm_tab4:
            _render_ai_generators()

        with dm_tab5:
            _render_initiative_tracker()


def _render_campaign_selection():
    """Renders the screen to load or create a campaign."""
    with st.container(border=True):
        st.subheader("Load Existing Campaign")
        camp_list = list_campaigns()
        if camp_list:
            selected_camp = st.selectbox(
                "Select Campaign", camp_list, key="sel_camp_main"
            )
            if st.button(
                "Load Campaign",
                type="primary",
                key="load_camp_btn",
                use_container_width=True,
            ):
                data = load_campaign(selected_camp)
                if data:
                    st.session_state.campaign_notes = data.get("notes", "")
                    st.session_state.active_campaign_name = selected_camp
                    st.session_state.campaign_party_files = data.get("party", [])

                    # Automatically populate the party in session state
                    st.session_state.party = []
                    for f in st.session_state.campaign_party_files:
                        char_data = load_character(f)
                        if char_data:
                            st.session_state.party.append(char_data)

                    logger.info(
                        f"Loaded campaign: {selected_camp} with {len(st.session_state.party)} members."
                    )
                    st.toast(f"Loaded campaign: {selected_camp}")
                    st.rerun()
        else:
            st.write("No saved campaigns found.")

    with st.container(border=True):
        st.subheader("Start New Campaign")
        new_camp_name = st.text_input(
            "Campaign Name", placeholder="e.g., Curse of Strahd", key="new_camp_input"
        )
        if st.button(
            "Create Campaign", key="create_camp_btn", use_container_width=True
        ):
            if new_camp_name:
                st.session_state.active_campaign_name = new_camp_name
                st.session_state.campaign_notes = ""
                save_campaign(new_camp_name, "")
                st.rerun()
            else:
                st.warning("Please enter a campaign name.")


def _render_campaign_notes():
    """Renders the session logs and campaign management tools."""
    st.subheader("Session Logs & Lore")

    with st.expander("➕ Log New Session", expanded=False):
        new_log = st.text_area(
            "What happened in this session?", height=150, key="new_session_log"
        )
        if st.button("Append to Campaign Notes", type="primary", key="append_log_btn"):
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d")
            st.session_state.campaign_notes += (
                f"\n\n--- Session: {timestamp} ---\n{new_log}"
            )
            st.toast("Session log appended!")
            st.rerun()

    st.session_state.campaign_notes = st.text_area(
        "Full Master Lore & Notes:",
        st.session_state.campaign_notes,
        height=400,
        key="master_notes_area",
    )

    with st.container(border=True):
        st.markdown("#### Save Campaign")
        if st.button(
            "💾 Save Notes",
            type="primary",
            key="save_notes_btn",
            use_container_width=True,
        ):
            if save_campaign(
                st.session_state.active_campaign_name, st.session_state.campaign_notes
            ):
                st.toast("Notes saved successfully!")
            else:
                st.error("Failed to save notes.")

    st.markdown("---")
    st.subheader("✨ AI Session Prep")
    if st.button(
        "Generate Next Session Prep", key="gen_prep_btn", use_container_width=True
    ):
        party_info = (
            ", ".join(
                [
                    f"{c['char_name']} ({c['race']} {c['char_class']} Lv.{c['char_level']})"
                    for c in st.session_state.party
                ]
            )
            if st.session_state.party
            else "No party members loaded."
        )
        with st.spinner("Brainstorming plot hooks..."):
            st.session_state.session_prep_result = generate_session_prep(
                st.session_state.campaign_notes, party_info
            )

    if st.session_state.session_prep_result:
        st.info(st.session_state.session_prep_result)


def _render_party_tracker():
    """Renders the player character ingestion and tracking tools."""
    st.subheader("Party Management")

    with st.expander("📥 Ingest Characters from Storage", expanded=False):
        joined_files = st.session_state.get("campaign_party_files", [])
        if joined_files:
            st.info(f"There are {len(joined_files)} players who joined this campaign.")
            if st.button(
                "👥 Sync All Joined Players",
                key="sync_joined_btn",
                use_container_width=True,
            ):
                for f in joined_files:
                    char_data = load_character(f)
                    if char_data and not any(
                        c.get("char_id") == char_data.get("char_id")
                        for c in st.session_state.party
                    ):
                        st.session_state.party.append(char_data)
                st.success("Synced joined players!")
                st.rerun()
            st.markdown("---")

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
            if st.button(
                "Add to Party", key="add_to_party_btn", use_container_width=True
            ):
                char_data = load_character(char_to_add)
                if char_data:
                    if "char_id" not in char_data:
                        char_data["char_id"] = str(uuid.uuid4())[:8]
                    if any(
                        c.get("char_id") == char_data.get("char_id")
                        for c in st.session_state.party
                    ):
                        st.warning(f"{char_data['char_name']} is already in the party.")
                    else:
                        st.session_state.party.append(char_data)

                        # Persist to campaign file
                        from backend.storage import join_campaign

                        join_campaign(
                            st.session_state.active_campaign_name, char_to_add
                        )

                        st.success(f"Added {char_data['char_name']} to the party!")
                        st.rerun()

    with st.expander("✨ AI Quick Forge", expanded=False):
        q_edition = st.session_state.dnd_edition
        q_race_options = RACES_2014 if q_edition == EDITION_2014 else SPECIES_2024
        q_class_options = CLASSES_2014 if q_edition == EDITION_2014 else CLASSES_2024

        q_race = st.selectbox(
            "Race/Species", ["AI Choice"] + q_race_options, key="q_race"
        )
        q_class = st.selectbox("Class", ["AI Choice"] + q_class_options, key="q_class")
        q_level = st.number_input("Level", 1, 20, 1, key="q_level")
        q_name = st.text_input("Name (optional)", placeholder="AI Choice", key="q_name")
        q_concept = st.text_input("Concept", key="q_concept")

        if st.button("Forge & Add", key="forge_add_btn", use_container_width=True):
            with st.spinner("Forging & Generating Portrait..."):
                result = forge_character(
                    q_level,
                    q_race,
                    q_class,
                    "AI Choice",
                    q_concept,
                    name=q_name if q_name.strip() else "AI Choice",
                    edition=q_edition,
                )
                if result:
                    result["char_id"] = str(uuid.uuid4())[:8]
                    # Generate and save portrait
                    portrait_path = generate_portrait_url(result)
                    if portrait_path:
                        result["char_portrait"] = portrait_path

                    # Save to disk
                    from backend.storage import save_character

                    if save_character(result):
                        st.session_state.party.append(result)

                        # Persist to campaign file
                        from backend.storage import join_campaign

                        char_filename = f"{result['char_name'].replace(' ', '_').lower()}_{result['char_id']}.json"
                        join_campaign(
                            st.session_state.active_campaign_name, char_filename
                        )

                        st.success(f"Forged and saved {result['char_name']}!")
                        st.rerun()
                    else:
                        st.error("Failed to save forged character.")

    st.markdown("---")
    if not st.session_state.party:
        st.info("The party is currently empty.")
    else:
        for i, member in enumerate(st.session_state.party):
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 0.5])
                c1.markdown(f"**{member['char_name']}**")
                c1.caption(
                    f"{member['race']} {member['char_class']} (Lv.{member['char_level']})"
                )
                c2.metric("HP", f"{member['hp_max']}")
                c3.metric("AC", f"{member['armor_class']}")
                pp = 10 + calculate_modifier(member["stats"]["WIS"])
                c4.metric("Perc.", f"{pp}")
                if c5.button("🗑️", key=f"rem_party_{i}"):
                    from backend.storage import remove_from_campaign

                    char_id = member.get("char_id")
                    char_filename = f"{member['char_name'].replace(' ', '_').lower()}_{char_id}.json"

                    # Remove from the session state party
                    st.session_state.party.pop(i)

                    # Also remove from the campaign storage if it's there
                    remove_from_campaign(
                        st.session_state.active_campaign_name, char_filename
                    )

                    # Update the campaign_party_files in session state to reflect storage change
                    data = load_campaign(st.session_state.active_campaign_name)
                    if data:
                        st.session_state.campaign_party_files = data.get("party", [])

                    st.rerun()


def _render_ai_generators():
    """Renders the random encounter and NPC generator tools."""
    st.subheader("AI Generators")
    gen_type = st.radio("Type", ["Random Encounter", "NPC"], key="ai_gen_type")
    st.markdown("---")

    if gen_type == "Random Encounter":
        col1, col2 = st.columns(2)
        party_size = col1.number_input("Party Size", 1, 10, 4, key="enc_p_size")
        avg_level = col2.number_input("Avg Level", 1, 20, 5, key="enc_p_level")
        location = st.text_input("Location", "Dungeon", key="enc_loc")

        if st.button("Generate Encounter", key="gen_enc_btn", use_container_width=True):
            with st.spinner("Generating Encounter..."):
                st.session_state.encounter_result = generate_random_encounter(
                    party_size,
                    avg_level,
                    location,
                    edition=st.session_state.dnd_edition,
                )
                st.session_state.riddle_result = None  # Clear previous riddle

        if st.button(
            "✨ Generate Thematic Riddle",
            key="gen_riddle_btn",
            use_container_width=True,
        ):
            with st.spinner("Crafting a puzzle..."):
                st.session_state.riddle_result = generate_riddle(
                    location, edition=st.session_state.dnd_edition
                )
        if st.session_state.encounter_result:
            res = st.session_state.encounter_result
            if isinstance(res, dict):
                st.markdown(res.get("encounter_text", ""))
                if res.get("monsters"):
                    st.markdown("---")
                    st.markdown("#### 🧟 Monsters in this Encounter:")
                    for m in res["monsters"]:
                        qty = m.get("quantity", 1)
                        st.write(
                            f"- **{m['name']}** (x{qty}) | HP: {m.get('hp')} | AC: {m.get('ac')}"
                        )

                    if st.button(
                        "⚔️ Add Monsters to Initiative",
                        key="add_enc_to_init",
                        use_container_width=True,
                        type="primary",
                    ):
                        for m in res["monsters"]:
                            qty = m.get("quantity", 1)
                            for i in range(1, qty + 1):
                                name = f"{m['name']} {i}" if qty > 1 else m["name"]
                                # Basic initiative roll based on DEX
                                dex_val = m.get("dex", 10)
                                dex_mod = (dex_val - 10) // 2
                                from backend.dice import quick_roll

                                init_roll, _ = quick_roll(20, dex_mod)

                                st.session_state.initiative_order.append(
                                    {
                                        "id": str(uuid.uuid4())[:8],
                                        "name": name,
                                        "init": init_roll,
                                        "hp": m.get("hp", 10),
                                        "max_hp": m.get("hp", 10),
                                        "ac": m.get("ac", 10),
                                        "dex": dex_val,
                                        "portrait": "https://img.icons8.com/color/96/monster.png",
                                        "conditions": [],
                                        "concentration": False,
                                        "statblock": m.get("statblock_summary", ""),
                                    }
                                )
                        st.session_state.initiative_order.sort(
                            key=lambda x: (x["init"], x["dex"]), reverse=True
                        )
                        st.success("Monsters added to initiative tracker!")
                        st.toast("Check the Initiative Tracker tab.")
                        st.rerun()
                else:
                    st.warning(
                        "No monsters were extracted for this encounter. You'll need to add them manually to initiative."
                    )
            else:
                # Legacy or failed JSON fallback
                st.info(res)
                st.warning(
                    "⚠️ This encounter is in 'Legacy Format' or failed to generate monster data. Click 'Generate Encounter' again to enable the Initiative Tracker integration."
                )

        if st.session_state.get("riddle_result"):
            st.markdown("---")
            with st.container(border=True):
                st.markdown("### 🧩 The Oracle's Riddle")
                st.markdown(st.session_state.riddle_result)
                if st.button("🗑️ Clear Riddle", key="clear_riddle_btn"):
                    st.session_state.riddle_result = None
                    st.rerun()
    else:
        npc_concept = st.text_input(
            "Concept", "A sketchy merchant", key="npc_concept_input"
        )
        if st.button("Generate NPC", key="gen_npc_btn"):
            with st.spinner("Forging..."):
                st.session_state.npc_result = generate_npc(
                    npc_concept, edition=st.session_state.dnd_edition
                )
        if st.session_state.npc_result:
            st.info(st.session_state.npc_result)


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
            if b1.button(
                "➕ Add Custom", key="add_custom_init_btn", use_container_width=True
            ):
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
                "👥 Import Party", key="import_party_init_btn", use_container_width=True
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

            if b3.button("🗑️ Clear All", key="clear_init_btn", use_container_width=True):
                st.session_state.initiative_order = []
                st.session_state.combat_active = False
                st.rerun()

        st.markdown("**Load Character:**")
        lc1, lc2, lc3 = st.columns([3, 1, 1], vertical_alignment="bottom")
        char_file = lc1.selectbox(
            "Character", list_characters(), key="load_char_init_sel"
        )
        char_qty = lc2.number_input("Qty", 1, 20, 1, key="load_char_init_qty")
        if lc3.button("Load", key="load_char_init_btn", use_container_width=True):
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

    if not st.session_state.get("combat_active", False):
        if st.session_state.initiative_order:
            st.markdown("---")
            st.markdown("#### 📋 Encounter Preview")
            for c in st.session_state.initiative_order:
                with st.container(border=True):
                    cp1, cp2, cp3 = st.columns([1, 4, 1])
                    p_url = (
                        c.get("portrait")
                        if c.get("portrait")
                        else "https://img.icons8.com/color/96/monster.png"
                    )
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
                use_container_width=True,
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
            p_url_active = (
                active.get("portrait")
                if active.get("portrait")
                else "https://img.icons8.com/color/96/monster.png"
            )
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
                    use_container_width=True,
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

            # Default portrait logic
            p_url = (
                c.get("portrait")
                if c.get("portrait")
                else "https://img.icons8.com/color/96/monster.png"
            )

            with st.container():
                st.html(f"""
<div style="border: {border}; background-color: {bg}; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-family: sans-serif;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center;">
            <img src="{p_url}" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; border: 1px solid #555;">
            <div style="font-size: 1.3em; font-weight: bold; margin-right: 15px; color: #ff4b4b;">{c["init"]}</div>
            <div style="flex-grow: 1;">
                <span style="font-size: 1.1em; font-weight: bold; color: white;">{c["name"]}</span>
                {' <span style="color: #ff4b4b; margin-left: 10px; font-weight: bold;">[CONC]</span>' if c.get("concentration") else ""}
            </div>
        </div>
        <div style="color: #bbb; font-size: 0.9em;">AC: {c["ac"]} | DEX: {c["dex"]}</div>
    </div>
</div>
""")

                cols = st.columns([1, 1.5, 2, 2, 0.5])
                new_init = cols[0].number_input(
                    "Init",
                    value=c["init"],
                    key=f"init_act_{c['id']}_{i}",
                    label_visibility="collapsed",
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
                    label_visibility="collapsed",
                )
                if new_hp != c["hp"]:
                    c["hp"] = new_hp

                cols[1].progress(max(0.0, min(1.0, c["hp"] / max(1, c["max_hp"]))))
                c["conditions"] = cols[2].multiselect(
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
                    label_visibility="collapsed",
                )

                if cols[3].button("❌", key=f"rem_act_{c['id']}_{i}"):
                    st.session_state.initiative_order.pop(i)
                    if not st.session_state.initiative_order:
                        st.session_state.combat_active = False
                    st.rerun()

                r1, r2, r3 = st.columns([1, 2, 2])
                c["concentration"] = r1.toggle(
                    "Conc.",
                    value=c.get("concentration", False),
                    key=f"conc_act_{c['id']}_{i}",
                )

                if c.get("statblock"):
                    with r2.popover("📜 Statblock"):
                        st.caption("Quick Reference:")
                        st.write(c["statblock"])

                with r3.popover("🎲 Quick Roll"):
                    d_type = st.selectbox(
                        "Die", [20, 12, 10, 8, 6, 4], key=f"roll_d_{c['id']}_{i}"
                    )
                    mod = st.number_input("Mod", value=0, key=f"roll_m_{c['id']}_{i}")
                    if st.button("Roll", key=f"roll_b_{c['id']}_{i}"):
                        from backend.dice import quick_roll

                        res, raw = quick_roll(d_type, mod)
                        st.toast(f"🎲 {c['name']} rolled: {res}")


def _render_party_dashboard():
    """Renders the high-level party overview."""
    st.subheader("Party Dashboard")
    if not st.session_state.party:
        st.info("Party is empty.")
        return

    cols = st.columns(3)
    for i, member in enumerate(st.session_state.party):
        with cols[i % 3]:
            with st.container(border=True):
                c1, c2 = st.columns([1, 2])
                if member.get("char_portrait"):
                    c1.image(member["char_portrait"], width=80)
                else:
                    c1.markdown("👤")

                c2.markdown(f"#### {member.get('char_name', 'Hero')}")
                c2.caption(f"{member['race']} {member['char_class']}")

                st.markdown("---")
                s1, s2, s3 = st.columns(3)
                s1.metric("HP", f"{member.get('hp_max')}")
                s2.metric("AC", member.get("armor_class"))
                pp = 10 + calculate_modifier(member["stats"]["WIS"])
                s3.metric("Perc.", f"{pp}")

                st.markdown("**Ability Checks:**")
                r_cols = st.columns(3)
                for j, stat in enumerate(["STR", "DEX", "CON", "INT", "WIS", "CHA"]):
                    mod = calculate_modifier(member["stats"][stat])
                    mod_str = f"+{mod}" if mod >= 0 else str(mod)
                    if r_cols[j % 3].button(
                        f"{stat}\n{mod_str}", key=f"dash_roll_{stat}_{i}"
                    ):
                        from backend.dice import quick_roll

                        res, raw = quick_roll(20, mod)
                        st.toast(f"{member['char_name']} rolled {stat}: {res}")
