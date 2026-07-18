import streamlit as st


@st.dialog("NPC Stat Block", width="large")
def show_npc_stat_block(npc: dict):
    """Shows a detailed stat block for an NPC."""
    st.markdown(f"### {npc.get('name', 'Unknown NPC')}")
    st.markdown(
        f"*{npc.get('race', 'Unknown Race')} {npc.get('class', 'Commoner')} - {npc.get('alignment', 'Neutral')}*"
    )

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Armor Class:** {npc.get('ac', 10)}")
        st.markdown(f"**Hit Points:** {npc.get('hp', 4)}")
        st.markdown(f"**Speed:** {npc.get('speed', '30 ft.')}")
    with col2:
        st.markdown("**Core Stats:**")
        stats = npc.get("stats", {})
        if stats:
            stat_str = " | ".join([f"{k}: {v}" for k, v in stats.items()])
            st.markdown(f"`{stat_str}`")
        else:
            st.markdown("`Standard Array`")

    st.divider()

    st.markdown("**Traits & Features:**")
    for trait in npc.get("traits", []):
        st.markdown(f"- **{trait.get('name', '')}**: {trait.get('description', '')}")

    st.markdown("**Actions:**")
    for action in npc.get("actions", []):
        st.markdown(f"- **{action.get('name', '')}**: {action.get('description', '')}")

    if npc.get("notes"):
        st.divider()
        st.markdown("**DM Notes:**")
        st.info(npc.get("notes"))
