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

        meta_str = f"<b>Type:</b> {htype}"
        if details:
            meta_str += f" | {' | '.join(details)}"

        story.append(Paragraph(meta_str, meta_style))

        # Description
        desc = item.get("description", "No description provided.")
        # Replace newlines with break tags for reportlab
        desc = desc.replace("\n", "<br/>")
        story.append(Paragraph(desc, body_style))

        story.append(Spacer(1, 0.4 * inch))

    doc.build(story)
    buffer.seek(0)
    return buffer
