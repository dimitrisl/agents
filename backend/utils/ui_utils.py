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

            /* Dice Roll CSS Animations & Styling */
            @keyframes dice-roll {{
                0% {{ transform: scale(0.3) rotate(0deg); filter: blur(4px); }}
                15% {{ transform: scale(1.1) rotate(180deg); }}
                30% {{ transform: scale(0.9) rotate(360deg); }}
                45% {{ transform: scale(1.15) rotate(540deg) translate(5px, -5px); }}
                60% {{ transform: scale(0.95) rotate(720deg) translate(-5px, 5px); }}
                75% {{ transform: scale(1.05) rotate(900deg) translate(2px, 2px); }}
                90% {{ transform: scale(0.98) rotate(1000deg); }}
                100% {{ transform: scale(1) rotate(1080deg); }}
            }}

            @keyframes text-glow {{
                0% {{ text-shadow: 0 0 2px rgba(212, 175, 55, 0.3); }}
                50% {{ text-shadow: 0 0 10px rgba(212, 175, 55, 0.8), 0 0 20px rgba(212, 175, 55, 0.5); }}
                100% {{ text-shadow: 0 0 2px rgba(212, 175, 55, 0.3); }}
            }}

            @keyframes fade-in {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}

            .dice-card {{
                background: linear-gradient(135deg, rgba(20, 10, 10, 0.95) 0%, rgba(10, 5, 5, 0.98) 100%);
                border: 2px solid var(--primary-color);
                border-radius: 16px;
                padding: 20px;
                margin: 15px 0;
                text-align: center;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
                animation: fade-in 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                position: relative;
                overflow: hidden;
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
                animation: dice-roll 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
                transform-origin: center;
            }}

            .dice-svg polygon, .dice-svg rect, .dice-svg line {{
                stroke: var(--primary-color) !important;
            }}

            .dice-text {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-family: 'Outfit', 'Inter', sans-serif;
                font-size: 2.2rem;
                font-weight: 900;
                color: var(--accent-color);
                animation: text-glow 2s infinite alternate, fade-in 0.3s ease-out 0.9s both;
                pointer-events: none;
            }}

            .dice-label-text {{
                font-size: 1.1rem;
                font-weight: 700;
                color: #fff;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                margin-bottom: 5px;
            }}

            .dice-subtext {{
                font-size: 0.9rem;
                color: #888;
                margin-top: 10px;
            }}

            .dice-total-display {{
                font-size: 2.5rem;
                font-weight: 800;
                color: var(--primary-color);
                margin: 5px 0;
                animation: fade-in 0.3s ease-out 1.1s both;
            }}

            /* Themed Markdown Block - Bio-mechanical style */
            .themed-markdown-block {{
                display: none;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"] {{
                background: linear-gradient(135deg, rgba(20, 10, 10, 0.45) 0%, rgba(10, 5, 5, 0.7) 100%) !important;
                border: 1px solid rgba(255, 75, 75, 0.15) !important;
                border-left: 5px solid var(--primary-color) !important;
                border-radius: 12px !important;
                padding: 20px 24px !important;
                margin: 15px 0 !important;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5) !important;
                transition: all 0.3s cubic-bezier(0.165, 0.84, 0.44, 1) !important;
            }}

            div.element-container:has(div.themed-markdown-block) + div.element-container [data-testid="stMarkdownContainer"]:hover {{
                border-color: rgba(255, 75, 75, 0.3) !important;
                box-shadow: 0 12px 40px rgba(255, 75, 75, 0.15) !important;
                transform: translateY(-2px);
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
    """Renders the visually animated dice roll from session state if available."""
    if "active_roll" not in st.session_state or st.session_state.active_roll is None:
        return

    roll = st.session_state.active_roll
    label = roll.get("label", "Dice Roll")
    sides = roll.get("sides", 20)
    raw = roll.get("raw", 1)  # Can be int or list (for advantage/disadvantage)
    modifier = roll.get("modifier", 0)
    total = roll.get("total", 1)
    adv_type = roll.get("adv_type", "None")

    # Generate the SVG based on dice type
    svg_content = ""
    if sides == 4:
        svg_content = """
        <polygon points="50,10 90,85 10,85" fill="#1a0a0a" stroke="#ff4b4b" stroke-width="4"/>
        <line x1="50" y1="10" x2="50" y2="85" stroke="#ff4b4b" stroke-width="1.5" stroke-dasharray="2,2"/>
        """
    elif sides == 6:
        svg_content = """
        <rect x="15" y="15" width="70" height="70" rx="10" ry="10" fill="#1a0a0a" stroke="#ff4b4b" stroke-width="4"/>
        <line x1="15" y1="15" x2="85" y2="85" stroke="#ff4b4b" stroke-width="1" opacity="0.3"/>
        """
    elif sides == 8:
        svg_content = """
        <polygon points="50,5 90,50 50,95 10,50" fill="#1a0a0a" stroke="#ff4b4b" stroke-width="4"/>
        <line x1="10" y1="50" x2="90" y2="50" stroke="#ff4b4b" stroke-width="2"/>
        <line x1="50" y1="5" x2="50" y2="95" stroke="#ff4b4b" stroke-width="1.5" stroke-dasharray="2,2"/>
        """
    elif sides == 10:
        svg_content = """
        <polygon points="50,5 85,40 50,95 15,40" fill="#1a0a0a" stroke="#ff4b4b" stroke-width="4"/>
        <line x1="15" y1="40" x2="85" y2="40" stroke="#ff4b4b" stroke-width="2"/>
        <line x1="50" y1="5" x2="50" y2="95" stroke="#ff4b4b" stroke-width="1.5" stroke-dasharray="2,2"/>
        """
    elif sides == 12:
        svg_content = """
        <polygon points="50,5 88,33 73,78 27,78 12,33" fill="#1a0a0a" stroke="#ff4b4b" stroke-width="4"/>
        <line x1="50" y1="5" x2="50" y2="40" stroke="#ff4b4b" stroke-width="1.5"/>
        <line x1="88" y1="33" x2="60" y2="50" stroke="#ff4b4b" stroke-width="1.5"/>
        <line x1="73" y1="78" x2="55" y2="70" stroke="#ff4b4b" stroke-width="1.5"/>
        <line x1="27" y1="78" x2="45" y2="70" stroke="#ff4b4b" stroke-width="1.5"/>
        <line x1="12" y1="33" x2="40" y2="50" stroke="#ff4b4b" stroke-width="1.5"/>
        """
    else:  # D20 and fallback
        svg_content = """
        <polygon points="50,15 85,75 15,75" fill="#1a0a0a" stroke="#ff4b4b" stroke-width="3"/>
        <polygon points="50,15 15,75 5,35" fill="#120505" stroke="#ff4b4b" stroke-dasharray="2,2" stroke-width="1.5"/>
        <polygon points="50,15 85,75 95,35" fill="#120505" stroke="#ff4b4b" stroke-dasharray="2,2" stroke-width="1.5"/>
        <polygon points="15,75 85,75 50,95" fill="#120505" stroke="#ff4b4b" stroke-dasharray="2,2" stroke-width="1.5"/>
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
