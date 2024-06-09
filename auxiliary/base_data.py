from typing import List, Set, Dict, Any
#from auxiliary.format_of_complex_stage_entry_and_exit_conditions import is_complex_stage_condition
from enum import Enum
from loguru import logger


#
class PropType(Enum):
    INVALID = 0,
    ROLE_COMPONENT = 1
    WEAPON = 2
    CLOTHES = 3
    NON_CONSUMABLE_ITEM = 4
    #EVENT = 5

class PropData:

    def __init__(self, name: str, codename: str, description: str, is_unique: str, type: str, attributes: str) -> None:
        self._name = name
        self._codename = codename
        self._description = description
        self._is_unique = is_unique
        self._type = type
        self._attributes_string: str = attributes

        #默认值，如果不是武器或者衣服，就是0
        self._attributes: List[int] = [0, 0, 0]
        if attributes != "":
            #是武器或者衣服，就进行构建
            self._build_attributes(attributes)

    def isunique(self) -> bool:
        return self._is_unique.lower() == "yes"
    
    @property
    def e_type(self) -> PropType:
        if self.is_role_component():
            return PropType.ROLE_COMPONENT
        elif self.is_weapon():
            return PropType.WEAPON
        elif self.is_clothes():
            return PropType.CLOTHES
        elif self.is_non_consumable_item():
            return PropType.NON_CONSUMABLE_ITEM
        # elif self.is_event():
        #     self.em_type = PropType.EVENT
        return PropType.INVALID
    
    def is_role_component(self) -> bool:
        return self._type == "RoleComponent"
    
    def is_weapon(self) -> bool:
        return self._type == "Weapon"
    
    def is_clothes(self) -> bool:
        return self._type == "Clothes"
    
    def is_non_consumable_item(self) -> bool:
        return self._type == "NonConsumableItem"
    
    def reseialization(self, prop_data: Any) -> 'PropData':
        self._name = prop_data.get('name')
        self._codename = prop_data.get('codename')
        self._description = prop_data.get('description')
        self._is_unique = prop_data.get('is_unique')
        self._type = prop_data.get('type')
        self._build_attributes(prop_data.get('attributes'))
        return self

    def serialization(self) -> Dict[str, str]:
        return {
            "name": self._name,
            "codename": self._codename,
            "description": self._description,
            "is_unique": self._is_unique,
            "type": self._type,
            "attributes": ",".join([str(attr) for attr in self._attributes])
        }
    
    def __str__(self) -> str:
        return f"{self._name}"
    
    def _build_attributes(self, attributes_string: str) -> None:
        if attributes_string == "":
            return
        self._attributes = [int(attr) for attr in attributes_string.split(',')]
        assert len(self._attributes) == 3   

    @property
    def maxhp(self) -> int:
        return self._attributes[0]
    
    @property
    def attack(self) -> int:
        return self._attributes[1]
    
    @property
    def defense(self) -> int:
        return self._attributes[2]
    
def PropDataProxy(name: str) -> PropData:
    return PropData(name, "", "", "", "", "")
########################################################################################################################
########################################################################################################################
########################################################################################################################
class ActorData:
    def __init__(self, name: str, 
                 codename: str, 
                 url: str, 
                 memory: str, 
                 props: Set[PropData], 
                 mentioned_actors: Set[str], 
                 mentioned_stages: Set[str],
                 appearance: str) -> None:
        self.name = name
        self.codename = codename
        self.url = url
        self.memory = memory
        self.props: Set[PropData] = props
        self.actor_names_mentioned_during_editing_or_for_agent: Set[str] = mentioned_actors 
        self.stage_names_mentioned_during_editing_or_for_agent: Set[str] = mentioned_stages
        self.attributes: List[int] = []
        self._appearance: str = appearance

    def build_attributes(self, attributes: str) -> None:
        self.attributes = [int(attr) for attr in attributes.split(',')]
        assert len(self.attributes) == 4

def ActorDataProxy(name: str) -> ActorData:
    return ActorData(name, "", "", "", set(), set(), set(), "")
########################################################################################################################
########################################################################################################################
########################################################################################################################
class StageData:
    def __init__(self, name: str, 
                 codename: str, 
                 description: str, 
                 url: str, 
                 memory: str, 
                 foo1: Any, 
                 foo2: Any, 
                 actors: set[ActorData], 
                 props: set[PropData],
                 foo3: Any,
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
        # self.entry_conditions: list[StageConditionData] = entry_conditions
        # self.exit_conditions: list[StageConditionData] = exit_conditions
        self.actors: set[ActorData] = actors
        self.props: set[PropData] = props
        self.exit_of_portal: set[StageData] = set()
        self.attributes: List[int] = []
        #self.interactiveprops: str = interactiveprops

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
    return StageData(name, "", "", "", "", "", "", set(), set(), "", "", "", "", "", "", "")
########################################################################################################################
########################################################################################################################
########################################################################################################################





        