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


# Discriminated union for generic parsing
HomebrewEntity = Annotated[
    Union[HomebrewWeapon, HomebrewItem, HomebrewSpell, HomebrewFeat, HomebrewFeature],
    Field(discriminator="homebrew_type"),
]


class HomebrewCreateRequest(BaseModel):
    type: Literal["weapon", "item", "spell", "feat", "feature"]
    prompt: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class HomebrewExportResponse(BaseModel):
    campaign_id: str
    items: List[Dict[str, Any]]


class HomebrewImportRequest(BaseModel):
    items: List[Dict[str, Any]]
