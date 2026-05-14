import pytest
from backend.pdf_exporter import PDFMappingProvider, export_character_to_pdf


@pytest.fixture
def sample_char_data():
    return {
        "char_name": "Grog",
        "char_class": "Barbarian",
        "char_level": 5,
        "race": "Goliath",
        "background": "Outlander",
        "alignment": "Chaotic Neutral",
        "stats": {"STR": 18, "DEX": 12, "CON": 16, "INT": 8, "WIS": 10, "CHA": 8},
        "proficiency_bonus": 3,
        "hp_max": 65,
        "armor_class": 14,
        "skills": {"Athletics": 7, "Perception": 3},
        "skill_proficiencies": ["Athletics", "Perception"],
        "saving_throws": ["STR", "CON"],
        "weapons": [{"name": "Greatsword", "attack_bonus": "+7", "damage": "2d6 + 4"}],
        "equipment": ["Explorer's Pack", "Javelin (5)"],
        "features_traits": [
            {"name": "Rage", "description": "You can enter a rage as a bonus action."}
        ],
    }


def test_pdf_mapping_provider_load():
    # Test standard 5e mapping
    provider = PDFMappingProvider("standard_5e")
    assert provider.mapping != {}
    assert "identity" in provider.mapping
    assert provider.mapping["identity"]["CharacterName"] == "char_name"


def test_get_field_data(sample_char_data):
    provider = PDFMappingProvider("standard_5e")
    field_data = provider.get_field_data(sample_char_data)

    # Check Identity
    assert field_data["CharacterName"] == "Grog"
    assert field_data["ClassLevel"] == "Barbarian 5"
    assert field_data["ProfBonus"] == "+3"

    # Check Stats
    assert field_data["STR"] == "18"
    assert field_data["STRmod"] == "+4"
    assert field_data["INTmod"] == "-1"

    # Check Skills
    assert field_data["Athletics"] == "7"
    assert field_data["Check Box 26"] == "Yes"  # Athletics prof check
    assert field_data["Check Box 34"] == "Yes"  # Perception prof check
    assert field_data["Check Box 23"] == "/Off"  # Acrobatics (not prof)

    # Check Saving Throws
    assert field_data["ST Strength"] == "+7"  # 4 (mod) + 3 (prof)
    assert field_data["Check Box 11"] == "Yes"
    assert field_data["Check Box 12"] == "/Off"

    # Check Weapons
    assert field_data["Wpn Name"] == "Greatsword"
    assert field_data["Wpn1 AtkBonus"] == "+7"
    assert field_data["Wpn1 Damage"] == "2d6 + 4"


def test_export_to_pdf_missing_template(sample_char_data):
    # Should return None if template doesn't exist
    result = export_character_to_pdf(sample_char_data, "non_existent_template.pdf")
    assert result is None
