from backend.utils.dnd_math import calculate_ability_modifier
import pytest


@pytest.mark.parametrize(
    "score, expected_modifier",
    [
        (10, 0),
        (15, 2),
        (8, -1),
        (18, 4),
        (30, 10),
    ],
)
def test_calculate_ability_modifier(score, expected_modifier):
    assert calculate_ability_modifier(score) == expected_modifier


def test_calculate_ability_with_invalid_score():
    with pytest.raises(ValueError):
        calculate_ability_modifier(-5)
