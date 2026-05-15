from backend.utils.dice import roll_dice, quick_roll


def test_roll_dice_valid():
    # Test simple roll
    result = roll_dice("1d20")
    assert "error" not in result
    assert 1 <= result["total"] <= 20
    assert len(result["rolls"]) == 1

    # Test with modifier
    result = roll_dice("1d20+5")
    assert 6 <= result["total"] <= 25
    assert result["modifier"] == 5

    # Test multiple dice
    result = roll_dice("2d8-2")
    assert 0 <= result["total"] <= 14
    assert len(result["rolls"]) == 2
    assert result["modifier"] == -2


def test_roll_dice_invalid():
    result = roll_dice("not a dice")
    assert "error" in result

    result = roll_dice("d20")  # Missing number of dice
    assert "error" in result


def test_quick_roll():
    total, raw = quick_roll(20, 5)
    assert 6 <= total <= 25
    assert 1 <= raw <= 20
    assert total == raw + 5
