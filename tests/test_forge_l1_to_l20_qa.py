"""End-to-end Level 1 -> Level 20 Character Forge & Progression QA test suite."""

from unittest.mock import patch

import mongomock
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.services.forge_service import forge_character, forge_character_manual
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter


class _AsyncCursor:
    def __init__(self, items):
        self._it = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length=None):
        return list(self._it)


class _AsyncCollection:
    def __init__(self, col):
        self._col = col

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def insert_one(self, doc):
        return self._col.insert_one(doc)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def distinct(self, key):
        return self._col.distinct(key)

    def find(self, *args, **kwargs):
        return _AsyncCursor(list(self._col.find(*args, **kwargs)))


class _AsyncDB:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return _AsyncCollection(self._db[name])


def _level_up_to_20(
    client: TestClient,
    mdb,
    char_id: str,
    char_class: str,
    primary_stat: str,
    *,
    subclass_pick: str | None = None,
):
    for target_lvl in range(2, 21):
        cur = mdb["characters"].find_one({"char_id": char_id})
        cur.pop("_id", None)
        analysis_resp = client.post(
            "/api/v1/forge/level-up-analysis",
            json={"character": cur, "target_class": char_class},
        )
        assert analysis_resp.status_code == 200
        analysis = analysis_resp.json()

        user_choices = {"hp_method": "average", "level_up_class": char_class}
        sub_choice = None
        for idx, ch in enumerate(analysis.get("choices_required") or []):
            if ch.get("type") == "subclass" and ch.get("options"):
                opts = ch["options"]
                pick = (
                    next((o for o in opts if subclass_pick.lower() in o.lower()), opts[0])
                    if subclass_pick
                    else opts[0]
                )
                sub_choice = pick
                user_choices[f"subclass_{idx}"] = pick

        if sub_choice:
            user_choices["subclass"] = sub_choice
            reanalysis = client.post(
                "/api/v1/forge/level-up-analysis",
                json={"character": cur, "user_choices": user_choices},
            )
            assert reanalysis.status_code == 200
            analysis = reanalysis.json()

        seen_spells = {
            str(s).lower()
            for lst in (cur.get("spells") or {}).values()
            if isinstance(lst, list)
            for s in lst
        }
        seen_feats = {
            str(f.get("name") or "").lower()
            for f in (cur.get("features_traits") or [])
            if isinstance(f, dict)
        }
        seen_other_choices: set[str] = set()

        for idx, ch in enumerate(analysis.get("choices_required") or []):
            ct = ch.get("type")
            opts = ch.get("options") or []
            key = f"{ct}_{idx}"
            if ct == "subclass":
                if key not in user_choices and opts:
                    user_choices[key] = sub_choice or opts[0]
            elif ct == "feat" or "feat" in (ch.get("label") or "").lower():
                if "+2 to one Stat" in opts:
                    user_choices[key] = "+2 to one Stat"
                    user_choices[f"{ct}_stat1_{idx}"] = (
                        primary_stat
                        if (cur["stats"].get(primary_stat, 10) < 20 or target_lvl >= 19)
                        else "CON"
                    )
                elif opts:
                    pick = next((o for o in opts if o.lower() not in seen_feats), opts[0])
                    user_choices[key] = pick
                    fm = (ch.get("feat_metadata") or {}).get(pick) or {}
                    if fm.get("has_stat_choice"):
                        user_choices[f"{ct}_stat1_{idx}"] = (
                            fm.get("stat_choice_options") or ["CON"]
                        )[0]
            elif ct == "spell" or "spell" in (ch.get("label") or "").lower():
                pick = next(
                    (o for o in opts if o.lower() not in seen_spells), opts[0] if opts else None
                )
                if pick:
                    user_choices[key] = pick
                    seen_spells.add(pick.lower())
            elif opts:
                pick = next(
                    (
                        o
                        for o in opts
                        if o.lower() not in seen_other_choices and o.lower() not in seen_feats
                    ),
                    opts[0],
                )
                user_choices[key] = pick
                seen_other_choices.add(pick.lower())

        apply_resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": char_id,
                "analysis": analysis,
                "user_choices": user_choices,
            },
        )
        assert apply_resp.status_code == 200, apply_resp.text

    final_doc = mdb["characters"].find_one({"char_id": char_id})
    return final_doc


@patch("backend.services.forge_service.generate_ai_json", return_value=None)
def test_forge_variant_human_and_fallback_stats_spells_parity(_mock_ai):
    vh = forge_character(
        target_level=1,
        forge_race="Variant Human",
        forge_class="Fighter",
        forge_background="Soldier",
        concept="Seasoned halberdier",
        name="Vex",
        edition=EDITION_2014,
    )
    assert vh["stats"]["STR"] == 16
    assert vh["stats"]["CON"] == 15
    assert any(a.get("level") == 1 and a.get("type") == "Feat" for a in vh["advancements"])

    wiz = forge_character(
        target_level=1,
        forge_race="Elf",
        forge_class="Wizard",
        forge_background="Sage",
        concept="Apprentice mage",
        name="Alden",
        edition=EDITION_2014,
    )
    assert wiz["stats"]["INT"] == 15

    clr = forge_character_manual(
        target_level=5,
        race="Dwarf",
        char_class="Cleric",
        background="Acolyte",
        subclass=None,
        alignment="Lawful Good",
        gender="Male",
        name="Zogal Check",
        base_stats={"STR": 14, "DEX": 10, "CON": 15, "INT": 10, "WIS": 15, "CHA": 12},
        skill_proficiencies=["Religion", "Insight"],
        saving_throws=["WIS", "CHA"],
        spell_ability="WIS",
        concept="",
        edition=EDITION_2014,
    )
    assert len(clr["spells"]["cantrips"]) == 4
    assert clr["spells"]["level_2"]
    assert clr["spells"]["level_3"]


@patch("backend.services.forge_service.generate_ai_json", return_value=None)
def test_l1_to_l20_progression_artificer_ek_warlock_barbarian_monk(_mock_ai):
    mdb = mongomock.MongoClient()["qa_l1_l20_reg"]
    orig_overrides = dict(app.dependency_overrides)
    orig_limiter = limiter.enabled
    limiter.enabled = False
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "qa_u",
        "username": "qa",
        "name": "QA",
        "role": "player",
        "is_admin": False,
    }
    app.dependency_overrides[get_database] = lambda: _AsyncDB(mdb)
    client = TestClient(app)

    try:
        # 1. 2014 Artificer -> L1..L5 spells, 4 cantrips, Flash of Genius (INT mod)
        art = forge_character_manual(
            1,
            "Gnome",
            "Artificer",
            "Soldier",
            None,
            "Neutral",
            "Male",
            "Gimble",
            {"STR": 8, "DEX": 14, "CON": 13, "INT": 15, "WIS": 12, "CHA": 10},
            ["Arcana", "Investigation"],
            [],
            None,
            "",
            edition=EDITION_2014,
        )
        art["char_id"] = "art_2014"
        art["owner_id"] = "qa_u"
        mdb["characters"].insert_one(dict(art))
        art20 = _level_up_to_20(client, mdb, "art_2014", "Artificer", "INT")
        assert art20["char_level"] == 20
        assert art20["spells"]["level_5"]
        assert len(art20["spells"]["cantrips"]) == 4
        assert any(
            r["name"] == "Flash of Genius" and r["max"] == 5 for r in art20["class_resources"]
        )

        # 2. 2024 Eldritch Knight Fighter -> Wizard cantrips + L1..L4 spells on L3 unlock
        ek = forge_character_manual(
            1,
            "Warforged",
            "Fighter",
            "Soldier",
            None,
            "Neutral",
            "Male",
            "Unit-9",
            {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8},
            ["Athletics", "Perception"],
            [],
            None,
            "",
            edition=EDITION_2024,
        )
        ek["char_id"] = "ek_2024"
        ek["owner_id"] = "qa_u"
        mdb["characters"].insert_one(dict(ek))
        ek20 = _level_up_to_20(
            client, mdb, "ek_2024", "Fighter", "STR", subclass_pick="Eldritch Knight"
        )
        assert ek20["char_level"] == 20
        assert ek20["subclass"] == "Eldritch Knight"
        assert len(ek20["spells"]["cantrips"]) == 3
        assert ek20["spells"]["level_4"]

        # 3. 2024 Warlock -> Pact slots at level_5 + 1 Mystic Arcanum per 6..9 + 4 cantrips
        wlk = forge_character_manual(
            1,
            "Tiefling",
            "Warlock",
            "Soldier",
            None,
            "Neutral",
            "Male",
            "Mordai",
            {"STR": 8, "DEX": 14, "CON": 13, "INT": 10, "WIS": 12, "CHA": 15},
            ["Arcana", "Deception"],
            [],
            None,
            "",
            edition=EDITION_2024,
        )
        wlk["char_id"] = "wlk_2024"
        wlk["owner_id"] = "qa_u"
        mdb["characters"].insert_one(dict(wlk))
        wlk20 = _level_up_to_20(client, mdb, "wlk_2024", "Warlock", "CHA")
        assert wlk20["char_level"] == 20
        assert list(wlk20["spell_slots"].keys()) == ["level_5"]
        assert len(wlk20["spells"]["cantrips"]) == 4
        for tier in ("level_6", "level_7", "level_8", "level_9"):
            assert len(wlk20["spells"][tier]) == 1

        # 4. 2014 Barbarian -> Fast Movement (+10 speed) & Primal Champion (+4 STR/+4 CON, cap 24)
        barb = forge_character_manual(
            1,
            "Half-Orc",
            "Barbarian",
            "Soldier",
            None,
            "Chaotic Neutral",
            "Male",
            "Krag",
            {"STR": 15, "DEX": 14, "CON": 13, "INT": 8, "WIS": 10, "CHA": 12},
            ["Athletics", "Survival"],
            [],
            None,
            "",
            edition=EDITION_2014,
        )
        barb["char_id"] = "barb_2014"
        barb["owner_id"] = "qa_u"
        mdb["characters"].insert_one(dict(barb))
        barb20 = _level_up_to_20(client, mdb, "barb_2014", "Barbarian", "STR")
        assert barb20["char_level"] == 20
        assert barb20["speed"] == 40
        assert barb20["stats"]["STR"] == 24
        assert barb20["stats"]["CON"] >= 17

        # 5. 2024 Monk -> Unarmored Movement (60 ft), Martial Arts 1d12 DEX, Body & Mind (cap 25)
        mnk = forge_character_manual(
            1,
            "Human",
            "Monk",
            "Soldier",
            None,
            "Lawful Neutral",
            "Male",
            "Kenshin",
            {"STR": 10, "DEX": 15, "CON": 13, "INT": 12, "WIS": 14, "CHA": 8},
            ["Acrobatics", "Insight"],
            [],
            None,
            "",
            edition=EDITION_2024,
        )
        mnk["char_id"] = "mnk_2024"
        mnk["owner_id"] = "qa_u"
        mdb["characters"].insert_one(dict(mnk))
        mnk20 = _level_up_to_20(client, mdb, "mnk_2024", "Monk", "DEX")
        assert mnk20["char_level"] == 20
        assert mnk20["speed"] == 60
        assert mnk20["stats"]["DEX"] == 25
        assert mnk20["stats"]["WIS"] == 18
        qstaff = next(w for w in mnk20["weapons"] if "quarterstaff" in w["name"].lower())
        assert qstaff["attack_bonus"] == "+13"
        assert qstaff["damage"] == "1d12 + 7"
    finally:
        limiter.enabled = orig_limiter
        app.dependency_overrides = orig_overrides


@patch("backend.services.forge_service.generate_ai_json", return_value=None)
def test_2014_subraces_and_2024_species_parity(_mock_ai):
    from backend.repositories.rules_repository import RulesRepository
    from backend.services.validation_service import get_character_armor_proficiencies

    repo = RulesRepository()

    # 2014 Wood Elf: +2 DEX, +1 WIS, speed 35 ft, Keen Senses (Perception)
    wood_elf = forge_character(
        target_level=1,
        forge_race="Wood Elf",
        forge_class="Ranger",
        forge_background="Outlander",
        concept="Forest tracker",
        name="Theren",
        edition=EDITION_2014,
    )
    assert wood_elf["stats"]["DEX"] == 17  # 15 + 2
    assert wood_elf["stats"]["WIS"] == 15  # 14 + 1
    assert wood_elf["speed"] == 35
    assert "Perception" in wood_elf["skill_proficiencies"]
    assert any(f["name"] == "Mask of the Wild" for f in wood_elf["features_traits"])

    # 2014 High Elf: +2 DEX, +1 INT, Cantrip & Elf Weapon Training (Wizard priority: INT=15->16, CON=14, DEX=13->15)
    high_elf = forge_character(
        target_level=1,
        forge_race="High Elf",
        forge_class="Wizard",
        forge_background="Sage",
        concept="Arcane blade",
        name="Aelar",
        edition=EDITION_2014,
    )
    assert high_elf["stats"]["INT"] == 16  # 15 + 1
    assert high_elf["stats"]["DEX"] == 15  # 13 + 2
    assert any(f["name"] == "Cantrip" for f in high_elf["features_traits"])
    assert any(f["name"] == "Elf Weapon Training" for f in high_elf["features_traits"])

    # 2014 Dark Elf (Drow) and "Drow" alias: +2 DEX, +1 CHA, Drow Magic & Superior Darkvision
    assert (repo.get_race_data("Drow", EDITION_2014) or {}).get("name") == "Dark Elf (Drow)"
    drow = forge_character(
        target_level=1,
        forge_race="Dark Elf (Drow)",
        forge_class="Rogue",
        forge_background="Criminal",
        concept="Underdark scout",
        name="Driz",
        edition=EDITION_2014,
    )
    assert drow["stats"]["DEX"] == 17  # 15 + 2
    assert drow["stats"]["CHA"] == 11  # 10 + 1
    assert any(f["name"] == "Drow Magic" for f in drow["features_traits"])

    # 2014 Hill Dwarf (+1 WIS, +2 CON, Dwarven Toughness +1 HP/lvl) vs Mountain Dwarf (+2 STR, +2 CON, Light/Medium Armor)
    hill_dwarf = forge_character_manual(
        1,
        "Hill Dwarf",
        "Cleric",
        "Acolyte",
        "Life Domain",
        "Lawful Good",
        "Male",
        "Torin",
        {"STR": 14, "DEX": 10, "CON": 15, "INT": 8, "WIS": 16, "CHA": 12},
        ["Religion", "Medicine"],
        [],
        None,
        "",
        edition=EDITION_2014,
    )
    assert hill_dwarf["speed"] == 25
    assert hill_dwarf["hp_max"] == 8 + 2 + 1  # d8 hit die + CON(+2) + Dwarven Toughness(+1)

    mtn_dwarf = forge_character(
        target_level=1,
        forge_race="Mountain Dwarf",
        forge_class="Wizard",
        forge_background="Soldier",
        concept="Armored abjurer",
        name="Bruenor",
        edition=EDITION_2014,
    )
    assert mtn_dwarf["stats"]["STR"] >= 10
    wiz_prog = repo.get_class_progression("Wizard", EDITION_2014)
    armor_profs = get_character_armor_proficiencies(mtn_dwarf, wiz_prog)
    assert {"light armor", "medium armor"}.issubset(armor_profs)

    # 2014 Half-Elf: +2 CHA and two distinct +1 bonuses + Skill Versatility (2 skills)
    half_elf = forge_character(
        target_level=1,
        forge_race="Half-Elf",
        forge_class="Bard",
        forge_background="Entertainer",
        concept="Diplomat",
        name="Lyric",
        edition=EDITION_2014,
    )
    assert half_elf["stats"]["CHA"] == 17  # 15 + 2
    assert sum(half_elf["stats"].values()) == sum((15, 14, 13, 12, 10, 8)) + 4
    assert any(f["name"] == "Skill Versatility" for f in half_elf["features_traits"])

    # 2014 Lightfoot Halfling: Naturally Stealthy trait WITHOUT forcing Stealth skill proficiency;
    # 2024 Halfling: Naturally Stealthy DOES grant Stealth skill proficiency
    lf_2014 = forge_character_manual(
        1,
        "Lightfoot Halfling",
        "Fighter",
        "Acolyte",
        None,
        "Neutral Good",
        "Male",
        "Pip",
        {"STR": 10, "DEX": 17, "CON": 14, "INT": 12, "WIS": 10, "CHA": 13},
        ["Athletics", "Perception"],
        [],
        None,
        "",
        edition=EDITION_2014,
    )
    assert any(f["name"] == "Naturally Stealthy" for f in lf_2014["features_traits"])
    assert "Stealth" not in lf_2014["skill_proficiencies"]

    half_2024 = forge_character_manual(
        1,
        "Halfling",
        "Fighter",
        "Acolyte",
        None,
        "Neutral Good",
        "Male",
        "Milo",
        {"STR": 10, "DEX": 17, "CON": 14, "INT": 12, "WIS": 10, "CHA": 13},
        ["Athletics", "Perception"],
        [],
        None,
        "",
        edition=EDITION_2024,
    )
    assert "Stealth" in half_2024["skill_proficiencies"]
    assert (repo.get_race_data("Drow", EDITION_2024) or {}).get("name") == "Elf"
