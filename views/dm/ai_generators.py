import streamlit as st
import logging
import uuid
from backend.services.dm_service import (
    generate_npc,
    generate_random_encounter,
    generate_riddle,
)
from backend.utils.ui_utils import (
    render_themed_markdown,
)


logger = logging.getLogger("DnDAssistant.DMView")


def _render_ai_generators():
    """Renders the random encounter and NPC generator tools."""
    st.subheader("AI Generators")
    gen_type = st.radio("Type", ["Random Encounter", "NPC"], key="ai_gen_type")
    st.markdown("---")

    if gen_type == "Random Encounter":
        col1, col2, col3 = st.columns(3)
        party_size = col1.number_input("Party Size", 1, 10, 4, key="enc_p_size")
        avg_level = col2.number_input("Avg Level", 1, 20, 5, key="enc_p_level")
        difficulty_label = col3.selectbox(
            "Difficulty",
            ["Low (Χαμηλή)", "Medium (Κανονική)", "High (Υψηλή)"],
            index=1,
            key="enc_diff_label",
        )
        difficulty = difficulty_label.split(" ")[0]

        location = st.text_input("Location", "Dungeon", key="enc_loc")

        if st.button("Generate Encounter", key="gen_enc_btn", width="stretch"):
            with st.spinner("Generating Encounter..."):
                st.session_state.encounter_result = generate_random_encounter(
                    party_size,
                    avg_level,
                    location,
                    edition=st.session_state.dnd_edition,
                    difficulty=difficulty,
                )
                st.session_state.riddle_result = None  # Clear previous riddle

        if st.button(
            "✨ Generate Thematic Riddle",
            key="gen_riddle_btn",
            width="stretch",
        ):
            with st.spinner("Crafting a puzzle..."):
                st.session_state.riddle_result = generate_riddle(
                    location, edition=st.session_state.dnd_edition
                )
        if st.session_state.get("encounter_result"):
            res = st.session_state.encounter_result
            if isinstance(res, dict):
                render_themed_markdown(res.get("encounter_text", ""))
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
                        width="stretch",
                        type="primary",
                    ):
                        for m in res["monsters"]:
                            qty = m.get("quantity", 1)
                            for i in range(1, qty + 1):
                                name = f"{m['name']} {i}" if qty > 1 else m["name"]
                                # Basic initiative roll based on DEX
                                dex_val = m.get("dex", 10)
                                dex_mod = (dex_val - 10) // 2
                                from backend.utils.dice import quick_roll

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
                render_themed_markdown(res)
                st.warning(
                    "⚠️ This encounter is in 'Legacy Format' or failed to generate monster data. Click 'Generate Encounter' again to enable the Initiative Tracker integration."
                )

        if st.session_state.get("riddle_result"):
            st.markdown("---")
            with st.container(border=True):
                st.markdown("### 🧩 The Oracle's Riddle")
                render_themed_markdown(st.session_state.riddle_result)
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
        if st.session_state.get("npc_result"):
            render_themed_markdown(st.session_state.npc_result)
