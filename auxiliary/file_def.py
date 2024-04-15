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

    def content(self) -> str:
        prop_json = json.dumps(self.prop.__dict__, ensure_ascii = False)
        return prop_json
    
    def __str__(self) -> str:
        return f"{self.prop}"
############################################################################################################
## 表达一个NPC档案，有这个档案说明你认识这个NPC
class KnownNPCFile(BaseFile):
    def __init__(self, name: str, ownersname: str, npcname: str) -> None:
        super().__init__(name, ownersname)
        self.npcsname = npcname

    def content(self) -> str:
        makedict: Dict[str, str] = {}
        makedict.setdefault(self.npcsname, f"Having this file means you know this NPC")
        return json.dumps(makedict, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self.npcsname}"
############################################################################################################
## 表达一个Stage的档案，有这个档案说明你知道这个Stage
class KnownStageFile(BaseFile):
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
