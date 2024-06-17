from typing import List, Set, Dict, Any
from enum import Enum
from loguru import logger

########################################################################################################################
########################################################################################################################
########################################################################################################################
class PropType(Enum):
    INVALID = 0,
    SPECIAL_COMPONENT = 1
    WEAPON = 2
    CLOTHES = 3
    NON_CONSUMABLE_ITEM = 4
########################################################################################################################
########################################################################################################################
########################################################################################################################
class Attributes:

    _attributes: List[int] = []

    def __init__(self, raw_string_val: str) -> None:
        if raw_string_val != "":
            assert ',' in raw_string_val, f"raw_string_val: {raw_string_val} is not valid."
            self._attributes = [int(attr) for attr in raw_string_val.split(',')]        

    def get_value(self, index: int) -> int:
        if index >= len(self._attributes):
            logger.error(f"index: {index} is out of range.")
            return 0
        return self._attributes[index]
    
    def serialization(self) -> str:
        return ",".join([str(attr) for attr in self._attributes])
    
    def length(self) -> int:
        return len(self._attributes)
########################################################################################################################
########################################################################################################################
########################################################################################################################
class PropData:

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 description: str, 
                 is_unique: str, 
                 type: str, 
                 attr: Attributes) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._is_unique: str = is_unique
        self._type: str = type
        self._attributes: Attributes = attr
        if self._attributes.length() > 0:
            assert self._attributes.length() == 3

    def isunique(self) -> bool:
        return self._is_unique.lower() == "yes"
    
    @property
    def e_type(self) -> PropType:
        if self.is_special_component():
            return PropType.SPECIAL_COMPONENT
        elif self.is_weapon():
            return PropType.WEAPON
        elif self.is_clothes():
            return PropType.CLOTHES
        elif self.is_non_consumable_item():
            return PropType.NON_CONSUMABLE_ITEM
        else:
            assert False, f"Invalid prop type: {self._type}"
        return PropType.INVALID
    
    def is_special_component(self) -> bool:
        return self._type == "SpecialComponent"
    
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
        self._attributes = Attributes(prop_data.get('attributes'))
        return self

    def serialization(self) -> Dict[str, str]:
        return {
            "name": self._name,
            "codename": self._codename,
            "description": self._description,
            "is_unique": self._is_unique,
            "type": self._type,
            "attributes": self._attributes.serialization()
        }
    
    def __str__(self) -> str:
        return f"{self._name}"
    
    @property
    def maxhp(self) -> int:
        return self._attributes.get_value(0)
    
    @property
    def attack(self) -> int:
        return self._attributes.get_value(1)
    
    @property
    def defense(self) -> int:
        return self._attributes.get_value(2)
    
def PropDataProxy(name: str) -> PropData:
    return PropData(name, "", "", "", "", Attributes(""))
########################################################################################################################
########################################################################################################################
########################################################################################################################
class ActorData:
    def __init__(self, 
                 name: str, 
                 codename: str, 
                 url: str, 
                 kick_off_memory: str, 
                 props: Set[PropData], 
                 mentioned_actors: Set[str], 
                 mentioned_stages: Set[str],
                 appearance: str,
                 body: str,
                 attr: Attributes) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._url: str = url
        self._kick_off_memory: str = kick_off_memory
        self._props: Set[PropData] = props
        self._actor_names_mentioned_during_editing_or_for_agent: Set[str] = mentioned_actors 
        self._stage_names_mentioned_during_editing_or_for_agent: Set[str] = mentioned_stages
        self._attributes: Attributes = attr
        if self._attributes.length() > 0:
            assert self._attributes.length() == 4
        self._appearance: str = appearance
        self._body: str = body

    @property
    def maxhp(self) -> int:
        return self._attributes.get_value(0)
    
    @property
    def hp(self) -> int:
        return self._attributes.get_value(1)
    
    @property
    def attack(self) -> int:
        return self._attributes.get_value(2)
    
    @property
    def defense(self) -> int:
        return self._attributes.get_value(3)

def ActorDataProxy(name: str) -> ActorData:
    return ActorData(name, "", "", "", set(), set(), set(), "", "", Attributes(""))
########################################################################################################################
########################################################################################################################
########################################################################################################################
class StageData:
    def __init__(self, 
                 name: str, 
                 codename: str, 
                 description: str, 
                 url: str, 
                 kick_off_memory: str, 
                 actors: Set[ActorData], 
                 props: Set[PropData],
                 stage_entry_status: str,
                 stage_entry_actor_status: str,
                 stage_entry_actor_props: str,
                 stage_exit_status: str,
                 stage_exit_actor_status: str,
                 stage_exit_actor_props: str,
                 attr: Attributes
                 ) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._url: str = url
        self._kick_off_memory: str = kick_off_memory
        self._actors: Set[ActorData] = actors
        self._props: Set[PropData] = props
        self._exit_of_portal: Set[StageData] = set()
        self._attributes: Attributes = attr
        if self._attributes.length() > 0:
            assert self._attributes.length() == 4

        # 新的限制条件
        self._stage_entry_status: str = stage_entry_status
        self._stage_entry_actor_status: str = stage_entry_actor_status
        self._stage_entry_actor_props: str = stage_entry_actor_props
        self._stage_exit_status: str = stage_exit_status
        self._stage_exit_actor_status: str = stage_exit_actor_status
        self._stage_exit_actor_props: str = stage_exit_actor_props

    ###
    def stage_as_exit_of_portal(self, stagename: str) -> None:
        stage_proxy = StageDataProxy(stagename)
        self._exit_of_portal.add(stage_proxy)

    @property
    def maxhp(self) -> int:
        return self._attributes.get_value(0)
    
    @property
    def hp(self) -> int:
        return self._attributes.get_value(1)
    
    @property
    def attack(self) -> int:
        return self._attributes.get_value(2)
    
    @property
    def defense(self) -> int:
        return self._attributes.get_value(3)

def StageDataProxy(name: str) -> StageData:
    return StageData(name, "", "", "", "", set(), set(), "", "", "", "", "", "", Attributes(""))
########################################################################################################################
########################################################################################################################
########################################################################################################################
class WorldSystemData:

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 url: str) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._url: str = url
       

def WorldSystemDataProxy(name: str) -> WorldSystemData:
    return WorldSystemData(name, "", "")
########################################################################################################################
########################################################################################################################
########################################################################################################################


        