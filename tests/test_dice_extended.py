from backend.services.dice_service import roll_dice
from backend.utils.dice import roll_dice as utils_roll_dice


def test_roll_dice_extended():
    res1 = roll_dice("1d8 + 4 slashing")
    assert res1["num_dice"] == 1
    assert res1["sides"] == 8
    assert res1["modifier"] == 4

    res2 = roll_dice("2d6 - 1 fire")
    assert res2["num_dice"] == 2
    assert res2["sides"] == 6
    assert res2["modifier"] == -1

    res3 = roll_dice("d20")
    assert res3["num_dice"] == 1
    assert res3["sides"] == 20
    assert res3["modifier"] == 0

    res4 = utils_roll_dice("1d8 + 4 slashing")
    assert res4.get("modifier") == 4
    assert len(res4.get("rolls")) == 1
