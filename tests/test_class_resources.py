from backend.services.class_resources_service import rules_pools, sync_class_resources


def _by_name(pools):
    return {p["name"]: p for p in pools}


def sorcerer(level):
    return [{"class_name": "Sorcerer", "level": level}]


class TestRulesPools:
    def test_sorcery_points_equal_sorcerer_level_from_2nd(self):
        assert rules_pools(sorcerer(1), {}, "2014 Edition") == []
        pool = _by_name(rules_pools(sorcerer(8), {}, "2014 Edition"))["Sorcery Points"]
        assert pool["max"] == 8 and pool["recharge"] == "long"

    def test_monk_ki_is_a_short_rest_pool_and_renamed_focus_in_2024(self):
        assert _by_name(rules_pools([{"class_name": "Monk", "level": 5}], {}, "2014 Edition"))[
            "Ki Points"
        ] == {
            "name": "Ki Points",
            "max": 5,
            "recharge": "short",
            "auto": True,
            "_aliases": {"ki points", "ki"},
        }
        assert "Focus Points" in _by_name(
            rules_pools([{"class_name": "Monk", "level": 5}], {}, "2024 Revision")
        )

    def test_steps_use_the_highest_level_reached(self):
        def rage(lvl):
            return _by_name(rules_pools([{"class_name": "Barbarian", "level": lvl}], {}, "2014"))["Rage"]["max"]

        assert [rage(1), rage(3), rage(5), rage(6), rage(17)] == [2, 3, 3, 4, 6]

    def test_ability_based_pool_and_recharge_that_improves_with_level(self):
        stats = {"CHA": 18}  # +4
        early = _by_name(rules_pools([{"class_name": "Bard", "level": 4}], stats, "2014"))[
            "Bardic Inspiration"
        ]
        late = _by_name(rules_pools([{"class_name": "Bard", "level": 5}], stats, "2014"))[
            "Bardic Inspiration"
        ]
        assert early["max"] == 4 and early["recharge"] == "long"
        assert late["recharge"] == "short"  # Font of Inspiration
        low = _by_name(rules_pools([{"class_name": "Bard", "level": 1}], {"CHA": 8}, "2014"))[
            "Bardic Inspiration"
        ]
        assert low["max"] == 1  # never below 1

    def test_multiclass_gets_each_class_pool_at_its_own_level(self):
        pools = _by_name(
            rules_pools(
                [{"class_name": "Fighter", "level": 2}, {"class_name": "Sorcerer", "level": 3}],
                {},
                "2014",
            )
        )
        assert pools["Sorcery Points"]["max"] == 3
        assert pools["Action Surge"]["max"] == 1
        assert "Indomitable" not in pools

    def test_classes_without_pools(self):
        assert rules_pools([{"class_name": "Rogue", "level": 11}], {}, "2014") == []


class TestSyncClassResources:
    def test_new_pool_starts_full(self):
        result = sync_class_resources([], sorcerer(3), {}, "2014")
        assert result == [
            {"name": "Sorcery Points", "max": 3, "recharge": "long", "auto": True, "current": 3}
        ]

    def test_spent_points_stay_spent_when_the_level_rises(self):
        before = sync_class_resources([], sorcerer(3), {}, "2014")
        before[0]["current"] = 1
        after = sync_class_resources(before, sorcerer(4), {}, "2014")
        assert after[0]["max"] == 4 and after[0]["current"] == 1

    def test_a_full_pool_stays_full_when_the_level_rises(self):
        before = sync_class_resources([], sorcerer(3), {}, "2014")
        after = sync_class_resources(before, sorcerer(4), {}, "2014")
        assert after[0]["current"] == 4

    def test_hand_made_pool_is_adopted_not_duplicated_and_keeps_its_extra_uses(self):
        # Kael's sheet: "Sorcery Points" 5/10 typed in by hand at Sorcerer 8
        mine = [{"name": "Sorcery Points", "current": 5, "max": 10, "recharge": "long"}]
        result = sync_class_resources(mine, sorcerer(8), {}, "2014")
        assert len(result) == 1
        assert result[0] == {
            "name": "Sorcery Points",
            "max": 10,
            "recharge": "long",
            "auto": True,
            "bonus": 2,
            "current": 5,
        }
        # The bonus rides along on the next level up
        assert sync_class_resources(result, sorcerer(9), {}, "2014")[0]["max"] == 11

    def test_aliases_adopt_differently_named_hand_made_pools(self):
        result = sync_class_resources(
            [{"name": "ki", "current": 2, "max": 4}],
            [{"class_name": "Monk", "level": 4}],
            {},
            "2014",
        )
        assert [r["name"] for r in result] == ["Ki Points"]

    def test_custom_pools_are_kept_and_obsolete_rules_pools_dropped(self):
        custom = {"name": "Luck Points", "current": 3, "max": 3, "recharge": "long"}
        old_rules_pool = {
            "name": "Wild Shape",
            "current": 2,
            "max": 2,
            "recharge": "short",
            "auto": True,
        }
        result = sync_class_resources([custom, old_rules_pool], sorcerer(2), {}, "2014")
        names = [r["name"] for r in result]
        assert "Luck Points" in names  # untouched
        assert "Wild Shape" not in names  # no longer a druid
        assert "Sorcery Points" in names

    def test_a_negative_adjustment_is_kept_and_never_drops_below_one(self):
        pool = sync_class_resources([], sorcerer(8), {}, "2014")[0]
        pool.update(bonus=-2, max=6, current=6)
        assert sync_class_resources([pool], sorcerer(9), {}, "2014")[0]["max"] == 7
        pool.update(bonus=-20)
        assert sync_class_resources([pool], sorcerer(9), {}, "2014")[0]["max"] == 1
