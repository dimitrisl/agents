import streamlit as st

# Configure the page
st.set_page_config(
    page_title="D&D AI Assistant",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar Navigation
with st.sidebar:
    st.title("🎲 D&D AI Assistant")
    st.markdown("---")

    # Radio buttons act as our view switcher
    view_mode = st.radio(
        "Select Mode:", ["🗡️ Player Dashboard", "🏰 Dungeon Master View"], index=0
    )

    st.markdown("---")
    if st.button("✨ Generate with AI", use_container_width=True, type="primary"):
        st.toast("AI Generation module is not yet connected!")

# Main Content
if view_mode == "🗡️ Player Dashboard":
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Player Dashboard")
    with col2:
        st.write("👤 **Lv. 5 Paladin**")

    st.markdown("### Active Character: **Eldred the Valiant**")

    # Render Stats
    st.markdown("#### Ability Scores")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("STR", "18", "+4")
    c2.metric("DEX", "12", "+1")
    c3.metric("CON", "15", "+2")
    c4.metric("INT", "10", "+0")
    c5.metric("WIS", "14", "+2")
    c6.metric("CHA", "16", "+3")

    st.markdown("---")
    st.subheader("🤖 AI Build Suggestions")
    st.info(
        "Based on Eldred's personality and stats, consider multiclassing into Sorcerer for defensive buffs like *Shield* and offensive boosts like *Booming Blade*."
    )

else:
    st.title("Dungeon Master Workspace")

    st.markdown("### Active Campaign: **The Sunless Citadel**")
    st.warning(
        "**Session Log:** The Party enters the lower levels. You need to prepare encounters for the Goblin warren."
    )

    st.markdown("---")
    st.subheader("🎲 AI Encounter Generator")
    st.write(
        "Generate a balanced encounter tailored for a party of 4 level-5 characters deep underground."
    )

    if st.button("Generate Random Encounter"):
        st.success(
            "**Generated Encounter:** 1x Cave Troll and 3x Goblin ambushers dropping from the stalactites!"
        )
