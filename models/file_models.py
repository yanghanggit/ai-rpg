from typing import List, Dict, List, Any
from overrides import final
from pydantic import BaseModel
from enum import StrEnum, unique
from models.entity_models import PropInstanceModel, PropModel


@unique
class PropType(StrEnum):
    TYPE_SPECIAL = "Special"
    TYPE_WEAPON = "Weapon"
    TYPE_CLOTHES = "Clothes"
    TYPE_NON_CONSUMABLE_ITEM = "NonConsumableItem"
    TYPE_CONSUMABLE_ITEM = "ConsumableItem"
    TYPE_SKILL = "Skill"


@final
class ComponentDumpModel(BaseModel):
    name: str
    data: Dict[str, Any]


@final
class EntityProfileModel(BaseModel):
    name: str
    components: List[ComponentDumpModel]


@final
class StageArchiveFileModel(BaseModel):
    name: str
    owner: str
    stage_narrate: str
    stage_tags: List[str]


@final
class ActorArchiveFileModel(BaseModel):
    name: str
    owner: str
    appearance: str


@final
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
class PropSkillUsageMode(StrEnum):
    CASTER_TAG = "<技能施放者>"
    SINGLE_TARGET_TAG = "<单个目标>"
    MULTI_TARGETS_TAG = "<多个目标>"
