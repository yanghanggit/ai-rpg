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
    stage_tags: List[str]


class ActorArchiveFileModel(BaseModel):
    name: str
    owner: str
    appearance: str


class PropFileModel(BaseModel):
    owner: str
    prop_model: PropModel
    prop_instance_model: PropInstanceModel


@unique
class PropTypeName(StrEnum):
    SPECIAL = "特殊能力"
    WEAPON = "武器"
    CLOTHES = "衣服"
    NON_CONSUMABLE_ITEM = "非消耗品"
    CONSUMABLE_ITEM = "消耗品"
    SKILL = "技能"
    UNKNOWN = "未知"


@unique
class SkillUsageType(StrEnum):
    SINGLE_TARGET_SKILL_TAG = "<单体技能>"
    MULTI_TARGET_SKILL_TAG = "<群体技能>"
