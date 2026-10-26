import html
import io
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _esc(val: Any) -> str:
    if val is None:
        return ""
    return html.escape(str(val)).replace("\n", "<br/>")


def _format_properties(props: Any) -> str:
    if not props:
        return "None"
    if isinstance(props, list):
        cleaned = [str(p).strip() for p in props if p is not None and str(p).strip()]
        return _esc(", ".join(cleaned)) if cleaned else "None"
    return _esc(props)


def generate_homebrew_pdf(items: List[Dict[str, Any]]) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.alignment = 1  # Center

    card_title_style = ParagraphStyle(
        "CardTitle", parent=styles["Heading2"], textColor=colors.darkred, spaceAfter=6
    )

    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        textColor=colors.dimgrey,
        spaceAfter=12,
    )

    body_style = styles["BodyText"]

    story = []

    story.append(Paragraph("Campaign Homebrew Items", title_style))
    story.append(Spacer(1, 0.5 * inch))

    for item in items:
        # Title
        story.append(Paragraph(_esc(item.get("name") or "Unknown Item"), card_title_style))

        # Meta info
        raw_type = str(item.get("homebrew_type") or "Item").capitalize()
        htype = _esc(raw_type)
        details = []
        if raw_type == "Weapon":
            details.append(f"Damage: {_esc(item.get('damage_dice') or 'N/A')}")
            details.append(f"Properties: {_format_properties(item.get('properties'))}")
        elif raw_type == "Spell":
            details.append(f"Level: {_esc(item.get('level', 0))}")
            details.append(f"School: {_esc(item.get('school') or 'N/A')}")
        elif raw_type == "Monster":
            details.append(f"CR: {_esc(item.get('cr', '1'))}")
            details.append(f"AC: {_esc(item.get('ac', 10))}")
            details.append(f"HP: {_esc(item.get('hp', 10))}")
            details.append(f"Speed: {_esc(item.get('speed') or '30 ft.')}")

        meta_str = f"<b>Type:</b> {htype}"
        if details:
            meta_str += f" | {' | '.join(details)}"

        story.append(Paragraph(meta_str, meta_style))

        # Description
        desc_parts = []
        if item.get("description"):
            desc_parts.append(_esc(item["description"]))
        elif raw_type != "Monster":
            desc_parts.append("No description provided.")

        if raw_type == "Monster":
            traits = item.get("traits") or []
            if traits:
                desc_parts.append("<b>Traits:</b>")
                for t in traits:
                    if isinstance(t, dict):
                        t_name = _esc(t.get("name") or "Trait")
                        t_desc = _esc(t.get("description") or t.get("desc") or "")
                        desc_parts.append(f"• {t_name}: {t_desc}")
                    else:
                        desc_parts.append(f"• {_esc(t)}")
            actions = item.get("actions") or []
            if actions:
                desc_parts.append("<b>Actions:</b>")
                for a in actions:
                    if isinstance(a, dict):
                        a_name = _esc(a.get("name") or "Action")
                        a_desc = _esc(a.get("description") or a.get("desc") or "")
                        desc_parts.append(f"• {a_name}: {a_desc}")
                    else:
                        desc_parts.append(f"• {_esc(a)}")

        desc = "<br/>".join(desc_parts) if desc_parts else "No description provided."
        story.append(Paragraph(desc, body_style))

        story.append(Spacer(1, 0.4 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer
