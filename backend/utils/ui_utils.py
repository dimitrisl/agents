import streamlit as st
import os
import base64


def get_image_base64(path):
    """Helper to convert a local image path to a base64 string for HTML embedding."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            ext = os.path.splitext(path)[1].lower().replace(".", "")
            return f"data:image/{ext};base64,{encoded_string}"
    except Exception:
        return None


def inject_custom_css(primary_color: str, accent_color: str):
    """Injects custom CSS for a modern, high-contrast D&D skin."""
    st.markdown(
        f"""
        <style>
            :root {{
                --primary-color: {primary_color};
                --accent-color: {accent_color};
            }}

            /* Reset to clean modern fonts */
            .stApp {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            }}

            /* High Contrast Headers */
            h1, h2, h3, h4 {{
                color: var(--primary-color) !important;
                font-weight: 700 !important;
            }}

            /* Clean Score Boxes - Dark Mode Compatible */
            .score-box {{
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
                background-color: rgba(255,255,255,0.05); /* Subtle dark background */
                margin-bottom: 10px;
            }}
            .character-header {{
                background: rgba(255, 255, 255, 0.05);
                padding: 2rem;
                border-radius: 15px;
                margin-bottom: 2rem;
            }}
            .portrait-container {{
                width: 120px;
                height: 120px;
                border-radius: 15px;
                overflow: hidden;
                border: 3px solid rgba(255, 255, 255, 0.2);
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }}
            .portrait-img {{
                width: 100%;
                height: 100%;
                object-fit: cover;
            }}
            .score-label {{
                font-size: 0.8rem;
                font-weight: bold;
                color: var(--primary-color);
                text-transform: uppercase;
            }}
            .score-mod {{
                font-size: 2.2rem;
                font-weight: 800;
                margin: 2px 0;
            }}
            .score-value {{
                font-size: 1rem;
                background-color: var(--primary-color);
                color: white !important;
                border-radius: 12px;
                width: 40px;
                margin: 0 auto;
                padding: 2px 0;
                font-weight: bold;
            }}

            /* Simple Clear Tabs */
            .stTabs [data-baseweb="tab"] {{
                font-weight: 600;
            }}
            .stTabs [aria-selected="true"] {{
                color: var(--primary-color) !important;
                border-bottom: 3px solid var(--primary-color) !important;
            }}

            /* Banner - Clean Text only */
            .char-banner {{
                border-left: 5px solid var(--primary-color);
                padding-left: 15px;
                margin-bottom: 25px;
            }}

            /* Sidebar Radio Buttons as Segmented Control (Pills) */
            [data-testid="stSidebar"] .stRadio > div[role="radiogroup"] {{
                flex-direction: column !important;
                gap: 10px;
                padding: 5px 0;
            }}
            [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {{
                background-color: rgba(255, 255, 255, 0.03) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                border-radius: 10px !important;
                padding: 10px 14px !important;
                cursor: pointer;
                transition: all 0.2s ease;
                width: 100% !important;
                margin: 0 !important;
            }}
            [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {{
                font-weight: 600 !important;
                font-size: 0.95rem !important;
                margin: 0 !important;
            }}
            [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] > div:first-child {{
                display: none !important; /* Hide standard radio circle */
            }}
            [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:hover {{
                background-color: rgba(255, 255, 255, 0.08) !important;
                border-color: rgba(255, 255, 255, 0.2) !important;
            }}
            /* Target the selected state */
            [data-testid="stSidebar"] .stRadio label:has(input:checked) {{
                background-color: var(--primary-color) !important;
                border-color: var(--primary-color) !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
            }}
            [data-testid="stSidebar"] .stRadio label:has(input:checked) p {{
                color: white !important;
            }}

            /* Force Data Editor checkboxes to be visible (not just on hover) */
            [data-testid="stDataEditor"] [data-testid="stCheckbox"] {{
                opacity: 1 !important;
            }}

            /* Target specific internal elements if needed for different Streamlit versions */
            div[data-testid="stDataEditor"] .dvn-checkbox-container {{
                opacity: 1 !important;
            }}

            /* Phyrexian Roll CSS Animations & Styling */
            @keyframes phyrexian-pulse {{
                0% {{ transform: scale(0.8); filter: drop-shadow(0 0 5px var(--primary-color)); opacity: 0.7; }}
                50% {{ transform: scale(1.1); filter: drop-shadow(0 0 20px var(--primary-color)); opacity: 1; }}
                100% {{ transform: scale(1); filter: drop-shadow(0 0 10px var(--primary-color)); opacity: 0.9; }}
            }}

            @keyframes oil-drip {{
                0% {{ transform: translateY(-20px); opacity: 0; }}
                100% {{ transform: translateY(0); opacity: 1; }}
            }}

            @keyframes text-glow {{
                0% {{ text-shadow: 0 0 2px rgba(255, 75, 75, 0.3); }}
                50% {{ text-shadow: 0 0 10px rgba(255, 75, 75, 0.8), 0 0 20px rgba(255, 75, 75, 0.5); }}
                100% {{ text-shadow: 0 0 2px rgba(255, 75, 75, 0.3); }}
            }}

            @keyframes fade-in {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}

            .dice-card {{
                background: linear-gradient(135deg, rgba(10, 5, 5, 0.98) 0%, rgba(30, 10, 10, 0.95) 100%);
                border: 2px solid var(--primary-color);
                border-radius: 16px;
                padding: 20px;
                margin: 15px 0;
                text-align: center;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8), inset 0 0 15px rgba(255, 75, 75, 0.1);
                animation: fade-in 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                position: relative;
                overflow: hidden;
            }}

            .dice-card::before {{
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, var(--primary-color), transparent);
                animation: oil-drip 2s infinite;
            }}

            .dice-wrapper {{
                display: inline-block;
                position: relative;
                width: 120px;
                height: 120px;
                margin: 10px auto;
            }}

            .dice-svg {{
                width: 100%;
                height: 100%;
                animation: phyrexian-pulse 1.2s ease-in-out both;
                transform-origin: center;
            }}

            .dice-svg circle, .dice-svg line, .dice-svg path, .dice-svg polygon, .dice-svg rect {{
                stroke: var(--primary-color) !important;
                stroke-width: 6 !important;
                fill: none !important;
            }}

            .dice-text {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-family: 'Outfit', 'Inter', sans-serif;
                font-size: 2.2rem;
                font-weight: 900;
                color: #fff;
                text-shadow: 0 0 10px var(--primary-color);
                animation: text-glow 2s infinite alternate, fade-in 0.3s ease-out 0.6s both;
                pointer-events: none;
            }}

            .dice-label-text {{
                font-size: 1.1rem;
                font-weight: 700;
                color: #ccc;
                text-transform: uppercase;
                letter-spacing: 2px;
                margin-bottom: 5px;
            }}

            .dice-subtext {{
                font-size: 0.9rem;
                color: #666;
                margin-top: 10px;
                font-family: monospace;
            }}

            .dice-total-display {{
                font-size: 2.5rem;
                font-weight: 800;
                color: var(--primary-color);
                margin: 5px 0;
                text-shadow: 0 0 15px rgba(255, 75, 75, 0.4);
                animation: fade-in 0.3s ease-out 0.8s both;
            }}

            /* Themed Markdown Block - Phyrexian Biomechanical style */
            .themed-markdown-block {{
                display: none;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] {{
                background: linear-gradient(135deg, rgba(5, 5, 5, 0.9) 0%, rgba(20, 10, 10, 0.8) 100%) !important;
                border: 1px solid rgba(255, 75, 75, 0.2) !important;
                border-left: 4px solid var(--primary-color) !important;
                border-radius: 4px !important;
                padding: 24px 28px !important;
                margin: 20px 0 !important;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.7), inset 0 0 20px rgba(255, 75, 75, 0.05) !important;
                transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1) !important;
                position: relative !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"]::after {{
                content: "ALL WILL BE ONE";
                position: absolute;
                bottom: 5px;
                right: 15px;
                font-size: 0.6rem;
                color: rgba(255, 75, 75, 0.2);
                letter-spacing: 2px;
                font-weight: bold;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"]:hover {{
                border-color: rgba(255, 75, 75, 0.4) !important;
                box-shadow: 0 15px 50px rgba(255, 75, 75, 0.1) !important;
                transform: scale(1.005);
            }}

            /* Themed markdown children overrides for high contrast and premium feel */
            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] h1,
            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] h2,
            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] h3,
            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] h4 {{
                color: var(--primary-color) !important;
                font-family: 'Outfit', 'Inter', sans-serif !important;
                font-weight: 700 !important;
                margin-top: 1.5rem !important;
                margin-bottom: 0.8rem !important;
                text-shadow: 0 0 10px rgba(255, 75, 75, 0.15) !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] p {{
                line-height: 1.7 !important;
                color: #e0e0e0 !important;
                font-size: 1rem !important;
                margin-bottom: 1rem !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] ul,
            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] ol {{
                padding-left: 1.5rem !important;
                margin-bottom: 1.2rem !important;
                color: #d8d8d8 !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] li {{
                margin-bottom: 0.5rem !important;
                line-height: 1.6 !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] code {{
                background-color: rgba(255, 75, 75, 0.1) !important;
                color: var(--accent-color) !important;
                padding: 3px 6px !important;
                border-radius: 4px !important;
                font-size: 0.9em !important;
                font-family: monospace !important;
                border: 1px solid rgba(255, 75, 75, 0.15) !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] pre {{
                background-color: rgba(10, 5, 5, 0.6) !important;
                border: 1px solid rgba(255, 75, 75, 0.1) !important;
                border-radius: 8px !important;
                padding: 15px !important;
                overflow-x: auto !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] blockquote {{
                border-left: 3px solid var(--primary-color) !important;
                background-color: rgba(255, 75, 75, 0.05) !important;
                padding: 10px 15px !important;
                margin: 1.5rem 0 !important;
                border-radius: 0 8px 8px 0 !important;
                font-style: italic !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_themed_markdown(text: str):
    """Renders markdown inside a styled, bio-mechanical container using CSS selectors."""
    st.markdown('<div class="themed-markdown-block"></div>', unsafe_allow_html=True)
    st.markdown(text)


def render_character_header(
    name: str,
    race: str,
    char_class: str,
    level: int,
    background: str,
    alignment: str,
    accent_color: str,
    portrait_url: str = None,
    subclass: str = None,
):
    """Renders a visually striking header using native Streamlit components."""
    # Convert local path to base64 if it looks like a local path
    display_portrait = portrait_url
    if (
        portrait_url
        and not portrait_url.startswith("http")
        and not portrait_url.startswith("data:")
    ):
        display_portrait = get_image_base64(portrait_url)

    with st.container():
        # Add a custom CSS anchor point for the banner style
        st.markdown('<div class="char-banner">', unsafe_allow_html=True)

        col_img, col_text = st.columns([1, 5])

        if display_portrait:
            with col_img:
                st.markdown(
                    f"""
                    <div class="portrait-container">
                        <img src="{display_portrait}" class="portrait-img">
                    </div>
                """,
                    unsafe_allow_html=True,
                )

        with col_text:
            st.markdown(
                f"<h1 style='margin-bottom: 0;'>{name}</h1>", unsafe_allow_html=True
            )
            class_str = f"{char_class} ({subclass})" if subclass else char_class
            st.markdown(f"**Level {level} {race} {class_str}**")
            st.caption(f"{background} • {alignment}")

        st.markdown("</div>", unsafe_allow_html=True)


def render_active_roll_visual():
    """Renders the visually animated Phyrexian pulse from session state if available."""
    if "active_roll" not in st.session_state or st.session_state.active_roll is None:
        return

    roll = st.session_state.active_roll
    label = roll.get("label", "Dice Roll")
    raw = roll.get("raw", 1)  # Can be int or list (for advantage/disadvantage)
    modifier = roll.get("modifier", 0)
    total = roll.get("total", 1)
    adv_type = roll.get("adv_type", "None")

    # Unified Phyrexian Symbol (Φ) for all rolls
    svg_content = """
    <circle cx="50" cy="50" r="40" />
    <line x1="50" y1="10" x2="50" y2="90" />
    """

    # Format the calculation breakdown text
    mod_str = f"+{modifier}" if modifier >= 0 else str(modifier)

    # If list of rolls (advantage/disadvantage, or multi-dice)
    if isinstance(raw, list):
        raw_desc = ", ".join(str(r) for r in raw)
        calc_text = f"Rolls: ({raw_desc}) | Mod: {mod_str}"
        raw_val = roll.get("raw_selected", sum(raw))
    else:
        calc_text = f"Roll: {raw} | Mod: {mod_str}"
        raw_val = raw

    adv_badge = ""
    if adv_type == "Advantage":
        adv_badge = '<span style="background-color: #2e7d32; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-left: 8px;">ADVANTAGE</span>'
    elif adv_type == "Disadvantage":
        adv_badge = '<span style="background-color: #c62828; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; margin-left: 8px;">DISADVANTAGE</span>'

    # Build the full card HTML
    html_card = f"""
    <div class="dice-card">
        <div class="dice-label-text">{label} {adv_badge}</div>

        <div class="dice-wrapper">
            <svg class="dice-svg" viewBox="0 0 100 100">
                {svg_content}
            </svg>
            <div class="dice-text">{raw_val}</div>
        </div>

        <div class="dice-total-display">{total}</div>
        <div class="dice-subtext">{calc_text}</div>
    </div>
    """

    col_space, col_content, col_close = st.columns([1, 10, 1])
    with col_content:
        st.html(html_card)
    with col_close:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("❌", key="dismiss_dice_roll", help="Dismiss roll display"):
            st.session_state.active_roll = None
            st.rerun()
