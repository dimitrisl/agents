from backend.utils.dnd_math import calculate_ability_modifier
import pytest


def test_calculate_ability_modifier():
    assert calculate_ability_modifier(10) == 0
    assert calculate_ability_modifier(15) == 2
    assert calculate_ability_modifier(8) == -1
    assert calculate_ability_modifier(18) == 4


def test_calculate_ability_with_invalid_score():
    with pytest.raises(ValueError):
        calculate_ability_modifier(-5)
