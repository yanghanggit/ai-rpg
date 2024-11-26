from typing import final
from overrides import override
from my_models.entity_models import (
    PropModel,
    PropInstanceModel,
)
from my_models.entity_models import Attributes
from my_models.file_models import (
    PropType,
    PropFileModel,
    PropTypeName,
)
from extended_systems.base_file import BaseFile
from loguru import logger


@final
class PropFile(BaseFile):

    def __init__(
        self,
        prop_file_model: PropFileModel,
    ) -> None:

        super().__init__(
            prop_file_model.prop_instance_model.name, prop_file_model.owner
        )
        self._model: PropFileModel = prop_file_model

    ############################################################################################################
    @override
    def serialization(self) -> str:
        return self._model.model_dump_json()

    ############################################################################################################
    @override
    def deserialization(self, content: str) -> None:
        self._model = PropFileModel.model_validate_json(content)
        self._name = self._model.prop_instance_model.name
        self._owner_name = self._model.owner

    ############################################################################################################
    @property
    def guid(self) -> int:
        return self.prop_instance_model.guid

    ############################################################################################################
    @property
    def prop_model(self) -> PropModel:
        return self._model.prop_model

    ############################################################################################################
    @property
    def prop_instance_model(self) -> PropInstanceModel:
        return self._model.prop_instance_model

    ############################################################################################################
    @property
    def details(self) -> str:
        return self.prop_model.details

    ############################################################################################################
    @property
    def appearance(self) -> str:
        return self.prop_model.appearance

    ############################################################################################################
    @property
    def insight(self) -> str:
        return self.prop_model.insight

    ############################################################################################################
    @property
    def is_special(self) -> bool:
        return self.prop_model.type == PropType.TYPE_SPECIAL

    ############################################################################################################
    @property
    def is_weapon(self) -> bool:
        return self.prop_model.type == PropType.TYPE_WEAPON

    ############################################################################################################
    @property
    def is_clothes(self) -> bool:
        return self.prop_model.type == PropType.TYPE_CLOTHES

    ############################################################################################################
    @property
    def is_non_consumable_item(self) -> bool:
        return self.prop_model.type == PropType.TYPE_NON_CONSUMABLE_ITEM

    ############################################################################################################
    @property
    def is_consumable_item(self) -> bool:
        return self.prop_model.type == PropType.TYPE_CONSUMABLE_ITEM

    ############################################################################################################
    @property
    def is_skill(self) -> bool:
        return self.prop_model.type == PropType.TYPE_SKILL

    ############################################################################################################
    @property
    def damage(self) -> int:
        return self.prop_model.attributes[Attributes.DAMAGE]

    ############################################################################################################
    @property
    def heal(self) -> int:
        return self.prop_model.attributes[Attributes.HEAL]

    ############################################################################################################
    @property
    def defense(self) -> int:
        return self.prop_model.attributes[Attributes.DEFENSE]

    ############################################################################################################
    @property
    def count(self) -> int:
        return self.prop_instance_model.count

    ############################################################################################################
    def consume(self, amount: int) -> None:
        if not self.is_consumable_item:
            logger.debug(f"道具:{self.name}不是消耗品, 减少数量就略过")
            return
        self.prop_instance_model.count -= amount
        if self.prop_instance_model.count < 0:
            self.prop_instance_model.count = 0

    ############################################################################################################


###############################################################################################################################################
def generate_prop_type_prompt(prop_file: PropFile) -> str:

    if prop_file.is_weapon:
        return PropTypeName.WEAPON
    elif prop_file.is_clothes:
        return PropTypeName.CLOTHES
    elif prop_file.is_non_consumable_item:
        return PropTypeName.NON_CONSUMABLE_ITEM
    elif prop_file.is_consumable_item:
        return PropTypeName.CONSUMABLE_ITEM
    elif prop_file.is_special:
        return PropTypeName.SPECIAL
    elif prop_file.is_skill:
        return PropTypeName.SKILL

    assert False, f"未知的道具类型:{prop_file.prop_model.type}"
    return PropTypeName.UNKNOWN


###############################################################################################################################################
def _determine_prop_appearance_tag(prop_file: PropFile) -> str:
    if prop_file.is_skill:
        return "技能表现"
    return "道具外观"


###############################################################################################################################################
# 所有信息全要, 一般是用于做核心决策的时候
def generate_prop_file_total_prompt(prop_file: PropFile) -> str:
    return f"""### {prop_file.name}
- 类型: {generate_prop_type_prompt(prop_file)}
- 数量: {prop_file.count}
- 攻击力: {prop_file.damage}
- 防御力: {prop_file.defense}
- 治疗量: {prop_file.heal}
道具描述: 
{prop_file.details}
{_determine_prop_appearance_tag(prop_file)}: 
{prop_file.appearance}"""


###############################################################################################################################################
# 只要技能相关的信息，技能系统过程中需要
def generate_skill_prop_file_prompt(
    prop_file: PropFile, enable_insight_detail: bool
) -> str:
    assert prop_file.is_skill, "不是技能文件"
    return f"""### {prop_file.name}
- 类型: {generate_prop_type_prompt(prop_file)}
- 攻击力: {prop_file.damage}
- 防御力: {prop_file.defense}
- 治疗量: {prop_file.heal}
道具描述: 
{prop_file.details} {prop_file.insight if enable_insight_detail else ""}
{_determine_prop_appearance_tag(prop_file)}: 
{prop_file.appearance}"""


###############################################################################################################################################
# 只要技能配件相关的信息， 技能系统过程中需要
def generate_skill_accessory_prop_file_prompt(prop_file: PropFile) -> str:
    assert not prop_file.is_skill, "不是技能文件"
    return f"""### {prop_file.name}
- 类型: {generate_prop_type_prompt(prop_file)}
- 数量: {prop_file.count}
道具描述: 
{prop_file.details}"""


###############################################################################################################################################
# 只要外形相关的信息，观察场景时需要，还有输出场景描述时需要
def generate_prop_file_appearance_prompt(prop_file: PropFile) -> str:
    assert not prop_file.is_skill, "不是技能文件"
    return f"""### {prop_file.name}
- 类型: {generate_prop_type_prompt(prop_file)}
{_determine_prop_appearance_tag(prop_file)}: 
{prop_file.appearance}"""


###############################################################################################################################################
# 只要场景条件检查所需要的信息。
def generate_prop_file_for_stage_condition_prompt(prop_file: PropFile) -> str:
    assert not prop_file.is_skill, "不是技能文件"
    return f"""### {prop_file.name}
- 类型: {generate_prop_type_prompt(prop_file)}
道具描述: 
{prop_file.details}
{_determine_prop_appearance_tag(prop_file)}: 
{prop_file.appearance}"""


###############################################################################################################################################
