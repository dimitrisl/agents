import streamlit as st
import logging

from backend.core.storage import (
    save_character,
)
from backend.core.state_manager import (
    get_character_dict,
    update_session_from_dict,
)
from backend.services.mechanics_service import (
    get_modifier as calculate_modifier,
)
from backend.utils.pdf_exporter import export_character_to_pdf


logger = logging.getLogger(__name__)


def safe_int(val, default=0):
    try:
        if val is None:
            return default
        import math

        if isinstance(val, float) and math.isnan(val):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def log_roll(message: str):
    """Helper to log rolls to the session state history."""
    if "roll_history" not in st.session_state:
        st.session_state.roll_history = []
    st.session_state.roll_history.insert(0, message)
    if len(st.session_state.roll_history) > 20:
        st.session_state.roll_history = st.session_state.roll_history[:20]
    st.toast(message)


@st.cache_data
def get_item_effect(name: str) -> str:
    """Detects what a specific item does for the UI display using the KB."""
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _rules_repo.get_all_items()

    n = name.lower()
    item_data = next((i for i in all_items if i["name"].lower() == n), None)

    if not item_data:
        return "-"

    effects = []
    if "ac_base" in item_data:
        limit = item_data.get("dex_limit", 10)
        dex_str = f" + DEX (max {limit})" if limit < 10 else " + DEX"
        if limit == 0:
            dex_str = " (No DEX)"
        effects.append(f"Base AC {item_data['ac_base']}{dex_str}")
    if "ac_bonus" in item_data:
        effects.append(f"+{item_data['ac_bonus']} AC")
    if "stat_set" in item_data:
        for s, v in item_data["stat_set"].items():
            effects.append(f"{s} becomes {v}")
    if "stat_bonus" in item_data:
        for s, v in item_data["stat_bonus"].items():
            effects.append(f"+{v} {s}")

    return ", ".join(effects) if effects else "-"


@st.dialog("📥 Character Sheet PDF Export")
def show_pdf_export_preview(char_dict: dict):
    """Displays a preview of the character data before exporting to PDF."""
    st.markdown("### 🧬 Phyrexian bio-mechanical template ready for export.")
    st.write("Review the compiled metrics before committing to the PDF.")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(f"**Name:** `{char_dict.get('char_name', 'Unnamed')}`")
        st.markdown(
            f"**Class:** `{char_dict.get('char_class', 'Unknown')} {char_dict.get('char_level', 1)}`"
        )
        if char_dict.get("subclass"):
            st.markdown(f"**Subclass:** `{char_dict['subclass']}`")
        st.markdown(f"**Species/Race:** `{char_dict.get('race', 'Unknown')}`")
        st.markdown(f"**Background:** `{char_dict.get('background', 'Unknown')}`")
        st.markdown(f"**Alignment:** `{char_dict.get('alignment', 'Neutral')}`")
        st.markdown(f"**Ruleset:** `{char_dict.get('dnd_edition', '2014 Edition')}`")
    with col2:
        portrait_url = char_dict.get("char_portrait")
        if portrait_url:
            display_portrait = portrait_url
            if not portrait_url.startswith("http") and not portrait_url.startswith(
                "data:"
            ):
                from backend.utils.ui_utils import get_image_base64

                b64 = get_image_base64(portrait_url)
                if b64:
                    display_portrait = b64
            st.image(display_portrait, use_container_width=True)
        else:
            st.info("No portrait loaded.")

    st.markdown("#### 📊 Core Vitals & Abilities")
    # Vitals columns
    v_col1, v_col2, v_col3 = st.columns(3)
    v_col1.metric("HP Max", char_dict.get("hp_max", 10))
    v_col2.metric("Armor Class", char_dict.get("armor_class", 10))
    v_col3.metric("Speed", f"{char_dict.get('speed', 30)} ft")

    # Abilities layout
    stats = char_dict.get("stats", {})
    cols = st.columns(6)
    for idx, stat_name in enumerate(["STR", "DEX", "CON", "INT", "WIS", "CHA"]):
        val = stats.get(stat_name, 10)
        mod = calculate_modifier(val)
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        with cols[idx]:
            st.markdown(
                f"""
                <div style='text-align: center; border: 1px solid #444; border-radius: 8px; padding: 8px; background-color: rgba(255,255,255,0.05);'>
                    <div style='font-size: 0.8rem; font-weight: bold; color: var(--primary-color); text-transform: uppercase;'>{stat_name}</div>
                    <div style='font-size: 1.5rem; font-weight: 800; margin: 4px 0;'>{val}</div>
                    <div style='font-size: 0.9rem; color: #888;'>({mod_str})</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    # Saving Throws & Skills
    saves_list = char_dict.get("saving_throws", [])
    skills_list = char_dict.get("skill_proficiencies", [])

    col_s, col_sk = st.columns(2)
    with col_s:
        st.markdown("**Saving Throws:**")
        if saves_list:
            st.write(", ".join(saves_list))
        else:
            st.caption("No saving throw proficiencies.")
    with col_sk:
        st.markdown("**Skill Proficiencies:**")
        if skills_list:
            st.write(", ".join(skills_list))
        else:
            st.caption("No skill proficiencies.")

    st.markdown("---")
    # Quick Inventory & Weapon summary
    w_col, e_col = st.columns(2)
    with w_col:
        weapons = char_dict.get("weapons", [])
        st.markdown(f"**⚔️ Weapons ({len(weapons)}):**")
        if weapons:
            for w in weapons[:3]:
                st.write(
                    f"- {w.get('name')} ({w.get('damage_dice')} {w.get('attack_bonus')})"
                )
            if len(weapons) > 3:
                st.write(f"*...and {len(weapons) - 3} more*")
        else:
            st.caption("No weapons equipped.")

    with e_col:
        features = char_dict.get("features_traits", [])
        st.markdown(f"**🛡️ Features & Traits ({len(features)}):**")
        if features:
            for f in features[:3]:
                st.write(f"- {f.get('name')}")
            if len(features) > 3:
                st.write(f"*...and {len(features) - 3} more*")
        else:
            st.caption("No features listed.")

    # Spells summary
    spells = char_dict.get("spells", {})
    total_spells = (
        sum(len(s_list) for s_list in spells.values())
        if isinstance(spells, dict)
        else 0
    )
    if total_spells > 0:
        st.markdown(f"**🧙 Spellcasting:** `{total_spells}` spells known / prepared.")

    st.markdown("---")
    st.info(
        "⚠️ **Note:** Make sure all adjustments are complete. Once downloaded, form fields can still be edited manually within any PDF viewer."
    )

    # PDF Bytes preparation and Download button
    template_path = "5E_CharacterSheet_Fillable.pdf"
    with st.spinner("Compiling PDF sheet..."):
        pdf_bytes = export_character_to_pdf(char_dict, template_path)

    if pdf_bytes:
        st.download_button(
            label="📥 Confirm & Download PDF",
            data=pdf_bytes,
            file_name=f"{char_dict['char_name']}_Sheet.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            key="confirm_download_pdf_btn",
        )
    else:
        st.error("Failed to generate character sheet PDF.")


def trigger_sync():
    """Forces a synchronization of derived stats using the backend service."""
    from backend.services.forge_service import process_character_update

    # 1. Collect Stat Updates & Level
    stat_updates = {}
    for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        temp_key = f"stat_val_{k}"
        if temp_key in st.session_state:
            stat_updates[k] = st.session_state[temp_key]

    # Explicitly catch the level from the widget key
    if "char_level" in st.session_state:
        stat_updates["char_level"] = st.session_state.char_level

    # 2. Collect Equipment Deltas
    equipment_deltas = st.session_state.get("edit_equip_table", {})
    weapon_deltas = st.session_state.get("edit_weapons", {})

    # 3. Call Backend Service
    current_char = get_character_dict(st.session_state)

    # Safety Check: Don't sync if basic info is missing (prevents accidental resets)
    if not current_char.get("char_name") or current_char.get("char_name") == "New Hero":
        # Check if we have it in session state keys directly as a fallback
        alt_name = st.session_state.get("char_name")
        if alt_name and alt_name != "New Hero":
            current_char["char_name"] = alt_name
        else:
            st.error(
                "⚠️ Cannot sync: Character name is missing. Please ensure your character is loaded correctly."
            )
            return

    updated = process_character_update(
        current_char, stat_updates, equipment_deltas, weapon_deltas
    )

    # 4. Update UI State
    update_session_from_dict(st.session_state, updated)

    # Invalidate editor dataframes to force recreation
    if "equip_df_editor" in st.session_state:
        del st.session_state["equip_df_editor"]
    if "weapons_df_editor" in st.session_state:
        del st.session_state["weapons_df_editor"]

    # Update widget temp keys from the fresh data
    for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        try:
            st.session_state[f"stat_val_{k}"] = st.session_state.stats[k]
        except Exception:
            logger.error(f"Could not set session state for stat {k}")

    # Save to database immediately to prevent data loss on subsequent UI interactions
    save_character(get_character_dict(st.session_state))

    # 5. CLEAR the editor state
    if "edit_equip_table" in st.session_state:
        del st.session_state["edit_equip_table"]
    if "edit_weapons" in st.session_state:
        del st.session_state["edit_weapons"]
