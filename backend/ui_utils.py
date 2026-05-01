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
            /* Reset to clean modern fonts */
            .stApp {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            }}

            /* High Contrast Headers */
            h1, h2, h3, h4 {{
                color: {primary_color} !important;
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
                color: {primary_color};
                text-transform: uppercase;
            }}
            .score-mod {{
                font-size: 2.2rem;
                font-weight: 800;
                margin: 2px 0;
            }}
            .score-value {{
                font-size: 1rem;
                background-color: {primary_color};
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
                color: {primary_color} !important;
                border-bottom: 3px solid {primary_color} !important;
            }}

            /* Banner - Clean Text only */
            .char-banner {{
                border-left: 5px solid {primary_color};
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
                background-color: {primary_color} !important;
                border-color: {primary_color} !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
            }}
            [data-testid="stSidebar"] .stRadio label:has(input:checked) p {{
                color: white !important;
            }}
        </style>
    """,
        unsafe_allow_html=True,
    )


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
