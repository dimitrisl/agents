"""
Unit tests for Static SRD Monsters datasets and RulesRepository integration.
Verifies file existence, JSON validity, CR 0-24 coverage, schema compliance,
caching behavior, strict immutability, query filtering, and ID lookups.
"""

import json
import os

import pytest

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.repositories.rules_repository import RulesRepository, _monsters_cache


@pytest.fixture(autouse=True)
def reset_monsters_cache():
    """Ensure in-memory monsters cache is clean before each test."""
    _monsters_cache.clear()
    yield
    _monsters_cache.clear()


class TestStaticMonstersDatasets:
    """Verifies that the static JSON files exist on disk and meet schema requirements."""

    def test_monsters_2014_file_exists_and_is_valid_json(self):
        filepath = os.path.join("data", "rules", "monsters_2014.json")
        assert os.path.exists(filepath), f"File {filepath} must exist"
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) >= 60, f"Expected at least 60 monsters in 2014, found {len(data)}"

    def test_monsters_2024_file_exists_and_is_valid_json(self):
        filepath = os.path.join("data", "rules", "monsters_2024.json")
        assert os.path.exists(filepath), f"File {filepath} must exist"
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) >= 60, f"Expected at least 60 monsters in 2024, found {len(data)}"

    def test_cr_range_coverage_both_editions(self):
        required_crs = {"0", "1/8", "1/4", "1/2", "1", "2", "3", "4", "5", "10", "15", "20", "24"}
        for ed in ("2014", "2024"):
            filepath = os.path.join("data", "rules", f"monsters_{ed}.json")
            with open(filepath, "r", encoding="utf-8") as f:
                monsters = json.load(f)
            found_crs = {str(m.get("cr")).strip() for m in monsters if "cr" in m}
            missing = required_crs - found_crs
            assert not missing, f"Edition {ed} is missing required CR milestones: {missing}"

    def test_monster_schema_required_fields(self):
        required_keys = {
            "id",
            "name",
            "edition",
            "origin",
            "is_public",
            "size",
            "type",
            "alignment",
            "cr",
            "cr_numeric",
            "ac",
            "hp",
            "max_hp",
            "speed",
            "stats",
            "senses",
            "languages",
            "description",
            "traits",
            "actions",
        }
        for ed in ("2014", "2024"):
            filepath = os.path.join("data", "rules", f"monsters_{ed}.json")
            with open(filepath, "r", encoding="utf-8") as f:
                monsters = json.load(f)
            for m in monsters:
                missing = required_keys - set(m.keys())
                assert not missing, (
                    f"Monster {m.get('name', 'Unknown')} in {ed} missing keys: {missing}"
                )
                assert m["id"].startswith("srd_"), f"ID {m['id']} must start with 'srd_'"
                assert m["origin"] == "official", f"Monster {m['id']} origin must be 'official'"
                assert m["is_public"] is True, f"Monster {m['id']} is_public must be True"
                assert m["edition"] == ed, f"Monster {m['id']} edition must be '{ed}'"
                assert isinstance(m["stats"], dict), f"Stats for {m['id']} must be a dict"
                for stat in ("str", "dex", "con", "int", "wis", "cha"):
                    assert stat in m["stats"], f"Stat {stat} missing in {m['id']}"
                    assert 1 <= m["stats"][stat] <= 30, (
                        f"Stat {stat} out of range (1-30) in {m['id']}"
                    )

    def test_monster_actions_and_rolls_structure(self):
        for ed in ("2014", "2024"):
            filepath = os.path.join("data", "rules", f"monsters_{ed}.json")
            with open(filepath, "r", encoding="utf-8") as f:
                monsters = json.load(f)
            has_attack_actions = False
            for m in monsters:
                assert isinstance(m["actions"], list), f"Actions in {m['id']} must be a list"
                for action in m["actions"]:
                    assert "name" in action, f"Action in {m['id']} missing 'name'"
                    assert "description" in action, f"Action in {m['id']} missing 'description'"
                    if action.get("attack_bonus") is not None:
                        has_attack_actions = True
                        assert isinstance(action["attack_bonus"], int)
            assert has_attack_actions, (
                f"Edition {ed} dataset must contain structured attack actions"
            )


class TestRulesRepositoryMonstersLoading:
    """Tests loading, caching, and edition normalization in RulesRepository."""

    def test_get_all_monsters_default_is_2014(self):
        repo = RulesRepository()
        monsters = repo.get_all_monsters()
        assert isinstance(monsters, list)
        assert len(monsters) >= 60
        assert all(m["edition"] == "2014" for m in monsters)

    def test_get_all_monsters_2014_explicit(self):
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        assert len(monsters) >= 60
        assert all(m["edition"] == "2014" for m in monsters)

    def test_get_all_monsters_2024_explicit(self):
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2024")
        assert len(monsters) >= 60
        assert all(m["edition"] == "2024" for m in monsters)

    def test_edition_normalization_aliases(self):
        repo = RulesRepository()
        m_2014_short = repo.get_all_monsters("2014")
        m_2014_full = repo.get_all_monsters(EDITION_2014)
        assert len(m_2014_short) == len(m_2014_full)
        assert [m["id"] for m in m_2014_short] == [m["id"] for m in m_2014_full]

        m_2024_short = repo.get_all_monsters("2024")
        m_2024_full = repo.get_all_monsters(EDITION_2024)
        assert len(m_2024_short) == len(m_2024_full)
        assert [m["id"] for m in m_2024_short] == [m["id"] for m in m_2024_full]

    def test_caching_behavior(self, monkeypatch):
        repo = RulesRepository()
        assert "2014" not in _monsters_cache
        res1 = repo.get_all_monsters("2014")
        assert "2014" in _monsters_cache
        assert len(_monsters_cache["2014"]) == len(res1)

        # Monkeypatch _load_json to fail if called again
        def fail_load(*args, **kwargs):
            pytest.fail("_load_json should not be called when cache is populated")

        monkeypatch.setattr("backend.repositories.rules_repository._load_json", fail_load)
        res2 = repo.get_all_monsters("2014")
        assert len(res2) == len(res1)

    def test_missing_dataset_returns_empty_list_gracefully(self, monkeypatch):
        repo = RulesRepository()
        monkeypatch.setattr("os.path.exists", lambda path: False)
        res = repo.get_all_monsters("2014")
        assert res == []


class TestRulesRepositoryMonstersImmutability:
    """Verifies that callers cannot mutate the cache under any circumstances."""

    def test_get_all_monsters_mutation_does_not_corrupt_cache(self):
        repo = RulesRepository()
        m1 = repo.get_all_monsters("2014")
        original_name = m1[0]["name"]
        original_len = len(m1)

        # Mutate returned list and dict
        m1[0]["name"] = "MUTATED_DRAGON"
        m1.pop()

        m2 = repo.get_all_monsters("2014")
        assert len(m2) == original_len
        assert m2[0]["name"] == original_name

    def test_get_monster_by_id_mutation_does_not_corrupt_cache(self):
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        target_id = monsters[0]["id"]
        original_hp = monsters[0]["hp"]

        m = repo.get_monster_by_id(target_id)
        assert m is not None
        m["hp"] = 999999

        m_fresh = repo.get_monster_by_id(target_id)
        assert m_fresh["hp"] == original_hp

    def test_search_monsters_mutation_does_not_corrupt_cache(self):
        repo = RulesRepository()
        results = repo.search_monsters(query="goblin", edition="2014")
        assert len(results) > 0
        original_name = results[0]["name"]

        results[0]["name"] = "MUTATED_SEARCH"
        fresh = repo.search_monsters(query="goblin", edition="2014")
        assert fresh[0]["name"] == original_name


class TestRulesRepositorySearchMonsters:
    """Tests the search_monsters query and filter capabilities."""

    def test_search_by_name_case_insensitive(self):
        repo = RulesRepository()
        r1 = repo.search_monsters(query="goblin", edition="2014")
        r2 = repo.search_monsters(query="GOBLIN", edition="2014")
        assert len(r1) > 0
        assert len(r1) == len(r2)
        assert any("goblin" in m["name"].lower() for m in r1)

    def test_search_by_type(self):
        repo = RulesRepository()
        dragons = repo.search_monsters(monster_type="dragon", edition="2014")
        assert len(dragons) > 0
        assert all("dragon" in m["type"].lower() for m in dragons)

    def test_search_by_description(self):
        repo = RulesRepository()
        results = repo.search_monsters(query="rapacious", edition="2014")
        if results:
            assert all(
                "rapacious" in m["description"].lower() or "rapacious" in m["name"].lower()
                for m in results
            )

    def test_search_empty_query_returns_all(self):
        repo = RulesRepository()
        all_monsters = repo.get_all_monsters("2014")
        search_all = repo.search_monsters(query="", edition="2014")
        assert len(search_all) == len(all_monsters)

    def test_search_edition_none_returns_both_editions(self):
        repo = RulesRepository()
        both = repo.search_monsters(edition=None)
        all_2014 = repo.get_all_monsters("2014")
        all_2024 = repo.get_all_monsters("2024")
        assert len(both) == len(all_2014) + len(all_2024)

    def test_search_by_cr_string_and_numeric_equivalent(self):
        repo = RulesRepository()
        res_str = repo.search_monsters(cr="1/4", edition="2014")
        res_num = repo.search_monsters(cr="0.25", edition="2014")
        assert len(res_str) > 0
        assert len(res_str) == len(res_num)

    def test_search_by_cr_zero(self):
        repo = RulesRepository()
        res_zero = repo.search_monsters(cr="0", edition="2014")
        assert len(res_zero) > 0
        assert all(m["cr"] == "0" or m["cr_numeric"] == 0.0 for m in res_zero)

    def test_search_combined_filters(self):
        repo = RulesRepository()
        res = repo.search_monsters(query="dragon", cr="24", edition="2014")
        assert len(res) >= 1
        assert any("Ancient Red Dragon" in m["name"] for m in res)

    def test_search_no_matches_returns_empty_list(self):
        repo = RulesRepository()
        res = repo.search_monsters(query="nonexistent_monster_xyz", edition="2014")
        assert res == []


class TestRulesRepositoryGetMonsterById:
    """Tests looking up individual monsters by ID."""

    def test_get_monster_by_id_2014_success(self):
        repo = RulesRepository()
        m = repo.get_monster_by_id("srd_goblin_2014")
        assert m is not None
        assert m["id"] == "srd_goblin_2014"
        assert m["name"] == "Goblin"
        assert m["edition"] == "2014"

    def test_get_monster_by_id_2024_success(self):
        repo = RulesRepository()
        m = repo.get_monster_by_id("srd_goblin_2024")
        assert m is not None
        assert m["id"] == "srd_goblin_2024"
        assert m["name"] == "Goblin"
        assert m["edition"] == "2024"

    def test_get_monster_by_id_case_insensitive(self):
        repo = RulesRepository()
        m = repo.get_monster_by_id("SRD_GOBLIN_2014")
        assert m is not None
        assert m["name"] == "Goblin"

    def test_get_monster_by_id_prefix_tolerant(self):
        repo = RulesRepository()
        m = repo.get_monster_by_id("goblin_2014")
        assert m is not None
        assert m["name"] == "Goblin"

    def test_get_monster_by_id_nonexistent_returns_none(self):
        repo = RulesRepository()
        assert repo.get_monster_by_id("srd_fakemonster_9999") is None

    def test_get_monster_by_id_empty_or_none_returns_none(self):
        repo = RulesRepository()
        assert repo.get_monster_by_id("") is None
        assert repo.get_monster_by_id(None) is None  # type: ignore


class TestRulesRepositoryMonstersEdgeCases:
    """Tests edge cases, malformed data handling, and parser robustness."""

    def test_cr_numeric_parser_edge_cases(self):
        repo = RulesRepository()
        assert repo._parse_cr_numeric("0") == 0.0
        assert repo._parse_cr_numeric("1/8") == 0.125
        assert repo._parse_cr_numeric("1/4") == 0.25
        assert repo._parse_cr_numeric("1/2") == 0.5
        assert repo._parse_cr_numeric("1") == 1.0
        assert repo._parse_cr_numeric(2) == 2.0
        assert repo._parse_cr_numeric("24") == 24.0
        assert repo._parse_cr_numeric(None) == 0.0
        assert repo._parse_cr_numeric("invalid_string") == 0.0
        assert repo._parse_cr_numeric("1/0") == 0.0

    def test_raw_item_with_missing_id_is_normalized(self, monkeypatch):
        repo = RulesRepository()
        fake_data = [
            {
                "name": "Custom Behemoth",
                "cr": "1/2",
                "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            }
        ]
        monkeypatch.setattr(
            "backend.repositories.rules_repository._load_json", lambda path: fake_data
        )
        monsters = repo.get_all_monsters("2014")
        assert len(monsters) == 1
        m = monsters[0]
        assert m["id"] == "srd_custom_behemoth_2014"
        assert m["origin"] == "official"
        assert m["is_public"] is True
        assert m["cr_numeric"] == 0.5

    def test_raw_item_with_non_srd_id_gets_srd_prefix(self, monkeypatch):
        repo = RulesRepository()
        fake_data = [
            {
                "id": "my_beast_2014",
                "name": "My Beast",
                "cr": "2",
                "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            }
        ]
        monkeypatch.setattr(
            "backend.repositories.rules_repository._load_json", lambda path: fake_data
        )
        monsters = repo.get_all_monsters("2014")
        assert len(monsters) == 1
        assert monsters[0]["id"] == "srd_my_beast_2014"
