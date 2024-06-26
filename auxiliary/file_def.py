from overrides import override
from auxiliary.base_data import PropData
import json
from typing import Dict, Any
from abc import ABC, abstractmethod

############################################################################################################
############################################################################################################
############################################################################################################
class BaseFile(ABC):

    def __init__(self, name: str, ownersname: str) -> None:
        # 文件本身的名字，看具体需求
        self._name = name
        # 文件拥有者的名字
        self._ownersname = ownersname

    @abstractmethod
    def serialization(self) -> str:
        pass
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个道具.
class PropFile(BaseFile):
    def __init__(self, name: str, ownersname: str, prop: PropData, count: int) -> None:
        super().__init__(name, ownersname)
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
    
    def __str__(self) -> str:
        return f"{self._prop}"
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个Actor档案，有这个档案说明你认识这个Actor
class ActorArchiveFile(BaseFile):
    def __init__(self, name: str, ownersname: str, actorname: str, appearance: str) -> None:
        super().__init__(name, ownersname)
        self._actor_name = actorname
        self._appearance = appearance

    @override
    def serialization(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self._actor_name, self._appearance)
        return json.dumps(makedict, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self._actor_name}"
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个Stage的档案，有这个档案说明你知道这个Stage
class StageArchiveFile(BaseFile):
    def __init__(self, name: str, ownersname: str, stagename: str) -> None:
        super().__init__(name, ownersname)
        self._stage_name = stagename

    @override
    def serialization(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self._stage_name,  f"Having this file means you know this stage") #todo
        return json.dumps(makedict, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self._stage_name}"
############################################################################################################
############################################################################################################
############################################################################################################
## 表达一个一个角色的属性等信息的文件
class StatusProfileFile(BaseFile):
    def __init__(self, name: str, ownersname: str, data: Dict[str, Any]) -> None:
        super().__init__(name, ownersname)
        self._data: Dict[str, Any] = data

    @override
    def serialization(self) -> str:
        assert self._data is not None
        return json.dumps(self._data, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self._name}"
############################################################################################################
############################################################################################################
############################################################################################################



