from overrides import override
import json
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from prototype_data.data_model import PropModel

############################################################################################################
############################################################################################################
############################################################################################################
class BaseFile(ABC):

    def __init__(self, name: str, owner_name: str) -> None:
        # 文件本身的名字，看具体需求
        self._name = name
        # 文件拥有者的名字
        self._owner_name = owner_name
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
############################################################################################################
############################################################################################################


## 表达一个道具.
class PropFile(BaseFile):

    TYPE_SPECIAL_COMPONENT = "SpecialComponent"
    TYPE_WEAPON = "Weapon"
    TYPE_CLOTHES = "Clothes"
    TYPE_NON_CONSUMABLE_ITEM = "NonConsumableItem"

    def __init__(self, name: str, owner_name: str, prop_model: PropModel, count: int) -> None:
        super().__init__(name, owner_name)
        self._prop_model: PropModel = prop_model
        assert self._name == self._prop_model.name
        assert self._prop_model.codename != ""
        assert len(self._prop_model.attributes) == 3
        self._count: int = count
############################################################################################################
    @override
    def serialization(self) -> str:
        output: Dict[str, Any] = {}
        output["prop"] = self._prop_model
        output["count"] = self._count
        prop_json = json.dumps(output, ensure_ascii = False)
        return prop_json
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
    def is_unique(self) -> bool:
        return self._prop_model.isunique.lower() == "yes" or self._prop_model.isunique.lower() == "true"
############################################################################################################
    @property
    def is_special_component(self) -> bool:
        assert PropFile.TYPE_SPECIAL_COMPONENT == "SpecialComponent"
        return self._prop_model.type == PropFile.TYPE_SPECIAL_COMPONENT
############################################################################################################
    @property
    def is_weapon(self) -> bool:
        assert PropFile.TYPE_WEAPON == "Weapon"
        return self._prop_model.type == PropFile.TYPE_WEAPON
############################################################################################################
    @property
    def is_clothes(self) -> bool:
        assert PropFile.TYPE_CLOTHES == "Clothes"
        return self._prop_model.type == PropFile.TYPE_CLOTHES
############################################################################################################
    @property
    def is_non_consumable_item(self) -> bool:
        assert PropFile.TYPE_NON_CONSUMABLE_ITEM == "NonConsumableItem"
        return self._prop_model.type == PropFile.TYPE_NON_CONSUMABLE_ITEM
############################################################################################################
    @property
    def max_hp(self) -> int:
        assert len(self._prop_model.attributes) == 3
        return self._prop_model.attributes[0]
############################################################################################################
    @property
    def attack(self) -> int:
        assert len(self._prop_model.attributes) == 3
        return self._prop_model.attributes[1]
############################################################################################################
    @property
    def defense(self) -> int:
        assert len(self._prop_model.attributes) == 3
        return self._prop_model.attributes[2]
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个Actor档案，有这个档案说明你认识这个Actor
class ActorArchiveFile(BaseFile):
    def __init__(self, name: str, owner_name: str, actor_name: str, appearance: str) -> None:
        super().__init__(name, owner_name)
        self._actor_name = actor_name
        self._appearance = appearance

    @override
    def serialization(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self._actor_name, self._appearance)
        return json.dumps(makedict, ensure_ascii = False)
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个Stage的档案，有这个档案说明你知道这个Stage
class StageArchiveFile(BaseFile):
    def __init__(self, name: str, owner_name: str, stage_name: str) -> None:
        super().__init__(name, owner_name)
        self._stage_name = stage_name

    @override
    def serialization(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self._stage_name,  f"Having this file means you know this stage") #todo
        return json.dumps(makedict, ensure_ascii = False)
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
        return json.dumps(self._data, ensure_ascii = False)
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
        return json.dumps(self._data, ensure_ascii = False)
############################################################################################################
############################################################################################################
############################################################################################################
