import streamlit as st


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
):
    """Renders the stylized character banner header."""
    st.markdown(
        f"""
        <div class="char-banner">
            <h1 style="color: white !important; margin: 0; padding: 0;">{name}</h1>
            <div style="color: {accent_color}; font-size: 1.2rem; font-weight: bold;">
                {race} {char_class} | Level {level}
            </div>
            <div style="color: white; opacity: 0.8; font-size: 0.9rem;">
                {background} | {alignment}
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )
