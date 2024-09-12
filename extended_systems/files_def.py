from overrides import override
import json
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from my_data.model_def import PropModel
from pathlib import Path
from loguru import logger
from my_data.model_def import AttributesIndex, PropType


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
        self, guid: int, name: str, owner_name: str, prop_model: PropModel, count: int
    ) -> None:

        super().__init__(name, owner_name)
        self._guid = guid
        self._prop_model: PropModel = prop_model
        self._count: int = count

    ############################################################################################################
    @override
    def serialization(self) -> str:
        output: Dict[str, Any] = {}
        output["guid"] = self._guid
        output["prop"] = self._prop_model.model_dump()
        output["count"] = self._count
        return json.dumps(output, ensure_ascii=False)

    ############################################################################################################
    @property
    def description(self) -> str:
        return self._prop_model.description

    ############################################################################################################
    @property
    def appearance(self) -> str:
        return self._prop_model.appearance

    ############################################################################################################
    @property
    def is_special(self) -> bool:
        return self._prop_model.type == PropType.TYPE_SPECIAL

    ############################################################################################################
    @property
    def is_weapon(self) -> bool:
        return self._prop_model.type == PropType.TYPE_WEAPON

    ############################################################################################################
    @property
    def is_clothes(self) -> bool:
        return self._prop_model.type == PropType.TYPE_CLOTHES

    ############################################################################################################
    @property
    def is_non_consumable_item(self) -> bool:
        return self._prop_model.type == PropType.TYPE_NON_CONSUMABLE_ITEM

    ############################################################################################################
    @property
    def is_consumable_item(self) -> bool:
        return self._prop_model.type == PropType.TYPE_CONSUMABLE_ITEM

    ############################################################################################################
    @property
    def is_skill(self) -> bool:
        return self._prop_model.type == PropType.TYPE_SKILL

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
        return self._prop_model.attributes[AttributesIndex.MAX_HP.value]

    ############################################################################################################
    @property
    def hp(self) -> int:
        return self._prop_model.attributes[AttributesIndex.CUR_HP.value]

    ############################################################################################################
    @property
    def attack(self) -> int:
        return self._prop_model.attributes[AttributesIndex.DAMAGE.value]

    ############################################################################################################
    @property
    def defense(self) -> int:
        return self._prop_model.attributes[AttributesIndex.DEFENSE.value]


############################################################################################################
############################################################################################################
############################################################################################################
class ActorArchiveFile(BaseFile):
    def __init__(
        self, name: str, owner_name: str, actor_name: str, appearance: str
    ) -> None:
        super().__init__(name, owner_name)
        self._actor_name = actor_name
        self._appearance = appearance

    @override
    def serialization(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self._actor_name, self._appearance)
        return json.dumps(makedict, ensure_ascii=False)


############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个Stage的档案，有这个档案说明你知道这个Stage
class StageArchiveFile(BaseFile):
    def __init__(self, name: str, owner_name: str, stage_name: str) -> None:
        super().__init__(name, owner_name)
        self._stage_name: str = stage_name
        self._stage_narrate: str = ""

    @override
    def serialization(self) -> str:
        seri: Dict[str, str] = {}
        seri.setdefault(self._stage_name, self._stage_narrate)  # todo
        return json.dumps(seri, ensure_ascii=False)


############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个一个角色的属性等信息的文件
class StatusProfileFile(BaseFile):
    def __init__(self, name: str, owner_name: str, data: Dict[str, Any]) -> None:
        super().__init__(name, owner_name)
        self._data: Dict[str, Any] = data

    @override
    def serialization(self) -> str:
        assert self._data is not None
        return json.dumps(self._data, ensure_ascii=False)


############################################################################################################
############################################################################################################
############################################################################################################
## 场景与场景中的角色的映射文件。
class StageActorsMapFile(BaseFile):
    def __init__(self, data: Dict[str, List[str]]) -> None:
        super().__init__("", "")
        self._data: Dict[str, List[str]] = data

    @override
    def serialization(self) -> str:
        assert self._data is not None
        return json.dumps(self._data, ensure_ascii=False)


############################################################################################################
############################################################################################################
############################################################################################################
