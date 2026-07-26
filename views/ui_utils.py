import streamlit as st
import logging

logger = logging.getLogger("DnDAssistant.UIUtils")

# --- CLASS-SPECIFIC COLOR SCHEMES ---
CLASS_COLOR_THEMES = {
    "paladin": {
        "accent": "#F59E0B",
        "bg_subtle": "rgba(245, 158, 11, 0.12)",
        "header_badge": "#78350F",
    },
    "barbarian": {
        "accent": "#EF4444",
        "bg_subtle": "rgba(239, 68, 68, 0.12)",
        "header_badge": "#7F1D1D",
    },
    "bard": {
        "accent": "#EC4899",
        "bg_subtle": "rgba(236, 72, 153, 0.12)",
        "header_badge": "#831843",
    },
    "cleric": {
        "accent": "#67E8F9",
        "bg_subtle": "rgba(103, 232, 249, 0.12)",
        "header_badge": "#164E63",
    },
    "druid": {
        "accent": "#10B981",
        "bg_subtle": "rgba(16, 185, 129, 0.12)",
        "header_badge": "#064E3B",
    },
    "fighter": {
        "accent": "#F97316",
        "bg_subtle": "rgba(249, 115, 22, 0.12)",
        "header_badge": "#7C2D12",
    },
    "monk": {
        "accent": "#3B82F6",
        "bg_subtle": "rgba(59, 130, 246, 0.12)",
        "header_badge": "#1E3A8A",
    },
    "ranger": {
        "accent": "#84CC16",
        "bg_subtle": "rgba(132, 204, 22, 0.12)",
        "header_badge": "#365314",
    },
    "rogue": {
        "accent": "#A855F7",
        "bg_subtle": "rgba(168, 85, 247, 0.12)",
        "header_badge": "#581C87",
    },
    "sorcerer": {
        "accent": "#8B5CF6",
        "bg_subtle": "rgba(139, 92, 246, 0.12)",
        "header_badge": "#4C1D95",
    },
    "warlock": {
        "accent": "#6366F1",
        "bg_subtle": "rgba(99, 102, 241, 0.12)",
        "header_badge": "#312E81",
    },
    "wizard": {
        "accent": "#06B6D4",
        "bg_subtle": "rgba(6, 182, 212, 0.12)",
        "header_badge": "#164E63",
    },
}

DEFAULT_THEME = {
    "accent": "#D97706",
    "bg_subtle": "rgba(217, 119, 6, 0.12)",
    "header_badge": "#78350F",
}


def get_class_theme(char_class: str) -> dict:
    """Returns a color scheme dictionary for the specified D&D class."""
    if not char_class:
        return DEFAULT_THEME
    key = str(char_class).strip().lower()
    return CLASS_COLOR_THEMES.get(key, DEFAULT_THEME)


@st.cache_data(show_spinner=False)
def inject_global_theme():
    """Injects app-wide performance-optimized CSS for glassmorphism, micro buttons, and badges."""
    css = """
    <style>
    /* Compact Roll Buttons for Skills & Saving Throws */
    div[data-testid="stColumn"] div[data-testid="stButton"] button {
        padding: 2px 6px !important;
        min-height: 28px !important;
        height: 28px !important;
        font-size: 0.81rem !important;
        margin-bottom: 2px !important;
        border-radius: 6px !important;
    }

    /* Sleek Ability Score Box */
    .score-box {
        background: rgba(20, 20, 26, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 8px;
        text-align: center;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .score-box:hover {
        border-color: rgba(217, 119, 6, 0.5);
    }
    .score-label {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 1px;
        color: #9CA3AF;
        text-transform: uppercase;
    }
    .score-mod {
        font-size: 1.35rem;
        font-weight: 800;
        color: #F3F4F6;
        margin: 2px 0;
    }
    .score-value {
        font-size: 0.75rem;
        color: #6B7280;
    }

    /* Primary Stat Highlight Glow */
    .score-box-primary {
        border: 1.5px solid #F59E0B !important;
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.25) !important;
        background: rgba(245, 158, 11, 0.08) !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def extract_flat_names(data_source, max_items: int = 4) -> list:
    """
    Type-agnostic safe string extractor for equipment, spells, and features.
    Handles lists of strings, dicts, nested dicts, and empty values without raising KeyErrors.
    """
    if not data_source:
        return []

    items = []
    if isinstance(data_source, dict):
        for key, val in data_source.items():
            if isinstance(val, list):
                for el in val:
                    if isinstance(el, dict):
                        items.append(str(el.get("name") or el.get("item") or el))
                    else:
                        items.append(str(el))
            elif isinstance(val, dict):
                items.append(str(val.get("name") or val.get("item") or key))
            else:
                items.append(str(key if str(val).strip() == "" else f"{key}: {val}"))
    elif isinstance(data_source, list):
        for el in data_source:
            if isinstance(el, dict):
                items.append(str(el.get("name") or el.get("item") or el))
            else:
                items.append(str(el))

    return items[:max_items]
