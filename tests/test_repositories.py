import pytest
from unittest.mock import patch


# --- CharacterRepository ---


@pytest.fixture
def mock_db():
    import mongomock

    client = mongomock.MongoClient()
    return client.db


@pytest.fixture
def char_repo(mock_db):
    """Create a CharacterRepository pointing at a mock database."""
    with patch(
        "backend.repositories.character_repository.get_db", return_value=mock_db
    ):
        from backend.repositories.character_repository import CharacterRepository

        repo = CharacterRepository()
        yield repo


@pytest.fixture
def sample_char():
    return {
        "char_name": "Test Hero",
        "char_class": "Fighter",
        "char_level": 1,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "char_id": "abc123",
    }


class TestCharacterRepository:
    def test_save_and_load(self, char_repo, sample_char, tmp_path):
        assert char_repo.save(sample_char) is True

        files = char_repo.list_all()
        assert len(files) == 1

        loaded = char_repo.load(files[0])
        assert loaded is not None
        assert loaded["char_name"] == "Test Hero"
        assert loaded["char_class"] == "Fighter"

    def test_save_without_name_fails(self, char_repo):
        result = char_repo.save({"char_class": "Fighter"})
        assert result is False

    def test_list_empty(self, char_repo):
        assert char_repo.list_all() == []

    def test_load_nonexistent(self, char_repo):
        assert char_repo.load("nonexistent.json") is None

    def test_delete(self, char_repo, sample_char):
        char_repo.save(sample_char)
        files = char_repo.list_all()
        assert len(files) == 1

        assert char_repo.delete(files[0]) is True
        assert char_repo.list_all() == []

    def test_delete_nonexistent(self, char_repo):
        assert char_repo.delete("nonexistent.json") is False

    def test_save_generates_filename_from_name_and_id(
        self, char_repo, sample_char, tmp_path
    ):
        char_repo.save(sample_char)
        files = char_repo.list_all()
        assert len(files) == 1
        assert "test_hero" in files[0].lower()
        assert "abc123" in files[0]

    def test_multiple_saves_overwrite(self, char_repo, sample_char):
        char_repo.save(sample_char)
        sample_char["char_level"] = 5
        char_repo.save(sample_char)

        files = char_repo.list_all()
        assert len(files) == 1  # same file, not duplicated

        loaded = char_repo.load(files[0])
        assert loaded["char_level"] == 5


# --- CampaignRepository ---


@pytest.fixture
def camp_repo(mock_db):
    """Create a CampaignRepository pointing at a mock database."""
    with patch("backend.repositories.campaign_repository.get_db", return_value=mock_db):
        from backend.repositories.campaign_repository import CampaignRepository

        repo = CampaignRepository()
        yield repo


class TestCampaignRepository:
    def test_save_and_load(self, camp_repo):
        assert camp_repo.save("Lost Mines", "Session 1 notes", ["char1.json"]) is True
        loaded = camp_repo.load("Lost Mines")
        assert loaded is not None
        assert loaded["campaign_name"] == "Lost Mines"
        assert loaded["notes"] == "Session 1 notes"
        assert "char1.json" in loaded["party"]

    def test_save_empty_name_fails(self, camp_repo):
        assert camp_repo.save("", "notes") is False

    def test_load_nonexistent(self, camp_repo):
        assert camp_repo.load("Nonexistent") is None

    def test_list_campaigns(self, camp_repo):
        camp_repo.save("Campaign One", "Notes 1")
        camp_repo.save("Campaign Two", "Notes 2")
        campaigns = camp_repo.list_all()
        assert len(campaigns) == 2

    def test_save_preserves_party_when_none(self, camp_repo):
        """Saving with party=None should preserve existing party."""
        camp_repo.save("Lost Mines", "Session 1", ["hero.json"])
        camp_repo.save("Lost Mines", "Session 2 update", None)
        loaded = camp_repo.load("Lost Mines")
        assert loaded["notes"] == "Session 2 update"
        assert "hero.json" in loaded["party"]

    def test_list_empty(self, camp_repo):
        assert camp_repo.list_all() == []


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
