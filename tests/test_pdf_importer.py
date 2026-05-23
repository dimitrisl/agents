import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO

from backend.utils.pdf_importer import extract_text_and_fields_from_pdf
from backend.services.rules_service import parse_character_from_text


def test_extract_text_and_fields_from_pdf():
    # Create a mock PDF file object
    mock_pdf_file = BytesIO(b"dummy PDF data")

    # Mock pypdf and pdfplumber
    with (
        patch("pypdf.PdfReader") as MockPdfReader,
        patch("pdfplumber.open") as mock_pdfplumber_open,
    ):
        # Setup pypdf mocks
        mock_reader_instance = MagicMock()
        MockPdfReader.return_value = mock_reader_instance
        mock_reader_instance.get_fields.return_value = {
            "CharacterName": {"/V": "Willow Whisperwind"},
            "ClassLevel": {"/V": "Ranger 3"},
        }

        # Setup manual widget scan mocks
        mock_page = MagicMock()
        mock_annot = MagicMock()
        mock_annot_obj = MagicMock()
        mock_annot_obj.get.side_effect = lambda key: {
            "/Subtype": "/Widget",
            "/T": "XP",
            "/V": "2000",
        }.get(key)
        mock_annot.get_object.return_value = mock_annot_obj
        mock_page.get.return_value = [mock_annot]
        mock_reader_instance.pages = [mock_page]

        # Setup pdfplumber mocks
        mock_pdf_instance = MagicMock()
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf_instance

        mock_plumber_page = MagicMock()
        mock_plumber_page.extract_text.return_value = (
            "Willow Whisperwind\nLevel 3 Ranger"
        )
        mock_plumber_page.extract_tables.return_value = [
            [["Weapon", "Atk", "Dmg"], ["Shortbow", "+5", "1d6+3"]]
        ]
        mock_pdf_instance.pages = [mock_plumber_page]

        # Execute
        result = extract_text_and_fields_from_pdf(mock_pdf_file)

        # Assertions
        assert "CharacterName: Willow Whisperwind" in result
        assert "XP: 2000" in result
        assert "Willow Whisperwind" in result
        assert "Weapon | Atk | Dmg" in result
        assert "Shortbow | +5 | 1d6+3" in result


def test_parse_character_from_text():
    sheet_text = "Name: Willow Whisperwind, Class: Ranger, Level: 3"

    with patch(
        "backend.services.rules_service.generate_ai_json"
    ) as mock_generate_ai_json:
        # Mock step 1 and step 2 AI calls
        mock_generate_ai_json.side_effect = [
            # Step 1 core identity response
            {
                "char_name": "Willow Whisperwind",
                "char_class": "Ranger",
                "char_level": 3,
                "race": "Elf",
                "background": "Outlander",
                "stats": {
                    "STR": 10,
                    "DEX": 16,
                    "CON": 14,
                    "INT": 12,
                    "WIS": 14,
                    "CHA": 8,
                },
            },
            # Step 2 combat, equipment & spells response
            {
                "hp_max": 28,
                "armor_class": 15,
                "speed": 30,
                "proficiency_bonus": 2,
                "weapons": [
                    {"name": "Shortbow", "attack_bonus": "+5", "damage": "1d6+3"}
                ],
                "equipment": [{"name": "Leather armor", "equipped": True}],
                "spells": {
                    "cantrips": [],
                    "level_1": ["Goodberry", "Hunter's Mark"],
                },
            },
        ]

        # Execute
        parsed = parse_character_from_text(sheet_text)

        # Assertions
        assert parsed is not None
        assert parsed["char_name"] == "Willow Whisperwind"
        assert parsed["char_class"] == "Ranger"
        assert parsed["char_level"] == 3
        assert len(parsed["weapons"]) == 1
        assert parsed["weapons"][0]["name"] == "Shortbow"
        assert len(parsed["equipment"]) == 1
        assert parsed["equipment"][0]["name"] == "Leather armor"
        assert "Goodberry" in parsed["spells"]["level_1"]


def test_extract_real_pdf_ulad_bohr():
    import os

    pdf_path = "Ulad Bohr.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Ulad Bohr.pdf not found in root directory")

    with open(pdf_path, "rb") as f:
        result = extract_text_and_fields_from_pdf(f)

    # Assert that core attributes from the real character sheet are found in the extracted text
    assert "Leather Armor" in result
    assert "Longbow +1" in result
    assert "Shortswords x 2" in result
    assert "Favored Enemy" in result
    assert "Speak with Animals" in result
    assert "Planar Warrior" in result
