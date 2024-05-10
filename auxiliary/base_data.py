##干净与基础的数据结构
from typing import List, Set
from auxiliary.format_of_complex_stage_entry_and_exit_conditions import is_complex_stage_condition

class StageConditionData:
    
    #
    def __init__(self, name: str, type: str, prop_name: str) -> None:
        self.name = name
        self.type = type
        self.prop_name = prop_name
        self.complexconditions: str = ""

        # 分析是否是复杂条件
        if is_complex_stage_condition(prop_name):
            self.complexconditions = str(prop_name)

    #
    # def analyze_is_complex_condition(self, propname: str) -> bool:
    #     #下面是例子：输入 = “(内容A|内容B)” 。如果输入符合这种格式，那么就是复杂条件。否则就不是
    #     return propname.startswith("(") and propname.endswith(")") and "|" in propname

    # 默认是给名字
    def condition(self) -> str:
        if self.complexconditions != "":
            return self.complexconditions
        return self.prop_name

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
                 mentioned_stages: Set[str],
                 roleappearance: str) -> None:
        self.name = name
        self.codename = codename
        self.url = url
        self.memory = memory
        self.props: Set[PropData] = props
        self.npc_names_mentioned_during_editing_or_for_agent: Set[str] = mentioned_npcs 
        self.stage_names_mentioned_during_editing_or_for_agent: Set[str] = mentioned_stages
        self.attributes: List[int] = []
        self.role_appearance: str = roleappearance

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
                 props: set[PropData],
                 interactiveprops: str) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.url = url
        self.memory = memory
        self.entry_conditions: list[StageConditionData] = entry_conditions
        self.exit_conditions: list[StageConditionData] = exit_conditions
        self.npcs: set[NPCData] = npcs
        self.props: set[PropData] = props
        self.exit_of_prison: set[StageData] = set()
        self.attributes: List[int] = []
        self.interactiveprops: str = interactiveprops

    ###
    def stage_as_exit_of_prison(self, stagename: str) -> None:
        stage_only_has_name = StageData(stagename, "", "", "", "", [], [], set(), set(), "")
        self.exit_of_prison.add(stage_only_has_name)

    ###
    def buildattributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]





        