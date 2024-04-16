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
        self.attributes: List[int] = []

    def buildattributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]

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
        self.attributes: List[int] = []

    ###
    def connect_stage_by_name(self, stagename: str) -> None:
        stage_only_has_name = StageData(stagename, "", "", "", "", [], [], set(), set())
        self.connect_to_stage.add(stage_only_has_name)

    ###
    def buildattributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]





        