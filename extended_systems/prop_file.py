from typing import final
from overrides import override
import json
from my_models.entity_models import (
    PropModel,
    PropInstanceModel,
)
from my_models.entity_models import AttributesIndex
from my_models.file_models import (
    PropType,
    PropFileModel,
)
from extended_systems.base_file import BaseFile


@final
class PropFile(BaseFile):

    def __init__(
        self,
        prop_file_model: PropFileModel,
    ) -> None:

        super().__init__(prop_file_model.prop_proxy_model.name, prop_file_model.owner)
        self._model: PropFileModel = prop_file_model

    ############################################################################################################
    @override
    def serialization(self) -> str:
        return json.dumps(self._model.model_dump(), ensure_ascii=False)

    ############################################################################################################
    @override
    def deserialization(self, content: str) -> None:
        self._model = PropFileModel.model_validate_json(content)
        self._name = self._model.prop_proxy_model.name
        self._owner_name = self._model.owner

    ############################################################################################################
    @property
    def guid(self) -> int:
        return self.prop_proxy_model.guid

    ############################################################################################################
    @property
    def prop_model(self) -> PropModel:
        return self._model.prop_model

    ############################################################################################################
    @property
    def prop_proxy_model(self) -> PropInstanceModel:
        return self._model.prop_proxy_model

    ############################################################################################################
    @property
    def description(self) -> str:
        return self.prop_model.description

    ############################################################################################################
    @property
    def appearance(self) -> str:
        return self.prop_model.appearance

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
    def can_exchange(self) -> bool:
        return (
            self.is_weapon
            or self.is_clothes
            or self.is_non_consumable_item
            or self.is_consumable_item
        )

    ############################################################################################################
    @property
    def max_hp(self) -> int:
        return self.prop_model.attributes[AttributesIndex.MAX_HP.value]

    ############################################################################################################
    @property
    def hp(self) -> int:
        return self.prop_model.attributes[AttributesIndex.CUR_HP.value]

    ############################################################################################################
    @property
    def attack(self) -> int:
        return self.prop_model.attributes[AttributesIndex.DAMAGE.value]

    ############################################################################################################
    @property
    def defense(self) -> int:
        return self.prop_model.attributes[AttributesIndex.DEFENSE.value]

    ############################################################################################################
    @property
    def count(self) -> int:
        return self.prop_proxy_model.count

    ############################################################################################################
    def increase_count(self, amount: int) -> None:
        self.prop_proxy_model.count += amount

    ############################################################################################################
    def decrease_count(self, amount: int) -> None:
        self.prop_proxy_model.count -= amount
        if self.prop_proxy_model.count < 0:
            self.prop_proxy_model.count = 0

    ############################################################################################################


###############################################################################################################################################
def generate_prop_type_prompt(prop_file: PropFile) -> str:

    ret = "未知"

    if prop_file.is_weapon:
        ret = "武器"
    elif prop_file.is_clothes:
        ret = "衣服"
    elif prop_file.is_non_consumable_item:
        ret = "非消耗品"
    elif prop_file.is_special:
        ret = "特殊能力"
    elif prop_file.is_skill:
        ret = "技能"

    return ret


###############################################################################################################################################
def generate_prop_prompt(
    prop_file: PropFile,
    description_prompt: bool,
    appearance_prompt: bool,
    attr_prompt: bool = False,
) -> str:

    prompt = f"""### {prop_file.name}
- 类型:{generate_prop_type_prompt(prop_file)}"""

    if description_prompt:
        prompt += f"\n- 道具描述:{prop_file.description}"

    if appearance_prompt:
        prompt += f"\n- 道具外观:{prop_file.appearance}"

    if attr_prompt:
        prompt += f"\n- 攻击力:{prop_file.attack}\n- 防御力:{prop_file.defense}"

    return prompt


###############################################################################################################################################
