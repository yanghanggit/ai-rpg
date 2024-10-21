from overrides import override
import json
from abc import ABC, abstractmethod
from my_data.model_def import (
    PropModel,
    EntityProfileModel,
    StageArchiveFileModel,
    ActorArchiveFileModel,
    PropProxyModel,
)
from pathlib import Path
from loguru import logger
from my_data.model_def import AttributesIndex, PropType, PropFileModel


############################################################################################################
############################################################################################################
############################################################################################################
class BaseFile(ABC):

    def __init__(self, name: str, owner_name: str) -> None:
        self._name: str = name
        self._owner_name: str = owner_name

    ############################################################################################################
    @property
    def name(self) -> str:
        return self._name

    ############################################################################################################
    @property
    def owner_name(self) -> str:
        return self._owner_name

    ############################################################################################################
    @abstractmethod
    def serialization(self) -> str:
        pass

    ############################################################################################################
    @abstractmethod
    def deserialization(self, content: str) -> None:
        pass

    ############################################################################################################
    def write(self, write_path: Path) -> int:
        try:
            write_content = self.serialization()
            assert write_content != ""
            return write_path.write_text(write_content, encoding="utf-8")
        except Exception as e:
            logger.error(f"{self._name}, {self._owner_name} 写文件失败: {write_path}")
        return 0


############################################################################################################
############################################################################################################
############################################################################################################


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
    def prop_model(self) -> PropModel:
        return self._model.prop_model

    ############################################################################################################
    @property
    def prop_proxy_model(self) -> PropProxyModel:
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
    @property
    def guid(self) -> int:
        return self.prop_proxy_model.guid


############################################################################################################
############################################################################################################
############################################################################################################
class ActorArchiveFile(BaseFile):
    def __init__(
        self,
        model: ActorArchiveFileModel,
    ) -> None:
        super().__init__(model.name, model.owner)
        self._model = model

    @override
    def serialization(self) -> str:
        return json.dumps(self._model.model_dump(), ensure_ascii=False)

    @override
    def deserialization(self, content: str) -> None:
        self._model = ActorArchiveFileModel.model_validate_json(content)
        self._name = self._model.name
        self._owner_name = self._model.owner

    @property
    def appearance(self) -> str:
        return self._model.appearance

    def set_appearance(self, appearance: str) -> None:
        self._model.appearance = appearance

    def update(self, model: ActorArchiveFileModel) -> None:
        self._model = model
        self._name = model.name
        self._owner_name = model.owner


############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个Stage的档案，有这个档案说明你知道这个Stage
class StageArchiveFile(BaseFile):
    def __init__(self, model: StageArchiveFileModel) -> None:
        super().__init__(model.name, model.owner)
        self._model: StageArchiveFileModel = model

    @override
    def serialization(self) -> str:
        return json.dumps(self._model.model_dump(), ensure_ascii=False)

    @override
    def deserialization(self, content: str) -> None:
        self._model = StageArchiveFileModel.model_validate_json(content)
        self._name = self._model.name
        self._owner_name = self._model.owner

    @property
    def stage_narrate(self) -> str:
        return self._model.stage_narrate

    def set_stage_narrate(self, narrate: str) -> None:
        self._model.stage_narrate = narrate

    def update(self, model: StageArchiveFileModel) -> None:
        self._model = model
        self._name = model.name
        self._owner_name = model.owner


############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个一个角色的属性等信息的文件
class EntityProfileFile(BaseFile):
    def __init__(self, model: EntityProfileModel) -> None:
        super().__init__(model.name, model.name)
        self._model: EntityProfileModel = model

    @override
    def serialization(self) -> str:
        if self._model is None:
            return ""
        try:
            model_dump = self._model.model_dump()
            return json.dumps(model_dump, ensure_ascii=False)
        except Exception as e:
            logger.error(f"{e}")
        return ""

    @override
    def deserialization(self, content: str) -> None:
        self._model = EntityProfileModel.model_validate_json(content)
        self._name = self._model.name
        self._owner_name = self._model.name


############################################################################################################
############################################################################################################
############################################################################################################
