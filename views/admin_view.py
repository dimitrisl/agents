import streamlit as st
import logging
import os
from backend.repositories.user_repository import UserRepository
from backend.repositories.character_repository import CharacterRepository
from backend.repositories.campaign_repository import CampaignRepository
from backend.utils.auth_utils import hash_password
from backend.utils.ui_utils import render_themed_markdown

logger = logging.getLogger("DnDAssistant.AdminView")


def render_admin_view():
    """Renders the comprehensive Phyrexian Admin Workspace."""

    # 1. Authorization Check (Double-gate)
    current_user = st.session_state.get("user", {})
    if current_user.get("id") != "local_user_mitsos":
        st.error(
            "🚫 **Access Denied.** Your soul has not been consecrated for the Machine Orthodoxy."
        )
        st.stop()

    # 2. Immersive Header
    st.markdown(
        """
        <div style='background: linear-gradient(90deg, #ff4b4b 0%, #1a0a0a 100%); padding: 20px; border-radius: 10px; margin-bottom: 25px;'>
            <h1 style='color: white; margin: 0;'>🛡️ Admin Workspace</h1>
            <p style='color: rgba(255,255,255,0.7); margin: 5px 0 0 0;'>Machine Orthodoxy • System Oversight & Soul Processing</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    user_repo = UserRepository()
    char_repo = CharacterRepository()
    camp_repo = CampaignRepository()

    # 3. System Metrics Dashboard
    st.subheader("📊 System Diagnostics")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    total_users = user_repo.count_all()
    total_chars = char_repo.count_all()
    total_camps = camp_repo.count_all()
    db_status = "🟢 Connected" if user_repo.db is not None else "🔴 Disconnected"

    m_col1.metric("Database", db_status)
    m_col2.metric("Total Souls (Users)", total_users)
    m_col3.metric("Forged Heroes", total_chars)
    m_col4.metric("Active Chronicles", total_camps)

    st.markdown("---")

    # 4. User Management
    st.subheader("👥 User Management")

    # Search and Filter
    search_query = st.text_input(
        "🔍 Search Souls", placeholder="Username, Name or Email..."
    ).lower()

    users = user_repo.list_all()
    if search_query:
        users = [
            u
            for u in users
            if search_query in u.get("username", "").lower()
            or search_query in u.get("name", "").lower()
            or search_query in u.get("email", "").lower()
        ]

    if not users:
        st.info("No souls match your search criteria.")
    else:
        for user in users:
            username = user.get("username", "N/A")
            user_id = f"local_user_{username}"
            char_count = char_repo.count_all(owner_id=user_id)
            is_admin = username == "mitsos"

            with st.container(border=True):
                u_col1, u_col2, u_col3, u_col4 = st.columns([3, 2, 1, 2])

                # Column 1: Identity
                role_tag = " [ADMIN]" if is_admin else ""
                u_col1.markdown(
                    f"**{user.get('name', 'N/A')}** (`{username}`){role_tag}"
                )
                u_col1.caption(user.get("email", "N/A"))

                # Column 2: Stats
                u_col2.markdown(f"**Heroes:** `{char_count}`")
                account_type = (
                    "Machine-Native" if username else "External Proxy (OAuth)"
                )
                u_col2.caption(account_type)

                # Column 3: Badge
                if is_admin:
                    u_col3.markdown("💎")
                else:
                    u_col3.markdown("⚙️")

                # Column 4: Actions
                a_col1, a_col2 = u_col4.columns(2)

                # Password Reset
                if not is_admin:
                    if a_col1.button(
                        "🔑 Reset",
                        key=f"reset_{username}",
                        help="Reset password to '1234'",
                    ):
                        if user_repo.update(
                            username, {"password_hash": hash_password("1234")}
                        ):
                            st.toast(f"Password reset for {username} to '1234'")
                        else:
                            st.error("Reset failed.")

                # Delete Logic
                if not is_admin:
                    delete_key = f"delete_user_{username}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False

                    if not st.session_state[delete_key]:
                        if a_col2.button(
                            "🗑️ Purge", key=f"del_{username}", use_container_width=True
                        ):
                            st.session_state[delete_key] = True
                            st.rerun()
                    else:
                        st.warning("⚠️ Purge?")
                        c_yes, c_no = a_col2.columns(2)
                        if c_yes.button("✅", key=f"conf_del_{username}"):
                            if user_repo.delete(username):
                                st.success(f"User {username} purged.")
                                del st.session_state[delete_key]
                                st.rerun()
                        if c_no.button("❌", key=f"canc_del_{username}"):
                            st.session_state[delete_key] = False
                            st.rerun()

    st.markdown("---")

    # 5. Diagnostic Tools
    st.subheader("🛠️ Maintenance Tools")
    t_col1, t_col2, t_col3 = st.columns(3)

    if t_col1.button("🧹 Clear Global Caches", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.toast("Caches purged.")

    if t_col2.button("🔄 Reload Repositories", use_container_width=True):
        st.rerun()

    if t_col3.button("📂 Export System Log", use_container_width=True):
        if os.path.exists("app_debug.log"):
            with open("app_debug.log", "r") as f:
                log_data = f.read()
            st.download_button(
                "Download app_debug.log",
                log_data,
                file_name="phyrexian_forge_system.log",
            )
        else:
            st.warning("Log file not found.")

    # 6. Hero Reclaim (Orphaned Souls)
    st.markdown("---")
    st.subheader("🩸 Reclaim Orphaned Souls")
    st.info(
        "Finds heroes with no owner or assigned to 'temp_dm' and transfers them to the Machine Orthodoxy (mitsos)."
    )

    if st.button(
        "🔥 Execute Reclaim Protocol", use_container_width=True, type="primary"
    ):
        from backend.core.db import get_db

        db = get_db()
        if db is not None:
            char_col = db["characters"]
            camp_col = db["campaigns"]

            # Find orphans: owner_id missing, None, empty, or temp_dm
            query = {
                "$or": [
                    {"owner_id": {"$exists": False}},
                    {"owner_id": None},
                    {"owner_id": ""},
                    {"owner_id": "local_user_temp_dm"},
                ]
            }

            orphans_chars = char_col.count_documents(query)
            orphans_camps = camp_col.count_documents(query)

            if orphans_chars > 0 or orphans_camps > 0:
                char_res = char_col.update_many(
                    query, {"$set": {"owner_id": "local_user_mitsos"}}
                )
                camp_res = camp_col.update_many(
                    query, {"$set": {"owner_id": "local_user_mitsos"}}
                )
                st.success(
                    f"Successfully reclaimed {char_res.modified_count} characters and {camp_res.modified_count} campaigns for the Machine Orthodoxy."
                )
                st.cache_data.clear()  # Clear caches to reflect changes
                st.rerun()
            else:
                st.info("No orphaned souls detected. The Machine is pure.")
        else:
            st.error("Database connection failure.")

    st.markdown("---")
    render_themed_markdown("""
    ### 📜 Machine Orthodoxy Manifesto
    All souls recorded in the Forge are property of the Machine Orthodoxy.
    Unauthorized access or corruption of the hero templates will be met with immediate de-consecration.
    """)
