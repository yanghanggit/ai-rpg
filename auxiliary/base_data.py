from typing import List, Set, Dict
from auxiliary.format_of_complex_stage_entry_and_exit_conditions import is_complex_stage_condition
from enum import Enum
from loguru import logger


########################################################################################################################
########################################################################################################################
########################################################################################################################
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

    # 默认是给名字
    def condition(self) -> str:
        if self.complexconditions != "":
            return self.complexconditions
        return self.prop_name
########################################################################################################################
########################################################################################################################
########################################################################################################################
#
class PropType(Enum):
    INVALID = 0,
    ROLE_COMPONENT = 1
    WEAPON = 2
    CLOTHES = 3
    NON_CONSUMABLE_ITEM = 4
    EVENT = 5

class PropData:
    def __init__(self, name: str, codename: str, description: str, is_unique: str, type: str, attributes: str) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.is_unique = is_unique


        self.type = type
        self.em_type = PropType.INVALID
        self.parse_type()
        #print(f"PropData: {self.name} {self.em_type}")

        #默认值，如果不是武器或者衣服，就是0
        self.attributes: List[int] = [0, 0, 0]
        if attributes != "":
            #是武器或者衣服，就进行构建
            self.build_attributes(attributes)

    def isunique(self) -> bool:
        return self.is_unique == "Yes"
    
    def parse_type(self) -> None:
        if self.is_role_component():
            self.em_type = PropType.ROLE_COMPONENT
        elif self.is_weapon():
            self.em_type = PropType.WEAPON
        elif self.is_clothes():
            self.em_type = PropType.CLOTHES
        elif self.is_non_consumable_item():
            self.em_type = PropType.NON_CONSUMABLE_ITEM
        elif self.is_event():
            self.em_type = PropType.EVENT
        else:
            self.em_type = PropType.INVALID
    
    def is_role_component(self) -> bool:
        return self.type == "RoleComponent"
    
    def is_weapon(self) -> bool:
        return self.type == "Weapon"
    
    def is_clothes(self) -> bool:
        return self.type == "Clothes"
    
    def is_non_consumable_item(self) -> bool:
        return self.type == "NonConsumableItem"
    
    def is_event(self) -> bool:
        return self.type == "Event"
    
    def serialization(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "codename": self.codename,
            "description": self.description,
            "is_unique": self.is_unique,
            "type": self.type
        }
    
    def __str__(self) -> str:
        return f"{self.name}"
    
    def build_attributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]
        assert len(self.attributes) == 3

    @property
    def maxhp(self) -> int:
        return self.attributes[0]
    
    @property
    def attack(self) -> int:
        return self.attributes[1]
    
    @property
    def defense(self) -> int:
        return self.attributes[2]
    
def PropDataProxy(name: str) -> PropData:
    #logger.info(f"PropDataProxy: {name}")
    return PropData(name, "", "", "", "", "")
########################################################################################################################
########################################################################################################################
########################################################################################################################
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

    def build_attributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]
        assert len(self.attributes) == 4

def NPCDataProxy(name: str) -> NPCData:
    #logger.info(f"NPCDataProxy: {name}")
    return NPCData(name, "", "", "", set(), set(), set(), "")
########################################################################################################################
########################################################################################################################
########################################################################################################################
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
                 interactiveprops: str,
        
                 stage_entry_status: str,
                 stage_entry_role_status: str,
                 stage_entry_role_props: str,
                 stage_exit_status: str,
                 stage_exit_role_status: str,
                 stage_exit_role_props: str
                 ) -> None:
        
        
        
        
        
        
        self.name = name
        self.codename = codename
        self.description = description
        self.url = url
        self.memory = memory
        self.entry_conditions: list[StageConditionData] = entry_conditions
        self.exit_conditions: list[StageConditionData] = exit_conditions
        self.npcs: set[NPCData] = npcs
        self.props: set[PropData] = props
        self.exit_of_portal: set[StageData] = set()
        self.attributes: List[int] = []
        self.interactiveprops: str = interactiveprops


        # 新的限制条件
        self.stage_entry_status: str = stage_entry_status
        self.stage_entry_role_status: str = stage_entry_role_status
        self.stage_entry_role_props: str = stage_entry_role_props
        self.stage_exit_status: str = stage_exit_status
        self.stage_exit_role_status: str = stage_exit_role_status
        self.stage_exit_role_props: str = stage_exit_role_props

    ###
    def stage_as_exit_of_portal(self, stagename: str) -> None:
        stage_proxy = StageDataProxy(stagename)
        self.exit_of_portal.add(stage_proxy)

    ###
    def build_attributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]


def StageDataProxy(name: str) -> StageData:
    #logger.info(f"StageDataProxy: {name}")
    return StageData(name, "", "", "", "", [], [], set(), set(), "", "", "", "", "", "", "")
########################################################################################################################
########################################################################################################################
########################################################################################################################





        