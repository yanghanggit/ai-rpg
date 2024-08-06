from overrides import override
from prototype_data.data_def import PropData
import json
from typing import Dict, Any, List
from abc import ABC, abstractmethod

############################################################################################################
############################################################################################################
############################################################################################################
class BaseFile(ABC):

    def __init__(self, name: str, owner_name: str) -> None:
        # 文件本身的名字，看具体需求
        self._name = name
        # 文件拥有者的名字
        self._owner_name = owner_name

    @abstractmethod
    def serialization(self) -> str:
        pass
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个道具.
class PropFile(BaseFile):
    def __init__(self, name: str, owner_name: str, prop: PropData, count: int) -> None:
        super().__init__(name, owner_name)
        self._prop = prop
        assert self._prop._codename != ""
        self._count = count

    @override
    def serialization(self) -> str:
        output: Dict[str, Any] = {}
        seri = self._prop.serialization()
        output["prop"] = seri
        output["count"] = self._count
        prop_json = json.dumps(output, ensure_ascii = False)
        return prop_json
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
