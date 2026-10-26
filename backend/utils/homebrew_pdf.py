import io
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


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
        story.append(Paragraph(item.get("name", "Unknown Item"), card_title_style))

        # Meta info
        htype = item.get("homebrew_type", "Item").capitalize()
        details = []
        if htype == "Weapon":
            details.append(f"Damage: {item.get('damage_dice', 'N/A')}")
            details.append(f"Properties: {', '.join(item.get('properties', []))}")
        elif htype == "Spell":
            details.append(f"Level: {item.get('level', 0)}")
            details.append(f"School: {item.get('school', 'N/A')}")
        elif htype == "Monster":
            details.append(f"CR: {item.get('cr', '1')}")
            details.append(f"AC: {item.get('ac', 10)}")
            details.append(f"HP: {item.get('hp', 10)}")
            details.append(f"Speed: {item.get('speed', '30 ft.')}")

        meta_str = f"<b>Type:</b> {htype}"
        if details:
            meta_str += f" | {' | '.join(details)}"

        story.append(Paragraph(meta_str, meta_style))

        # Description
        desc_parts = []
        if item.get("description"):
            desc_parts.append(item["description"])
        elif htype != "Monster":
            desc_parts.append("No description provided.")

        if htype == "Monster":
            traits = item.get("traits") or []
            if traits:
                desc_parts.append("<b>Traits:</b>")
                for t in traits:
                    desc_parts.append(
                        f"• {t.get('name')}: {t.get('description')}"
                        if isinstance(t, dict)
                        else f"• {t}"
                    )
            actions = item.get("actions") or []
            if actions:
                desc_parts.append("<b>Actions:</b>")
                for a in actions:
                    desc_parts.append(
                        f"• {a.get('name')}: {a.get('description')}"
                        if isinstance(a, dict)
                        else f"• {a}"
                    )

        desc = "<br/>".join(desc_parts) if desc_parts else "No description provided."
        story.append(Paragraph(desc, body_style))

        story.append(Spacer(1, 0.4 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer
