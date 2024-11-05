from typing import List, Dict, List, Any
from pydantic import BaseModel
from enum import StrEnum, unique
from my_models.entity_models import PropInstanceModel, PropModel


@unique
class PropType(StrEnum):
    TYPE_SPECIAL = "Special"
    TYPE_WEAPON = "Weapon"
    TYPE_CLOTHES = "Clothes"
    TYPE_NON_CONSUMABLE_ITEM = "NonConsumableItem"
    TYPE_CONSUMABLE_ITEM = "ConsumableItem"
    TYPE_SKILL = "Skill"


class ComponentDumpModel(BaseModel):
    name: str
    data: Dict[str, Any]


class EntityProfileModel(BaseModel):
    name: str
    components: List[ComponentDumpModel]


class StageArchiveFileModel(BaseModel):
    name: str
    owner: str
    stage_narrate: str


class ActorArchiveFileModel(BaseModel):
    name: str
    owner: str
    appearance: str


class PropFileModel(BaseModel):
    owner: str
    prop_model: PropModel
    prop_proxy_model: PropInstanceModel
