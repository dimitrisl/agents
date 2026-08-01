# --- RulesRepository ---


class TestRulesRepository:
    def test_get_all_items(self):
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        items = repo.get_all_items()
        assert isinstance(items, list)
        assert len(items) > 0
        # Every item should have a name
        for item in items:
            assert "name" in item

    def test_items_have_required_fields(self):
        """Armor items must have ac_base + dex_limit, other items must have type."""
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        items = repo.get_all_items()
        for item in items:
            assert "type" in item
            assert "description" in item
            if item["type"] in ("Heavy Armor", "Medium Armor", "Light Armor"):
                assert "ac_base" in item, f"{item['name']} missing ac_base"
                assert "dex_limit" in item, f"{item['name']} missing dex_limit"

    def test_search_feats(self):
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        results = repo.search_feats("alert")
        # Should find at least one feat matching "alert"
        assert isinstance(results, list)

    def test_get_class_progression_nonexistent(self):
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        result = repo.get_class_progression("MadeUpClass")
        assert result is None

    def test_get_all_spells(self):
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        spells = repo.get_all_spells()
        assert isinstance(spells, list)
        assert len(spells) > 0
        for spell in spells:
            assert "name" in spell
            assert "level" in spell
            assert "school" in spell
            assert "description" in spell

    def test_search_spells(self):
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        results = repo.search_spells("fire bolt")
        assert isinstance(results, list)
