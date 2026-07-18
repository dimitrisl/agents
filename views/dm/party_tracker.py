import streamlit as st
import logging
import uuid
from backend.core.storage import (
    load_campaign,
    list_characters,
    load_character,
)
from backend.services.mechanics_service import get_modifier as calculate_modifier


logger = logging.getLogger("DnDAssistant.DMView")


def _render_party_tracker():
    """Renders the player character ingestion and tracking tools."""
    st.subheader("Party Management")

    active_edition = st.session_state.get("dnd_edition", "2014 Edition")
    is_active_2024 = "2024" in active_edition

    # ── Invite Players by Username ────────────────────────────────────────────
    with st.expander("👤 Invite a Player", expanded=True):
        from backend.repositories.user_repository import UserRepository as _UserRepo
        from backend.repositories.character_repository import (
            CharacterRepository as _CharRepo,
        )

        active_campaign = st.session_state.get("active_campaign_name")
        if not active_campaign:
            st.warning("No active campaign.")
        else:
            _ur = _UserRepo()
            all_users = _ur.list_all()
            dm_user = st.session_state.get("user", {})
            dm_id = dm_user.get("id", "")

            # Exclude the DM from the player list
            player_users = [
                u for u in all_users if f"local_user_{u['username']}" != dm_id
            ]

            if not player_users:
                st.info("No other registered players found.")
            else:
                user_options = {
                    u["name"]: f"local_user_{u['username']}" for u in player_users
                }
                selected_display = st.selectbox(
                    "Select Player",
                    list(user_options.keys()),
                    key="dm_invite_select_user",
                )
                selected_owner_id = user_options[selected_display]

                # Load that player's characters
                _cr = _CharRepo()
                player_chars = _cr.list_all(owner_id=selected_owner_id)

                if not player_chars:
                    st.caption(f"{selected_display} has no characters yet.")
                else:
                    char_options = {}
                    for fname in player_chars:
                        cdata = _cr.load(fname)
                        if cdata:
                            label = f"{cdata['char_name']} (Lv.{cdata.get('char_level', 1)} {cdata.get('char_class', '')})"
                            char_options[label] = (fname, cdata)

                    if char_options:
                        selected_char_labels = st.multiselect(
                            "Select Character(s) to Add",
                            list(char_options.keys()),
                            key="dm_invite_select_char",
                        )

                        if selected_char_labels:
                            to_add = []
                            already_in_names = []
                            for label in selected_char_labels:
                                fname, cdata = char_options[label]
                                already_in = any(
                                    c.get("char_id") == cdata.get("char_id")
                                    for c in st.session_state.party
                                )
                                if already_in:
                                    already_in_names.append(cdata["char_name"])
                                else:
                                    to_add.append((fname, cdata))

                            if already_in_names:
                                st.info(
                                    f"Already in party: {', '.join(already_in_names)}"
                                )

                            if to_add:
                                if st.button(
                                    f"➕ Add {len(to_add)} Character(s) to Party",
                                    type="primary",
                                    use_container_width=True,
                                    key="dm_invite_add_btn",
                                ):
                                    from backend.core.storage import join_campaign

                                    for fname, cdata in to_add:
                                        st.session_state.party.append(cdata)
                                        join_campaign(active_campaign, fname)
                                    st.success(
                                        f"✅ Added {len(to_add)} character(s) to party!"
                                    )
                                    st.rerun()

    with st.expander("📥 Ingest Characters from Storage", expanded=False):
        joined_files = st.session_state.get("campaign_party_files", [])
        if joined_files:
            st.info(f"There are {len(joined_files)} players who joined this campaign.")
            if st.button(
                "👥 Sync All Joined Players",
                key="sync_joined_btn",
                width="stretch",
            ):
                for f in joined_files:
                    char_data = load_character(f)
                    if char_data:
                        char_ed = char_data.get("dnd_edition", "2014 Edition")
                        is_char_2024 = "2024" in char_ed
                        if is_active_2024 == is_char_2024:
                            if not any(
                                c.get("char_id") == char_data.get("char_id")
                                for c in st.session_state.party
                            ):
                                st.session_state.party.append(char_data)
                st.success("Synced joined players!")
                st.rerun()
            st.markdown("---")

        available_chars = list_characters()
        if available_chars:
            filtered_chars = []
            for char_file in available_chars:
                char_data = load_character(char_file)
                if char_data:
                    if char_data.get("is_npc", False):
                        continue
                    char_ed = char_data.get("dnd_edition", "2014 Edition")
                    is_char_2024 = "2024" in char_ed
                    if is_active_2024 == is_char_2024:
                        filtered_chars.append(char_file)

            if filtered_chars:

                def format_char_filename(fname):
                    return fname.replace(".json", "").replace("_", " ").title()

                chars_to_add = st.multiselect(
                    "Select Character(s) to Add",
                    filtered_chars,
                    format_func=format_char_filename,
                    key="dm_ingest_select",
                )
                if st.button(
                    "Add Selected to Party", key="add_to_party_btn", width="stretch"
                ):
                    if not chars_to_add:
                        st.warning("Please select at least one character.")
                    else:
                        from backend.core.storage import join_campaign

                        added_names = []
                        already_in_party = []

                        for char_file in chars_to_add:
                            char_data = load_character(char_file)
                            if char_data:
                                if "char_id" not in char_data:
                                    char_data["char_id"] = str(uuid.uuid4())[:8]

                                if any(
                                    c.get("char_id") == char_data.get("char_id")
                                    for c in st.session_state.party
                                ):
                                    already_in_party.append(char_data["char_name"])
                                else:
                                    st.session_state.party.append(char_data)
                                    join_campaign(
                                        st.session_state.active_campaign_name, char_file
                                    )
                                    added_names.append(char_data["char_name"])

                        if added_names:
                            st.success(f"Successfully added: {', '.join(added_names)}")
                        if already_in_party:
                            st.warning(
                                f"Already in party: {', '.join(already_in_party)}"
                            )
                        st.rerun()
            else:
                st.info(
                    f"No characters found matching the {'2024 Revision' if is_active_2024 else '2014 Edition'}."
                )

    st.markdown("---")
    if not st.session_state.party:
        st.info("The party is currently empty.")
    else:
        with st.expander("🗑️ Bulk Remove from Party", expanded=False):
            member_options = {}
            for member in st.session_state.party:
                m_id = member.get("char_id")
                m_fname = f"{member['char_name'].replace(' ', '_').lower()}_{m_id}.json"
                label = f"{member['char_name']} (Lv.{member['char_level']} {member['char_class']})"
                member_options[label] = (member, m_fname)

            selected_to_remove = st.multiselect(
                "Select Character(s) to Remove",
                list(member_options.keys()),
                key="dm_bulk_remove_select",
            )
            if selected_to_remove:
                if st.button(
                    f"🗑️ Remove {len(selected_to_remove)} Character(s)",
                    type="primary",
                    use_container_width=True,
                    key="dm_bulk_remove_btn",
                ):
                    from backend.core.storage import remove_from_campaign

                    for label in selected_to_remove:
                        member_to_rem, m_fname = member_options[label]
                        st.session_state.party = [
                            c
                            for c in st.session_state.party
                            if c.get("char_id") != member_to_rem.get("char_id")
                        ]
                        remove_from_campaign(
                            st.session_state.active_campaign_name, m_fname
                        )

                    data = load_campaign(st.session_state.active_campaign_name)
                    if data:
                        st.session_state.campaign_party_files = data.get("party", [])
                    st.success(
                        f"Removed {len(selected_to_remove)} character(s) from campaign!"
                    )
                    st.rerun()

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
                    from backend.core.storage import remove_from_campaign

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
                import os

                portrait = member.get("char_portrait")
                if portrait and os.path.exists(portrait):
                    c1.image(portrait, width=80)
                else:
                    c1.markdown("👤")

                c2.markdown(f"#### {member.get('char_name', 'Hero')}")
                c2.caption(f"{member['race']} {member['char_class']}")
                c2.caption(f"👤 Owner: `{member.get('owner_id', 'Unknown')}`")

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
                        from backend.utils.dice import quick_roll

                        res, raw = quick_roll(20, mod)
                        st.session_state.active_roll = {
                            "label": f"{member['char_name']} - {stat} Check",
                            "sides": 20,
                            "raw": raw,
                            "modifier": mod,
                            "total": res,
                            "adv_type": "None",
                        }
                        st.rerun()
