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
):
    """Renders a visually striking header for the character sheet."""
    st.markdown(
        f"""
        <div class="character-header" style="border-left: 10px solid {accent_color}; padding-left: 20px; margin-bottom: 25px;">
            <div style="display: flex; align-items: center; gap: 25px;">
                {f'<div class="portrait-container"><img src="{portrait_url}" class="portrait-img"></div>' if portrait_url else ""}
                <div>
                    <h1 style="margin: 0; padding: 0; font-size: 2.5rem; color: white !important;">{name}</h1>
                    <p style="margin: 5px 0 0 0; font-size: 1.2rem; opacity: 0.9; color: white;">
                        Level {level} {race} {char_class} • {background} • {alignment}
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
