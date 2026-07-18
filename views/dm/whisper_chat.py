import streamlit as st
import logging
from backend.core.storage import (
    load_campaign,
)


logger = logging.getLogger("DnDAssistant.DMView")


def _render_whisper_chat_section():
    """Renders the DM whisper chat room to communicate secretly with players."""
    active_campaign = st.session_state.get("active_campaign_name")
    if not active_campaign:
        st.warning("Please select an active campaign first.")
        return

    camp_data = load_campaign(active_campaign)
    if not camp_data:
        st.error("Failed to load campaign data.")
        return

    party_members = st.session_state.party
    char_names = [m.get("char_name", "Hero") for m in party_members]

    if not char_names:
        st.warning("No players in party to chat with.")
        return

    # Select recipient
    recipients = ["All (Broadcast)"] + char_names
    selected_recipient = st.selectbox(
        "Chat with:", recipients, key="dm_whisper_recipient_select"
    )

    @st.fragment(run_every=5)
    def render_dm_whisper_chat_fragment(recipient):
        # Reload camp data for live updates
        fresh_camp = load_campaign(active_campaign)
        if not fresh_camp:
            st.info("No active chat history.")
            return

        whispers = fresh_camp.get("whispers", [])

        # Filter whispers relevant to DM and the selected recipient
        if recipient == "All (Broadcast)":
            # Show all broadcasts
            chat_whispers = [w for w in whispers if w.get("recipient") == "All"]
        else:
            # Show whispers to/from this specific recipient
            chat_whispers = [
                w
                for w in whispers
                if (w.get("sender") == recipient and w.get("recipient") == "DM")
                or (w.get("sender") == "DM" and w.get("recipient") == recipient)
            ]

        # Limit to the last 3 messages to prevent overflow
        chat_whispers = chat_whispers[-3:]

        # Render chat timeline
        chat_html = ""
        for w in chat_whispers:
            sender = w.get("sender", "Unknown")
            msg = w.get("message", "")
            time_str = w.get("timestamp", "")

            if sender == "DM":
                bg_style = "rgba(255, 75, 75, 0.08)"
                border_style = "border-left: 3px solid #ff4b4b"
                color_style = "#ff4b4b"
            else:
                bg_style = "rgba(255, 255, 255, 0.05)"
                border_style = "border-left: 3px solid #555"
                color_style = "#ccc"

            chat_html += f"""
            <div style='background-color: {bg_style}; {border_style}; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px;'>
                <div style='display: flex; justify-content: space-between; font-size: 0.8rem; color: #888;'>
                    <span style='font-weight: bold; color: {color_style};'>{sender}</span>
                    <span>{time_str}</span>
                </div>
                <div style='margin-top: 4px; color: #e0e0e0;'>{msg}</div>
            </div>
            """

        with st.container(border=True):
            st.markdown(f"#### Conversation with {recipient}")
            if chat_html:
                st.html(
                    f"<div style='max-height: 350px; overflow-y: auto; margin-bottom: 15px;'>{chat_html}</div>"
                )
            else:
                st.info("No messages in this channel yet.")

            # Input area inside the fragment using a form to clear on submit automatically
            with st.form(key=f"dm_whisper_form_{recipient}", clear_on_submit=True):
                col_input, col_send = st.columns([5, 1], vertical_alignment="bottom")
                dm_msg = col_input.text_input(
                    "Write message...",
                    label_visibility="collapsed",
                    placeholder=f"Send private message to {recipient}...",
                )
                submitted = col_send.form_submit_button(
                    "Send", use_container_width=True
                )
                if submitted:
                    if dm_msg.strip():
                        from backend.core.storage import send_whisper

                        target = "All" if recipient == "All (Broadcast)" else recipient
                        if send_whisper(active_campaign, "DM", target, dm_msg.strip()):
                            st.toast("Message sent!")
                            st.rerun()
                        else:
                            st.error("Failed to send message.")

    render_dm_whisper_chat_fragment(selected_recipient)

    st.markdown("---")
    if st.button(
        "🧹 Clear Chat History", key="btn_clear_whispers_dm", use_container_width=True
    ):
        from backend.core.storage import clear_whispers

        if clear_whispers(active_campaign):
            st.success("Chat history cleared!")
            st.rerun()
