from auxiliary.base_data import PropData
import json
from typing import Dict

############################################################################################################
class BaseFile:

    def __init__(self, name: str, ownersname: str) -> None:
        self.name = name
        self.ownersname = ownersname

    def content(self) -> str:
        return "BaseFile"
############################################################################################################


############################################################################################################
## 表达一个道具，有这个档案说明你有这个道具
class PropFile(BaseFile):
    def __init__(self, name: str, ownersname: str, prop: PropData) -> None:
        super().__init__(name, ownersname)
        self.prop = prop
        assert self.prop._codename != ""

    def content(self) -> str:
        seri = self.prop.serialization()
        prop_json = json.dumps(seri, ensure_ascii = False)
        return prop_json
    
    def __str__(self) -> str:
        return f"{self.prop}"
############################################################################################################


############################################################################################################
## 表达一个Actor档案，有这个档案说明你认识这个Actor
class ActorArchiveFile(BaseFile):
    def __init__(self, name: str, ownersname: str, actorname: str, appearance: str) -> None:
        super().__init__(name, ownersname)
        self.actorname = actorname
        self.appearance = appearance

    def content(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self.actorname, self.appearance)
        return json.dumps(makedict, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self.actorname}"
############################################################################################################



############################################################################################################
## 表达一个Stage的档案，有这个档案说明你知道这个Stage
class StageArchiveFile(BaseFile):
    def __init__(self, name: str, ownersname: str, stagename: str) -> None:
        super().__init__(name, ownersname)
        self.stagename = stagename

    def content(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self.stagename,  f"Having this file means you know this stage")
        return json.dumps(makedict, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self.stagename}"
############################################################################################################