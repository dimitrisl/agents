from typing import List, Dict, Optional
from pydantic import BaseModel, Field, field_validator


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
    damage: str
    range: Optional[str] = None
    properties: Optional[str] = None


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
