import streamlit as st
from backend.core.config_loader import load_config, save_config


def render_settings_view():
    st.title("⚙️ Application Settings")
    st.write("Manage your AI models, API configurations, and app preferences.")

    config = load_config()
    ai_settings = config.get("ai_settings", {})
    app_settings = config.get("app_settings", {})

    # AI Configuration Section
    st.subheader("🤖 AI Engine Configuration")
    col1, col2 = st.columns(2)

    available_models = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.1-flash-preview",
        "gemini-3.1-pro-preview",
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]

    # Helper to find current index in selectbox
    def get_index(model_list, current):
        try:
            return model_list.index(current.replace("models/", ""))
        except Exception:
            # Fallback to flash-latest if not found
            return model_list.index("gemini-flash-latest")

    with col1:
        preferred_model = st.selectbox(
            "Preferred AI Model",
            options=available_models,
            index=get_index(
                available_models, ai_settings.get("preferred_model", "gemini-1.5-flash")
            ),
            help="The primary model for complex tasks like PDF parsing and backstory generation.",
        )

        temperature = st.slider(
            "Creativity (Temperature)",
            min_value=0.0,
            max_value=1.5,
            value=float(ai_settings.get("temperature", 0.7)),
            step=0.1,
            help="Lower is more precise, higher is more creative.",
        )

    with col2:
        fallback_model = st.selectbox(
            "Fallback AI Model",
            options=available_models,
            index=get_index(
                available_models, ai_settings.get("fallback_model", "gemini-1.5-flash")
            ),
            help="Used if the preferred model is unavailable or encounters errors.",
        )

    st.markdown("---")

    # App Settings Section
    st.subheader("📂 Application Paths & Debug")
    col3, col4 = st.columns(2)

    with col3:
        portrait_dir = st.text_input(
            "Portrait Directory",
            value=app_settings.get("portrait_dir", "data/portraits"),
            help="Where character images are saved locally.",
        )

    with col4:
        debug_mode = st.toggle(
            "Enable Debug Mode",
            value=app_settings.get("debug_mode", False),
            help="Shows technical logs and extended error messages in the UI.",
        )

    st.markdown("---")

    # Action Buttons
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("💾 Save Settings", type="primary", use_container_width=True):
        new_config = {
            "ai_settings": {
                "preferred_model": preferred_model,
                "fallback_model": fallback_model,
                "temperature": temperature,
            },
            "app_settings": {"debug_mode": debug_mode, "portrait_dir": portrait_dir},
        }
        save_config(new_config)
        st.success(
            "Settings saved successfully! Changes will take effect on next AI call."
        )
        st.toast("Configuration updated.")

    if c2.button("🔄 Reset to Defaults", use_container_width=True):
        if st.confirm("Are you sure you want to reset all settings to defaults?"):
            # We don't have a direct delete, but we can save the DEFAULT_CONFIG
            # from config_loader if we expose it. For now, let's just clear.
            from backend.core.config_loader import DEFAULT_CONFIG

            save_config(DEFAULT_CONFIG)
            st.rerun()

    # Raw Config View
    with st.expander("🔍 View Raw config.json"):
        st.json(config)
