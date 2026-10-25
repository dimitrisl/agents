"""Test suite for Mobile/Tablet Player Companion features (#170-#175).

Validates:
- CurrencySchema defaults, validation, and serialization in CharacterSchema (#174)
- ClassResourceSchema normalization and short/long rest mechanics (#173)
- EquipmentItem quantity support and backwards-compatibility (#174)
- CharacterSchema backward compatibility with legacy payloads missing new companion fields
"""

from backend.core.schemas import (
    CharacterSchema,
    ClassResourceSchema,
    CurrencySchema,
    EquipmentItem,
)


def test_currency_schema_defaults_and_validation():
    """Verify CurrencySchema defaults to 0 and clamps negative values."""
    curr = CurrencySchema()
    assert curr.cp == 0
    assert curr.sp == 0
    assert curr.ep == 0
    assert curr.gp == 0
    assert curr.pp == 0

    # Negative inputs convert to 0 safely
    clamped = CurrencySchema(cp=-5, sp=-10, gp=50)
    assert clamped.cp == 0
    assert clamped.sp == 0
    assert clamped.gp == 50

    # Explicit None and string inputs convert safely via mode="before"
    none_and_str = CurrencySchema(cp=None, sp="12", ep="invalid", gp=None, pp=3)  # type: ignore
    assert none_and_str.cp == 0
    assert none_and_str.sp == 12
    assert none_and_str.ep == 0
    assert none_and_str.gp == 0
    assert none_and_str.pp == 3


def test_class_resource_schema_normalization():
    """Verify ClassResourceSchema clamps current to max and normalizes recharge."""
    # current > max clamped to max
    res1 = ClassResourceSchema(name="Rage", current=5, max=3, recharge="long")
    assert res1.current == 3
    assert res1.max == 3
    assert res1.recharge == "long"

    # negative current clamped to 0
    res2 = ClassResourceSchema(name="Ki Points", current=-2, max=5, recharge="short")
    assert res2.current == 0
    assert res2.max == 5
    assert res2.recharge == "short"

    # Invalid recharge string normalizes to long
    res3 = ClassResourceSchema(name="Channel Divinity", current=1, max=1, recharge="daily")
    assert res3.recharge == "long"

    # Explicit None for current and max normalizes safely without TypeError
    res4 = ClassResourceSchema(name="Second Wind", current=None, max=None, recharge=None)  # type: ignore
    assert res4.max == 1
    assert res4.current == 1
    assert res4.recharge == "long"


def test_equipment_item_quantity_defaults_and_validation():
    """Verify EquipmentItem quantity defaults to 1 and parses safely."""
    item_default = EquipmentItem(name="Longsword")
    assert item_default.quantity == 1

    item_custom = EquipmentItem(name="Arrow", quantity=20)
    assert item_custom.quantity == 20

    item_str = EquipmentItem(name="Rations", quantity="5")  # type: ignore
    assert item_str.quantity == 5

    item_none = EquipmentItem(name="Torch", quantity=None)  # type: ignore
    assert item_none.quantity == 1


def test_character_schema_backward_compatibility():
    """Verify legacy payloads missing currency or class_resources validate cleanly."""
    legacy_data = {
        "char_name": "Valeros",
        "char_class": "Fighter",
        "char_level": 3,
        "race": "Human",
        "background": "Soldier",
        "armor_class": 16,
        "hp_max": 28,
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "equipment": [{"name": "Chain Mail"}, {"name": "Shield"}],
    }

    char = CharacterSchema(**legacy_data)
    assert char.char_name == "Valeros"
    assert char.currency is not None
    assert char.currency.gp == 0
    assert isinstance(char.class_resources, list)
    assert len(char.class_resources) == 0
    assert len(char.equipment) == 2
    assert char.equipment[0].quantity == 1
    assert char.equipment[1].quantity == 1


def test_character_schema_with_companion_fields():
    """Verify CharacterSchema parses and serializes currency and class resources."""
    payload = {
        "char_name": "Eldrin",
        "char_class": "Monk",
        "char_level": 5,
        "race": "Elf",
        "background": "Hermit",
        "armor_class": 15,
        "hp_max": 38,
        "stats": {"STR": 10, "DEX": 16, "CON": 14, "INT": 12, "WIS": 16, "CHA": 8},
        "currency": {"cp": 15, "sp": 24, "ep": 0, "gp": 150, "pp": 2},
        "class_resources": [
            {"name": "Focus Points", "current": 3, "max": 5, "recharge": "short"},
            {"name": "Second Wind", "current": 1, "max": 1, "recharge": "short"},
        ],
        "equipment": [
            {"name": "Potion of Healing", "quantity": 3, "equipped": False},
            {"name": "Ring of Protection", "quantity": 1, "equipped": True, "attuned": True},
        ],
    }

    char = CharacterSchema(**payload)
    assert char.currency.gp == 150
    assert char.currency.pp == 2
    assert len(char.class_resources) == 2
    assert char.class_resources[0].name == "Focus Points"
    assert char.class_resources[0].current == 3
    assert char.class_resources[0].max == 5
    assert char.class_resources[0].recharge == "short"

    # Attunement and quantity
    assert char.equipment[0].quantity == 3
    assert char.equipment[1].attuned is True
    assert char.equipment[1].quantity == 1
