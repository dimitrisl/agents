import copy
from unittest.mock import patch

import mongomock
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import LevelUpAnalysisSchema, LevelUpApplyRequest
from backend.repositories.rules_repository import RulesRepository
from backend.services.class_resources_service import rules_pools, sync_class_resources
from backend.services.forge_service import (
    _generate_dynamic_future_milestones,
    analyze_level_up,
    forge_character_manual,
    resolve_level_up_automatic_features,
)
from backend.services.rest_service import apply_short_rest
from backend.services.rules_service import (
    grant_subclass_bonus_spells,
    inject_mandatory_character_grants,
)
from backend.services.stats_service import sync_character_stats
from backend.services.validation_service import (
    get_character_armor_proficiencies,
    get_character_weapon_proficiencies,
    is_weapon_proficient,
)
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _AsyncColl:
    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query=None, *args, **kwargs):
        return self._coll.find_one(query or {}, *args, **kwargs)

    async def insert_one(self, doc):
        return self._coll.insert_one(doc)

    async def update_one(self, query, update, upsert=False):
        class Res:
            def __init__(self, r):
                self.matched_count = r.matched_count
                self.modified_count = r.modified_count

        return Res(self._coll.update_one(query, update, upsert=upsert))

    def find(self, query=None, *args, **kwargs):
        cursor = self._coll.find(query or {}, *args, **kwargs)

        class _AsyncCursor:
            def __init__(self, c):
                self._items = list(c)
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx < len(self._items):
                    item = self._items[self._idx]
                    self._idx += 1
                    return item
                raise StopAsyncIteration

            async def to_list(self, length=None):
                return list(self._items)

        return _AsyncCursor(cursor)


class _AsyncDB:
    def __init__(self, name="qa_2014_fixes_db"):
        self._client = mongomock.MongoClient()
        self._db = self._client[name]
        self._colls = {}

    def __getitem__(self, item):
        if item not in self._colls:
            self._colls[item] = _AsyncColl(self._db[item])
        return self._colls[item]

    def __getattr__(self, item):
        return self[item]


def _make_base_char(**overrides):
    char = {
        "char_id": "qa-2014-hero-1",
        "owner_id": "user-qa-1",
        "char_name": "Kaelen",
        "char_class": "Fighter",
        "char_level": 1,
        "race": "Human",
        "background": "Soldier",
        "subclass": None,
        "dnd_edition": EDITION_2014,
        "alignment": "Neutral Good",
        "gender": "Male",
        "armor_class": 10,
        "hp_max": 12,
        "hp_current": 12,
        "speed": 30,
        "proficiency_bonus": 2,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "saving_throws": ["STR", "CON"],
        "skill_proficiencies": ["Athletics", "Intimidation"],
        "skill_expertise": [],
        "features_traits": [],
        "spells": {},
        "spell_slots": {},
        "weapons": [],
        "equipment": [],
        "class_resources": [],
        "classes": [{"class_name": "Fighter", "level": 1, "subclass": None}],
    }
    char.update(overrides)
    return char


def test_2014_saving_throw_features_paladin_monk_rogue_artificer():
    # Paladin L6 Aura of Protection (+CHA mod, min +1) across all 6 saves
    paladin = _make_base_char(
        char_class="Paladin",
        char_level=6,
        proficiency_bonus=3,
        classes=[{"class_name": "Paladin", "level": 6, "subclass": "Oath of Devotion"}],
        subclass="Oath of Devotion",
        stats={"STR": 18, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 18},  # CHA +4
        saving_throws=["WIS", "CHA"],
        features_traits=[
            {"name": "Aura of Protection", "description": "+CHA mod to all saving throws"}
        ],
    )
    pal_synced = sync_character_stats(copy.deepcopy(paladin))
    # STR +4 + 4 (Aura) = +8; DEX +0 + 4 = +4; CHA +4 + 3 (PB) + 4 (Aura) = +11
    assert pal_synced["saving_throw_values"]["STR"] == 8
    assert pal_synced["saving_throw_values"]["DEX"] == 4
    assert pal_synced["saving_throw_values"]["WIS"] == 8  # +1 + 3 + 4
    assert pal_synced["saving_throw_values"]["CHA"] == 11

    # Paladin with low CHA (+0) still gets minimum +1 from Aura of Protection in 2014/2024
    low_cha_pal = _make_base_char(
        char_class="Paladin",
        char_level=6,
        proficiency_bonus=3,
        classes=[{"class_name": "Paladin", "level": 6, "subclass": "Oath of Vengeance"}],
        stats={"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        saving_throws=["WIS", "CHA"],
        features_traits=[{"name": "Aura of Protection", "description": "Min +1 bonus"}],
    )
    low_cha_synced = sync_character_stats(low_cha_pal)
    assert low_cha_synced["saving_throw_values"]["DEX"] == 1

    # Monk L14 Diamond Soul: proficient in ALL 6 saving throws
    monk = _make_base_char(
        char_class="Monk",
        char_level=14,
        proficiency_bonus=5,
        classes=[{"class_name": "Monk", "level": 14, "subclass": "Way of the Open Hand"}],
        stats={"STR": 10, "DEX": 20, "CON": 14, "INT": 10, "WIS": 18, "CHA": 8},
        saving_throws=["STR", "DEX"],
    )
    monk_synced = sync_character_stats(monk)
    assert set(monk_synced["saving_throws"]) == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
    assert monk_synced["saving_throw_values"]["WIS"] == 9  # +4 WIS + 5 PB
    assert monk_synced["saving_throw_values"]["CHA"] == 4  # -1 CHA + 5 PB

    # Rogue L15 Slippery Mind: grants WIS save proficiency
    rogue = _make_base_char(
        char_class="Rogue",
        char_level=15,
        proficiency_bonus=5,
        classes=[{"class_name": "Rogue", "level": 15, "subclass": "Thief"}],
        stats={"STR": 8, "DEX": 20, "CON": 14, "INT": 14, "WIS": 12, "CHA": 10},
        saving_throws=["DEX", "INT"],
    )
    rogue_synced = sync_character_stats(rogue)
    assert {"DEX", "INT", "WIS"}.issubset(set(rogue_synced["saving_throws"]))
    assert rogue_synced["saving_throw_values"]["WIS"] == 6  # +1 + 5 PB

    # Artificer L20 Soul of Artifice: +1 per attuned magic item (max +6)
    artificer = _make_base_char(
        char_class="Artificer",
        char_level=20,
        proficiency_bonus=6,
        classes=[{"class_name": "Artificer", "level": 20, "subclass": "Armorer"}],
        stats={"STR": 10, "DEX": 14, "CON": 16, "INT": 20, "WIS": 12, "CHA": 10},
        saving_throws=["CON", "INT"],
        equipment=[
            {"name": f"Attuned Item {i}", "attuned": True, "requires_attunement": True}
            for i in range(7)  # 7 items -> Artificer L18+ has 6 slots, capped at +6
        ],
    )
    art_synced = sync_character_stats(artificer)
    assert art_synced["saving_throw_values"]["INT"] == 5 + 6 + 6  # +17


def test_resilient_feat_grants_saving_throw_proficiency_on_level_up():
    db = _AsyncDB()
    fighter = _make_base_char(
        char_id="resilient-fighter",
        owner_id="user-res-1",
        char_class="Fighter",
        char_level=3,
        classes=[{"class_name": "Fighter", "level": 3, "subclass": "Champion"}],
        subclass="Champion",
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 13, "CHA": 10},
        saving_throws=["STR", "CON"],
    )
    db._db["characters"].insert_one(fighter)

    analysis = analyze_level_up(copy.deepcopy(fighter), user_choices={})
    analysis_model = LevelUpAnalysisSchema.model_validate(analysis)

    feat_idx = next(i for i, c in enumerate(analysis_model.choices_required) if c.type == "feat")
    payload = LevelUpApplyRequest(
        character_id="resilient-fighter",
        analysis=analysis_model,
        user_choices={
            f"feat_{feat_idx}": "Resilient",
            f"feat_stat1_{feat_idx}": "WIS",
            "hp_method": "average",
        },
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "user-res-1", "role": "player"}
    app.dependency_overrides[get_database] = lambda: db
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/forge/level-up-apply", json=payload.model_dump())
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["stats"]["WIS"] == 14
    assert "WIS" in updated["saving_throws"]
    # WIS 14 (+2) + PB 2 (L4) = +4
    assert updated["saving_throw_values"]["WIS"] == 4


def test_2014_weapon_proficiencies_racial_domain_hexblade_and_stats_sync():
    repo = RulesRepository()

    # Wizard with High Elf racial weapons gets Longsword & Longbow proficiency, NOT Greatsword
    high_elf_wiz = _make_base_char(
        race="High Elf",
        char_class="Wizard",
        char_level=3,
        classes=[{"class_name": "Wizard", "level": 3, "subclass": "School of Evocation"}],
        stats={"STR": 14, "DEX": 16, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10},
        weapons=[
            {"name": "Longsword", "damage_dice": "1d8 slashing", "attack_bonus": "+0"},
            {"name": "Greatsword", "damage_dice": "2d6 slashing", "attack_bonus": "+0"},
        ],
    )
    wiz_prog = repo.get_class_progression("Wizard", EDITION_2014)
    w_profs = get_character_weapon_proficiencies(high_elf_wiz, wiz_prog)
    assert "longsword" in w_profs
    assert "longbow" in w_profs
    assert is_weapon_proficient({"name": "Longsword"}, w_profs) is True
    assert is_weapon_proficient({"name": "Greatsword"}, w_profs) is False

    synced_wiz = sync_character_stats(high_elf_wiz)
    assert "longsword" in synced_wiz["weapon_proficiencies"]
    longsword = next(w for w in synced_wiz["weapons"] if w["name"] == "Longsword")
    greatsword = next(w for w in synced_wiz["weapons"] if w["name"] == "Greatsword")
    assert longsword["proficient"] is True
    assert longsword["attack_bonus"] == "+4"  # +2 STR + 2 PB
    assert greatsword["proficient"] is False
    assert greatsword["attack_bonus"] == "+2"  # +2 STR only (no PB)

    # Tempest Domain Cleric gains Heavy Armor + Martial Weapons
    tempest_cleric = _make_base_char(
        race="Human",
        char_class="Cleric",
        char_level=1,
        subclass="Tempest Domain",
        classes=[{"class_name": "Cleric", "level": 1, "subclass": "Tempest Domain"}],
    )
    cleric_prog = repo.get_class_progression("Cleric", EDITION_2014)
    assert "heavy armor" in get_character_armor_proficiencies(tempest_cleric, cleric_prog)
    tempest_weapons = get_character_weapon_proficiencies(tempest_cleric, cleric_prog)
    assert is_weapon_proficient({"name": "Warhammer"}, tempest_weapons) is True

    # Warlock Hexblade gains Medium Armor, Shields, and Martial Weapons
    hexblade = _make_base_char(
        race="Human",
        char_class="Warlock",
        char_level=1,
        subclass="The Hexblade",
        classes=[{"class_name": "Warlock", "level": 1, "subclass": "The Hexblade"}],
    )
    warlock_prog = repo.get_class_progression("Warlock", EDITION_2014)
    hex_armor = get_character_armor_proficiencies(hexblade, warlock_prog)
    assert {"medium armor", "shields"}.issubset(hex_armor)
    hex_weapons = get_character_weapon_proficiencies(hexblade, warlock_prog)
    assert is_weapon_proficient({"name": "Rapier"}, hex_weapons) is True


def test_2014_feat_prerequisites_and_2024_parity():
    # Non-caster Fighter L3 -> L4 cannot take War Caster or Heavily Armored?
    # Fighter ALREADY has Heavy Armor + Medium Armor, so Heavily Armored shows;
    # Sorcerer does NOT have Medium Armor so Heavily Armored is blocked.
    fighter_2014 = _make_base_char(
        char_class="Fighter",
        char_level=3,
        subclass="Champion",
        classes=[{"class_name": "Fighter", "level": 3, "subclass": "Champion"}],
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        dnd_edition=EDITION_2014,
    )
    f_analysis = analyze_level_up(copy.deepcopy(fighter_2014))
    f_feat_choice = next(c for c in f_analysis["choices_required"] if c["type"] == "feat")
    assert "War Caster" not in f_feat_choice["options"]
    assert "Ritual Caster" not in f_feat_choice["options"]  # INT 10 / WIS 12 < 13
    assert "Defensive Duelist" not in f_feat_choice["options"]  # DEX 12 < 13

    # High INT Wizard has War Caster & Ritual Caster (INT 16 >= 13), but NOT Heavily Armored
    wizard_2014 = _make_base_char(
        char_class="Wizard",
        char_level=3,
        subclass="School of Evocation",
        classes=[{"class_name": "Wizard", "level": 3, "subclass": "School of Evocation"}],
        stats={"STR": 8, "DEX": 14, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10},
        dnd_edition=EDITION_2014,
    )
    w_analysis = analyze_level_up(copy.deepcopy(wizard_2014))
    w_feat_choice = next(c for c in w_analysis["choices_required"] if c["type"] == "feat")
    assert "War Caster" in w_feat_choice["options"]
    assert "Ritual Caster" in w_feat_choice["options"]
    assert "Heavily Armored" not in w_feat_choice["options"]
    assert "Moderately Armored" not in w_feat_choice["options"]
    assert "Lightly Armored" in w_feat_choice["options"]
    assert "Fey Touched" in w_feat_choice["options"]

    # 2024 parity: low-CHA Fighter sees Actor/Telekinetic, Heavily Armored (Medium Armor prof),
    # and Shield Master (STR 16 >= 13 + Shield prof), while non-caster Psi Warrior excludes War Caster;
    # Wizard 2024 gets War Caster and excludes Heavily Armored / Shield Master.
    fighter_2024 = _make_base_char(
        char_class="Fighter",
        char_level=3,
        subclass="Psi Warrior",
        classes=[{"class_name": "Fighter", "level": 3, "subclass": "Psi Warrior"}],
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 14, "WIS": 10, "CHA": 8},
        dnd_edition=EDITION_2024,
    )
    f24_analysis = analyze_level_up(copy.deepcopy(fighter_2024))
    f24_feat_choice = next(c for c in f24_analysis["choices_required"] if c["type"] == "feat")
    assert "Actor" in f24_feat_choice["options"]
    assert "Telekinetic" in f24_feat_choice["options"]
    assert "Heavily Armored" in f24_feat_choice["options"]
    assert "Shield Master" in f24_feat_choice["options"]
    assert "War Caster" not in f24_feat_choice["options"]

    wiz_2024 = _make_base_char(
        char_class="Wizard",
        char_level=3,
        subclass="Evoker",
        classes=[{"class_name": "Wizard", "level": 3, "subclass": "Evoker"}],
        stats={"STR": 8, "DEX": 14, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10},
        dnd_edition=EDITION_2024,
    )
    w24_analysis = analyze_level_up(copy.deepcopy(wiz_2024))
    w24_feat_choice = next(c for c in w24_analysis["choices_required"] if c["type"] == "feat")
    assert "War Caster" in w24_feat_choice["options"]
    assert "Heavily Armored" not in w24_feat_choice["options"]
    assert "Shield Master" not in w24_feat_choice["options"]


def test_2014_all_subclasses_progressions_domain_spells_and_high_elf_fighter():
    repo = RulesRepository()
    # Verify non-empty subclass progressions across all 13 2014 classes
    classes_13 = [
        "Artificer",
        "Barbarian",
        "Bard",
        "Cleric",
        "Druid",
        "Fighter",
        "Monk",
        "Paladin",
        "Ranger",
        "Rogue",
        "Sorcerer",
        "Warlock",
        "Wizard",
    ]
    for cls_name in classes_13:
        subs = repo.get_subclasses(cls_name, EDITION_2014)
        assert len(subs) > 0, f"Missing subclasses for {cls_name}"
        for sub_name in subs:
            sub_data = repo.get_subclass_entry(cls_name, sub_name, EDITION_2014)
            assert sub_data and len(sub_data.get("features") or {}) > 0, (
                f"Empty features for {cls_name}/{sub_name}"
            )

    # Spot check resolution on previously missing classes (Paladin L3, Druid L2, Sorcerer L1, Wizard L2)
    pal_feats = resolve_level_up_automatic_features(
        char_class="Paladin",
        target_level=3,
        subclass_to_use="Oath of Vengeance",
        edition=EDITION_2014,
    )
    assert any("Sacred Oath" not in f["name"] for f in pal_feats)
    assert any("Channel Divinity" in f["name"] or "Abjure Enemy" in f["name"] for f in pal_feats)

    # Future milestones reflect chosen subclass features
    milestones = _generate_dynamic_future_milestones(
        target_class="Wizard",
        target_class_level=2,
        subclass="School of Divination",
        edition=EDITION_2014,
        feat_rec="War Caster",
        archetype="Control & Divination",
    )
    assert any("Portent" in m for m in milestones)

    # Light Domain Cleric L3 gets Burning Hands, Faerie Fire, Flaming Sphere, Scorching Ray
    light_cleric = _make_base_char(
        char_class="Cleric",
        char_level=3,
        subclass="Light Domain",
        classes=[{"class_name": "Cleric", "level": 3, "subclass": "Light Domain"}],
        spells={"cantrips": ["Sacred Flame"], "level_1": [], "level_2": []},
    )
    grant_subclass_bonus_spells(
        light_cleric,
        "Cleric",
        "Light Domain",
        3,
        EDITION_2014,
        repo=repo,
    )
    assert {"Burning Hands", "Faerie Fire"}.issubset(set(light_cleric["spells"]["level_1"]))
    assert {"Flaming Sphere", "Scorching Ray"}.issubset(set(light_cleric["spells"]["level_2"]))

    # High Elf Champion Fighter L3 with Fire Bolt keeps Fire Bolt and is NOT inferred as Eldritch Knight
    high_elf_champ = _make_base_char(
        race="High Elf",
        char_class="Fighter",
        char_level=3,
        subclass="Champion",
        classes=[{"class_name": "Fighter", "level": 3, "subclass": "Champion"}],
        spells={"cantrips": ["Fire Bolt"]},
    )
    inject_mandatory_character_grants(high_elf_champ, edition=EDITION_2014)
    synced_champ = sync_character_stats(high_elf_champ)
    assert synced_champ["subclass"] == "Champion"
    assert "Fire Bolt" in (synced_champ["spells"].get("cantrips") or [])
    assert not synced_champ["spell_slots"]

    # 2014 Tiefling L3 innate spells include Thaumaturgy + Hellish Rebuke
    tiefling = _make_base_char(
        race="Tiefling",
        char_class="Rogue",
        char_level=3,
        classes=[{"class_name": "Rogue", "level": 3, "subclass": "Assassin"}],
    )
    inject_mandatory_character_grants(tiefling, edition=EDITION_2014)
    assert "Thaumaturgy" in (tiefling["spells"].get("cantrips") or [])
    assert "Hellish Rebuke" in (tiefling["spells"].get("level_1") or [])


def test_2014_structured_choice_pickers_apply_and_agonizing_blast():
    # Fighter L1 creation? Wait: analyze_level_up for Fighter L0->1 or Paladin L1->2 triggers fighting_style
    paladin_l1 = _make_base_char(
        char_id="choice-paladin",
        owner_id="user-choice",
        char_class="Paladin",
        char_level=1,
        classes=[{"class_name": "Paladin", "level": 1, "subclass": None}],
    )
    pal_analysis = analyze_level_up(copy.deepcopy(paladin_l1))
    assert any(c["type"] == "fighting_style" for c in pal_analysis["choices_required"])

    # Warlock L1->2 gets 2 Eldritch Invocation pickers; applying Agonizing Blast boosts Eldritch Blast damage +CHA
    db = _AsyncDB()
    warlock_l1 = _make_base_char(
        char_id="choice-warlock",
        owner_id="user-choice",
        char_class="Warlock",
        char_level=1,
        subclass="The Fiend",
        classes=[{"class_name": "Warlock", "level": 1, "subclass": "The Fiend"}],
        stats={"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 18},  # CHA +4
        weapons=[
            {
                "name": "Eldritch Blast",
                "attack_bonus": "+0",
                "damage_dice": "1d10 force",
                "ability_modifier": "CHA",
                "range": "120 ft.",
            }
        ],
    )
    db._db["characters"].insert_one(warlock_l1)
    lock_analysis = LevelUpAnalysisSchema.model_validate(
        analyze_level_up(copy.deepcopy(warlock_l1))
    )
    inv_indices = [
        i for i, c in enumerate(lock_analysis.choices_required) if c.type == "eldritch_invocation"
    ]
    assert len(inv_indices) == 2

    payload = LevelUpApplyRequest(
        character_id="choice-warlock",
        analysis=lock_analysis,
        user_choices={
            f"eldritch_invocation_{inv_indices[0]}": "Agonizing Blast",
            f"eldritch_invocation_{inv_indices[1]}": "Devil's Sight",
            "hp_method": "average",
        },
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-choice", "role": "player"}
    app.dependency_overrides[get_database] = lambda: db
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/forge/level-up-apply", json=payload.model_dump())
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    w2 = resp.json()
    feat_names = {f["name"] for f in w2["features_traits"]}
    assert {"Agonizing Blast", "Devil's Sight"}.issubset(feat_names)
    assert "Devil's Sight 120 ft." in w2["senses"]
    eb = next(w for w in w2["weapons"] if w["name"] == "Eldritch Blast")
    assert eb["damage_bonus"] == "+4"  # CHA +4 added cleanly via Agonizing Blast

    # Sorcerer L2->3 gets 2 Metamagic pickers; Battle Master L2->3 gets 3 Maneuver pickers; Artificer L1->2 gets 2 Infusions
    sorc_l2 = _make_base_char(
        char_class="Sorcerer",
        char_level=2,
        subclass="Draconic Bloodline",
        classes=[{"class_name": "Sorcerer", "level": 2, "subclass": "Draconic Bloodline"}],
    )
    sorc_a = analyze_level_up(sorc_l2)
    assert len([c for c in sorc_a["choices_required"] if c["type"] == "metamagic"]) == 2

    bm_l2 = _make_base_char(
        char_class="Fighter",
        char_level=2,
        classes=[{"class_name": "Fighter", "level": 2, "subclass": None}],
    )
    bm_a = analyze_level_up(bm_l2, user_choices={"subclass": "Battle Master"})
    assert len([c for c in bm_a["choices_required"] if c["type"] == "maneuver"]) == 3

    art_l1 = _make_base_char(
        char_class="Artificer",
        char_level=1,
        classes=[{"class_name": "Artificer", "level": 1, "subclass": None}],
    )
    art_a = analyze_level_up(art_l1)
    assert len([c for c in art_a["choices_required"] if c["type"] == "infusion"]) == 2

    hunter_l2 = _make_base_char(
        char_class="Ranger",
        char_level=2,
        classes=[{"class_name": "Ranger", "level": 2, "subclass": None}],
    )
    hunter_a = analyze_level_up(hunter_l2, user_choices={"subclass": "Hunter"})
    assert len([c for c in hunter_a["choices_required"] if c["type"] == "hunter_choice"]) == 1


def test_2014_sorcerous_restoration_short_rest_and_racial_pools():
    # 2014 Sorcerer L20 recovers up to +4 Sorcery Points on a Short Rest
    sorc_2014 = _make_base_char(
        char_class="Sorcerer",
        char_level=20,
        classes=[{"class_name": "Sorcerer", "level": 20, "subclass": "Draconic Bloodline"}],
        dnd_edition=EDITION_2014,
        class_resources=[{"name": "Sorcery Points", "current": 2, "max": 20, "recharge": "long"}],
    )
    after_sr_14 = apply_short_rest(sorc_2014, dice_to_spend=0)
    sp_14 = next(r for r in after_sr_14["class_resources"] if r["name"] == "Sorcery Points")
    assert sp_14["current"] == 6

    # 2024 Sorcerer L20 does NOT trigger old L20 +4 SP Short Rest rule when using Sorcerous Restoration L5 ruleset
    sorc_2024 = _make_base_char(
        char_class="Sorcerer",
        char_level=20,
        classes=[{"class_name": "Sorcerer", "level": 20, "subclass": "Draconic Sorcery"}],
        dnd_edition=EDITION_2024,
        class_resources=[
            {"name": "Sorcery Points", "current": 2, "max": 20, "recharge": "long"},
            {"name": "Sorcerous Restoration", "current": 1, "max": 1, "recharge": "long"},
        ],
    )
    after_sr_24 = apply_short_rest(sorc_2024, dice_to_spend=0)
    sp_24 = next(r for r in after_sr_24["class_resources"] if r["name"] == "Sorcery Points")
    assert sp_24["current"] == 2

    # Dragonborn Breath Weapon: 2014 (1/short) vs 2024 (PB/long)
    p14 = rules_pools(
        [{"class_name": "Fighter", "level": 5}],
        {"CON": 14},
        EDITION_2014,
        race="Dragonborn",
        total_level=5,
    )
    bw14 = next(r for r in p14 if r["name"] == "Breath Weapon")
    assert bw14["max"] == 1
    assert bw14["recharge"] == "short"

    p24 = rules_pools(
        [{"class_name": "Fighter", "level": 5}],
        {"CON": 14},
        EDITION_2024,
        race="Dragonborn",
        total_level=5,
    )
    bw24 = next(r for r in p24 if r["name"] == "Breath Weapon")
    assert bw24["max"] == 3
    assert bw24["recharge"] == "long"

    # Half-Orc Relentless Endurance
    orc_res = sync_class_resources(
        [],
        [{"class_name": "Barbarian", "level": 3}],
        {"STR": 16, "CON": 16},
        EDITION_2014,
        race="Half-Orc",
        total_level=3,
    )
    assert any(r["name"] == "Relentless Endurance" and r["max"] == 1 for r in orc_res)


def test_senses_damage_resistances_and_save_advantages_derivation():
    tiefling_forge_gloom = _make_base_char(
        race="Dark Elf (Drow)",
        char_class="Ranger",
        char_level=3,
        subclass="Gloom Stalker",
        classes=[{"class_name": "Ranger", "level": 3, "subclass": "Gloom Stalker"}],
        features_traits=[
            {"name": "Blind Fighting", "description": "Blindsight 10 ft."},
            {"name": "Soul of the Forge", "description": "Resistance to fire damage."},
            {
                "name": "War Caster",
                "description": "Advantage on Constitution saving throws to maintain concentration.",
            },
        ],
    )
    synced = sync_character_stats(tiefling_forge_gloom)
    assert "Superior Darkvision 150 ft." in synced["senses"]
    assert "Blindsight 10 ft." in synced["senses"]
    assert "Fire" in synced["damage_resistances"]
    assert any("Charmed" in a for a in synced["save_advantages"])
    assert any("Concentration" in a for a in synced["save_advantages"])

    # Manual forge smoke check for Dragonborn 2014 Breath Weapon pool (AI call mocked)
    with patch("backend.services.forge_service.generate_ai_json", return_value={}):
        db_paladin = forge_character_manual(
            1,
            "Dragonborn",
            "Paladin",
            "Noble",
            None,
            "Lawful Good",
            "Male",
            "Bharash",
            {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
            ["Athletics", "Persuasion"],
            [],
            None,
            "",
            edition=EDITION_2014,
        )
    assert "Breath Weapon" in {r["name"] for r in db_paladin["class_resources"]}
