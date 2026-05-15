from backend.utils.dice import roll_dice, quick_roll


class TestRollDiceEdgeCases:
    def test_spaces_in_input(self):
        """Spaces should be stripped before parsing."""
        result = roll_dice("1 d 20 + 5")
        assert "error" not in result
        assert result["modifier"] == 5

    def test_uppercase_d(self):
        """Capital D should still work (e.g. '1D20')."""
        result = roll_dice("1D20")
        assert "error" not in result
        assert 1 <= result["total"] <= 20

    def test_large_number_of_dice(self):
        """Rolling many dice should produce correct count."""
        result = roll_dice("10d6")
        assert "error" not in result
        assert len(result["rolls"]) == 10
        assert 10 <= result["total"] <= 60

    def test_d100(self):
        """d100 (percentile) should work."""
        result = roll_dice("1d100")
        assert "error" not in result
        assert 1 <= result["total"] <= 100

    def test_negative_modifier(self):
        result = roll_dice("1d20-3")
        assert result["modifier"] == -3

    def test_zero_modifier_result_text(self):
        """With no modifier, result_text should not show '+ 0'."""
        result = roll_dice("1d20")
        assert "+ 0" not in result["result_text"]
        assert "+" not in result["result_text"]

    def test_result_text_with_modifier(self):
        """With a modifier, result text should include it."""
        result = roll_dice("1d20+5")
        assert "+ 5" in result["result_text"]

    def test_only_modifier_no_dice_fails(self):
        """Just a number should fail."""
        result = roll_dice("+5")
        assert "error" in result

    def test_empty_string_fails(self):
        result = roll_dice("")
        assert "error" in result

    def test_d_alone_fails(self):
        """Just 'd' is not valid."""
        result = roll_dice("d")
        assert "error" in result


class TestQuickRollEdgeCases:
    def test_d4(self):
        total, raw = quick_roll(4)
        assert 1 <= raw <= 4
        assert total == raw  # no modifier

    def test_negative_modifier(self):
        total, raw = quick_roll(20, -3)
        assert total == raw - 3

    def test_modifier_zero(self):
        total, raw = quick_roll(6, 0)
        assert total == raw
