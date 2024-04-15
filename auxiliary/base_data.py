##干净与基础的数据结构
from typing import List, Set, Any

class StageConditionData:
    def __init__(self, name: str, type: str, prop_name: str) -> None:
        self.name = name
        self.type = type
        self.prop_name = prop_name


class PropData:
    def __init__(self, name: str, codename: str, description: str, is_unique: str) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.is_unique = is_unique

    def isunique(self) -> bool:
        return self.is_unique == "Yes"
    
    def __str__(self) -> str:
        return f"{self.name}"

class NPCData:
    def __init__(self, name: str, 
                 codename: str, 
                 url: str, 
                 memory: str, 
                 props: Set[PropData], 
                 mentioned_npcs: Set[str], 
                 mentioned_stages: Set[str]) -> None:
        self.name = name
        self.codename = codename
        self.url = url
        self.memory = memory
        self.props: Set[PropData] = props
        self.mentioned_npcs: Set[str] = mentioned_npcs
        self.mentioned_stages: Set[str] = mentioned_stages

class StageData:
    def __init__(self, name: str, 
                 codename: str, 
                 description: str, 
                 url: str, 
                 memory: str, 
                 entry_conditions: list[StageConditionData], 
                 exit_conditions: list[StageConditionData], 
                 npcs: set[NPCData], 
                 props: set[PropData]) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.url = url
        self.memory = memory
        self.entry_conditions: list[StageConditionData] = entry_conditions
        self.exit_conditions: list[StageConditionData] = exit_conditions
        self.npcs: set[NPCData] = npcs
        self.props: set[PropData] = props
        self.connect_to_stage: set[StageData] = set()

    ###
    def connectstage(self, stage: 'StageData') -> None:
        self.connect_to_stage.add(stage)





        