from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.schemas import EquipmentItem, FeatSchema, FeatureTrait, SpellSchema, Weapon


class HomebrewBase(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    campaign_id: str
    creator_dm_id: str
    name: str


class HomebrewWeapon(HomebrewBase, Weapon):
    homebrew_type: Literal["weapon"] = "weapon"


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
