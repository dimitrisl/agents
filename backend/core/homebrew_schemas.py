from builtins import int as BuiltinInt
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.schemas import EquipmentItem, FeatSchema, FeatureTrait, SpellSchema, Weapon


class HomebrewBase(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    campaign_id: str
    creator_dm_id: str
    name: str
    description: Optional[str] = ""


class HomebrewWeapon(HomebrewBase, Weapon):
    homebrew_type: Literal["weapon"] = "weapon"
    damage_type: Optional[str] = None


class HomebrewItem(HomebrewBase, EquipmentItem):
    homebrew_type: Literal["item"] = "item"


class HomebrewSpell(HomebrewBase, SpellSchema):
    homebrew_type: Literal["spell"] = "spell"


class HomebrewFeat(HomebrewBase, FeatSchema):
    homebrew_type: Literal["feat"] = "feat"


class HomebrewFeature(HomebrewBase, FeatureTrait):
    homebrew_type: Literal["feature"] = "feature"


class HomebrewMonster(HomebrewBase):
    homebrew_type: Literal["monster"] = "monster"
    size: str = "Medium"
    type: str = "humanoid"
    alignment: str = "unaligned"
    cr: Union[str, float, int] = "1"
    ac: int = 10
    hp: int = 10
    max_hp: Optional[int] = None
    speed: Union[str, Dict[str, Any]] = "30 ft."
    stats: Dict[str, int] = Field(
        default_factory=lambda: {
            "str": 10,
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }
    )
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    traits: List[Dict[str, Any]] = Field(default_factory=list)
    senses: Optional[str] = ""
    languages: Optional[str] = ""
    description: Optional[str] = ""


class MonsterStats(BaseModel):
    str: BuiltinInt = 10
    dex: BuiltinInt = 10
    con: BuiltinInt = 10
    int: BuiltinInt = 10
    wis: BuiltinInt = 10
    cha: BuiltinInt = 10


class MonsterActionEntry(BaseModel):
    name: str
    description: str = ""


class AIHomebrewWeapon(BaseModel):
    name: str
    attack_bonus: str = "+0"
    damage_dice: str = "1d8"
    damage_bonus: str = "+0"
    damage_type: Optional[str] = None
    range: Optional[str] = None
    properties: Optional[str] = None
    is_custom: bool = True
    magic_bonus: int = 0
    ability_modifier: Optional[str] = None
    damage: Optional[str] = None
    description: Optional[str] = ""


class AIHomebrewItem(BaseModel):
    name: str
    quantity: int = 1
    equipped: bool = False
    attuned: bool = False
    ac_bonus: int = 0
    mod1: str = "None"
    val1: int = 0
    mod2: str = "None"
    val2: int = 0
    description: Optional[str] = ""


class AIHomebrewSpell(BaseModel):
    name: str
    level: int = 1
    school: str = "Evocation"
    casting_time: Optional[str] = "1 action"
    range: Optional[str] = "60 feet"
    components: Optional[str] = "V, S"
    duration: Optional[str] = "Instantaneous"
    description: str = ""


class AIHomebrewFeat(BaseModel):
    name: str
    prerequisite: Optional[str] = None
    description: str = ""


class AIHomebrewFeature(BaseModel):
    name: str
    source: Optional[str] = "Homebrew"
    description: str = ""


class AIHomebrewMonster(BaseModel):
    name: str
    size: str = "Medium"
    type: str = "humanoid"
    alignment: str = "unaligned"
    cr: str = "1"
    ac: int = 10
    hp: int = 10
    max_hp: Optional[int] = None
    speed: str = "30 ft."
    stats: MonsterStats = Field(default_factory=MonsterStats)
    actions: List[MonsterActionEntry] = Field(default_factory=list)
    traits: List[MonsterActionEntry] = Field(default_factory=list)
    senses: Optional[str] = ""
    languages: Optional[str] = ""
    description: Optional[str] = ""


AI_HOMEBREW_SCHEMA_MAP = {
    "weapon": AIHomebrewWeapon,
    "item": AIHomebrewItem,
    "spell": AIHomebrewSpell,
    "feat": AIHomebrewFeat,
    "feature": AIHomebrewFeature,
    "monster": AIHomebrewMonster,
}


# Discriminated union for generic parsing
HomebrewEntity = Annotated[
    Union[
        HomebrewWeapon,
        HomebrewItem,
        HomebrewSpell,
        HomebrewFeat,
        HomebrewFeature,
        HomebrewMonster,
    ],
    Field(discriminator="homebrew_type"),
]


class HomebrewCreateRequest(BaseModel):
    type: Literal["weapon", "item", "spell", "feat", "feature", "monster"]
    prompt: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class HomebrewExportResponse(BaseModel):
    campaign_id: str
    items: List[Dict[str, Any]]


class HomebrewImportRequest(BaseModel):
    items: List[Dict[str, Any]]
