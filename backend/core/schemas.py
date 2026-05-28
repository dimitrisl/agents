from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class StatBlock(BaseModel):
    STR: int = 10
    DEX: int = 10
    CON: int = 10
    INT: int = 10
    WIS: int = 10
    CHA: int = 10


class Weapon(BaseModel):
    name: str
    attack_bonus: str
    damage_dice: str = ""
    damage_bonus: str = "+0"
    range: Optional[str] = None
    properties: Optional[str] = None
    is_custom: bool = False
    magic_bonus: int = 0
    ability_modifier: Optional[str] = None  # Explicit scaling stat (e.g., 'STR', 'DEX')
    damage: Optional[str] = None  # Added for legacy support/internal formula storage

    @classmethod
    def normalize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps UI labels to backend field names and provides defaults."""
        field_map = {
            "Weapon Name": "name",
            "To Hit": "attack_bonus",
            "Damage Dice": "damage_dice",
            "Dmg Bonus": "damage_bonus",
            "Custom": "is_custom",
            "Properties": "properties",
            "Range": "range",
            "+X": "magic_bonus",
        }
        normalized = {}
        for k, v in data.items():
            normalized[field_map.get(k, k)] = v

        # Ensure core combat fields trigger is_custom if they don't look standard
        # (This logic is moved from mechanics_service to here)
        if not normalized.get("is_custom"):
            import re

            atk = str(normalized.get("attack_bonus", "+0")).replace(" ", "")
            dmg_b = str(normalized.get("damage_bonus", "+0")).replace(" ", "")

            # If any core combat field was edited, we often want to lock it
            core_combat_fields = {
                "attack_bonus",
                "damage_dice",
                "damage_bonus",
                "damage",
            }
            if any(k in core_combat_fields for k in normalized):
                if (
                    not re.match(r"^[+-]?\d+$", atk)
                    or not re.match(r"^[+-]?\d+$", dmg_b)
                    or "damage" in normalized
                ):
                    normalized["is_custom"] = True
                elif normalized.get("attack_bonus") not in [None, "+0", "0", 0]:
                    normalized["is_custom"] = True

        return normalized

    @model_validator(mode="before")
    @classmethod
    def parse_damage_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Apply normalization first if it looks like UI data
            if any(k in data for k in ["Weapon Name", "To Hit", "Dmg Bonus"]):
                data = cls.normalize_dict(data)

            dmg = data.get("damage")
            if dmg and not data.get("damage_dice"):
                import re

                dice_match = re.match(r"^\s*(\d*d\d+)", str(dmg), re.I)
                if dice_match:
                    dice_part = dice_match.group(1)
                    type_match = re.search(r"([a-zA-Z][a-zA-Z\s]*)$", str(dmg))
                    dmg_type = type_match.group(1).strip() if type_match else ""
                    data["damage_dice"] = f"{dice_part} {dmg_type}".strip()

                    bonus_match = re.search(r"([+-]\s*\d+)", str(dmg))
                    if bonus_match:
                        data["damage_bonus"] = bonus_match.group(1).replace(" ", "")
                    else:
                        data["damage_bonus"] = "+0"
        return data


class EquipmentItem(BaseModel):
    name: str
    equipped: bool = False
    attuned: bool = False
    ac_bonus: int = 0
    mod1: str = "None"
    val1: int = 0
    mod2: str = "None"
    val2: int = 0


class FeatureTrait(BaseModel):
    name: str
    description: str
    source: Optional[str] = None


class Advancement(BaseModel):
    level: int
    type: str  # Feat, Origin Feat, ASI
    name: str
    description: str


class SpellList(BaseModel):
    cantrips: List[str] = []
    level_1: List[str] = []
    level_2: List[str] = []
    level_3: List[str] = []
    level_4: List[str] = []
    level_5: List[str] = []
    level_6: List[str] = []
    level_7: List[str] = []
    level_8: List[str] = []
    level_9: List[str] = []

    @model_validator(mode="before")
    @classmethod
    def clean_spell_lists(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        cleaned = {}
        levels = [f"level_{i}" for i in range(1, 10)] + ["cantrips"]
        for lvl in levels:
            val = data.get(lvl)
            if val is None or not isinstance(val, list):
                cleaned[lvl] = []
            else:
                clean_lvl = []
                for item in val:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("spell_name")
                        if name:
                            clean_lvl.append(str(name))
                    elif item is not None:
                        clean_lvl.append(str(item))
                cleaned[lvl] = clean_lvl
        return cleaned


class CharacterSchema(BaseModel):
    char_id: Optional[str] = None
    char_name: str
    gender: Optional[str] = "Unknown"
    char_class: str
    subclass: Optional[str] = None
    char_level: int = 1
    race: str
    background: str
    alignment: Optional[str] = "Neutral"
    backstory: Optional[str] = ""
    armor_class: int = 10
    hp_max: int = 10
    hp_current: Optional[int] = None
    hit_dice_used: int = 0
    speed: int = 30
    proficiency_bonus: int = 2
    stats: StatBlock
    saving_throws: List[str] = []
    skills: Dict[str, int] = {}
    skill_proficiencies: List[str] = []
    skill_expertise: List[str] = []
    weapon_masteries: List[str] = []
    weapons: List[Weapon] = []
    equipment: List[EquipmentItem] = []
    features_traits: List[FeatureTrait] = []
    spells: SpellList = Field(default_factory=SpellList)
    prepared_spells: List[str] = []
    spell_slots: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    concentrating_on: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    spell_ability: Optional[str] = None
    spell_save_dc: Optional[int] = None
    spell_attack_bonus: Optional[str] = None
    hit_dice: Optional[str] = ""
    passive_perception: int = 10
    saving_throw_values: Dict[str, int] = {}
    initiative_modifier: int = 0
    advancements: List[Advancement] = []
    personality_traits: Optional[str] = ""
    ideals: Optional[str] = ""
    bonds: Optional[str] = ""
    flaws: Optional[str] = ""
    languages: List[str] = []
    tool_proficiencies: List[str] = []
    char_portrait: Optional[str] = None
    playstyle_guide: Optional[str] = ""
    dnd_edition: str = "2014 Edition"
    active_campaign: Optional[str] = None

    @field_validator("equipment", mode="before")
    @classmethod
    def convert_strings_to_items(cls, v):
        if isinstance(v, list):
            return [{"name": item} if isinstance(item, str) else item for item in v]
        return v

    @field_validator("features_traits", mode="before")
    @classmethod
    def convert_strings_to_features(cls, v):
        if isinstance(v, list):
            return [
                {"name": item, "description": "Imported feature"}
                if isinstance(item, str)
                else item
                for item in v
            ]
        return v

    @model_validator(mode="before")
    @classmethod
    def sanitize_class_subclass_and_spells(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # 1. Base class and Subclass splitting
        char_class = data.get("char_class")
        subclass = data.get("subclass")
        if char_class and isinstance(char_class, str) and " " in char_class:
            parts = [p.strip() for p in char_class.split()]
            known_classes = {
                "barbarian",
                "bard",
                "cleric",
                "druid",
                "fighter",
                "monk",
                "paladin",
                "ranger",
                "rogue",
                "sorcerer",
                "warlock",
                "wizard",
                "artificer",
            }
            if parts[0].lower() in known_classes:
                data["char_class"] = parts[0]
                if not subclass:
                    data["subclass"] = " ".join(parts[1:])

        # 2. Spells type correction (e.g. from empty list or null to dict)
        spells = data.get("spells")
        if spells is not None and not isinstance(spells, dict):
            data["spells"] = {}

        return data


class MonsterEncounter(BaseModel):
    name: str
    hp: int
    ac: int
    dex: int = 10
    quantity: int = 1
    statblock_summary: str


class EncounterSchema(BaseModel):
    encounter_text: str
    monsters: List[MonsterEncounter] = []


class LevelUpChoice(BaseModel):
    type: str  # subclass|feat|spell|other
    label: str
    options: List[str] = []
    ai_recommendation: Optional[str] = None


class LevelUpAnalysisSchema(BaseModel):
    automatic_changes: List[FeatureTrait] = []
    hp_increase: int
    new_total_hp: int
    choices_required: List[LevelUpChoice] = []
    updated_proficiency_bonus: Optional[int] = None
    updated_spell_slots: Optional[Dict[str, int]] = None


class BuildValidationSchema(BaseModel):
    is_valid: bool
    issues: List[str] = []
    suggestions: List[str] = []
    corrections: Optional[Dict[str, Any]] = {}
