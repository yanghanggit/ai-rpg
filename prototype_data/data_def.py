from typing import List, Set, Dict, Any
from loguru import logger

########################################################################################################################
########################################################################################################################
########################################################################################################################
class Attributes:

    def __init__(self, org_string: str) -> None:
        self._org_string: str = org_string
        self._attributes: List[int] = []
        self.reseialization(self._org_string)

    def get_value(self, index: int) -> int:
        if index >= len(self._attributes):
            return 0
        return self._attributes[index]
    
    def serialization(self) -> str:
        return ",".join([str(attr) for attr in self._attributes])
    
    def reseialization(self, data: Any) -> 'Attributes':
        # 会对自身产生影响
        self._attributes.clear()

        if not isinstance(data, str):
            logger.error(f"Attributes: {data} is not a string.")
            return self
        
        if data == "":
            return self

        assert ',' in data, f"raw_string_val: {data} is not valid."
        self._attributes = [int(attr) for attr in data.split(',')]        
        return self
    
    def length(self) -> int:
        return len(self._attributes)
########################################################################################################################
########################################################################################################################
########################################################################################################################
class PropData:

    @staticmethod
    def create_proxy(name: str) -> 'PropData':
        return PropData(name, "", "", "", "", Attributes(""), "")

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 description: str, 
                 is_unique: str, 
                 type: str, 
                 attr: Attributes, 
                 appearance: str) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._is_unique: str = is_unique
        self._type: str = type
        self._attributes: Attributes = attr
        if self._attributes.length() > 0:
            assert self._attributes.length() == 3
        self._appearance: str = appearance

    def is_unique(self) -> bool:
        return self._is_unique.lower() == "yes" or self._is_unique.lower() == "true"
    
    def is_special_component(self) -> bool:
        return self._type == "SpecialComponent"
    
    def is_weapon(self) -> bool:
        return self._type == "Weapon"
    
    def is_clothes(self) -> bool:
        return self._type == "Clothes"
    
    def is_non_consumable_item(self) -> bool:
        return self._type == "NonConsumableItem"
    
    def reseialization(self, data: Any) -> 'PropData':
        self._name = data['name']
        self._codename = data['codename']
        self._description = data['description']
        self._is_unique = data['is_unique']
        self._type = data['type']
        self._attributes = Attributes(data['attributes'])
        self._appearance = data['appearance']
        return self

    def serialization(self) -> Dict[str, str]:
        return {
            "name": self._name,
            "codename": self._codename,
            "description": self._description,
            "is_unique": self._is_unique,
            "type": self._type,
            "attributes": self._attributes.serialization(),
            "appearance": self._appearance
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
########################################################################################################################
########################################################################################################################
########################################################################################################################
class ActorData:

    @staticmethod
    def create_proxy(name: str) -> 'ActorData':
        return ActorData(name, "", "", "", set(), set(), "", "", Attributes(""))
    
    def __init__(self, 
                 name: str, 
                 codename: str, 
                 url: str, 
                 kick_off_memory: str, 
                 actor_archives: Set[str], 
                 stage_archives: Set[str],
                 appearance: str,
                 body: str,
                 attr: Attributes) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._url: str = url
        self._kick_off_memory: str = kick_off_memory
        self._props: List[tuple[PropData, int]] = []
        self._actor_archives: Set[str] = actor_archives 
        self._stage_archives: Set[str] = stage_archives
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
########################################################################################################################
########################################################################################################################
########################################################################################################################
class StageData:

    @staticmethod
    def create_proxy(name: str) -> 'StageData':
        return StageData(name, "", "", "", "", "", "", "", "", "", "", Attributes(""))

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 description: str, 
                 url: str, 
                 kick_off_memory: str, 
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
        self._actors: Set[ActorData] = set()
        self._props: List[tuple[PropData, int]] = []
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
        stage_proxy = StageData.create_proxy(stagename)
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
########################################################################################################################
########################################################################################################################
########################################################################################################################
class WorldSystemData:


    @staticmethod
    def create_proxy(name: str) -> 'WorldSystemData':
        return WorldSystemData(name, "", "")

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 url: str) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._url: str = url
########################################################################################################################
########################################################################################################################
########################################################################################################################


        