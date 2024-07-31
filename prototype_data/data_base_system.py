from typing import Optional, Dict, TypeVar, Generic
from prototype_data.data_def import ActorData, PropData, StageData, WorldSystemData

# 加限制不能超出这四种类型
PrototypeDataType = TypeVar('PrototypeDataType', ActorData, PropData, StageData, WorldSystemData) 

class MyDBSystem(Generic[PrototypeDataType]):

    """
    单独封装一下，方便使用。
    """
    def __init__(self) -> None:
        self._data: Dict[str, PrototypeDataType] = {}

    def add(self, name: str, data: PrototypeDataType) -> None:
        self._data.setdefault(name, data)
    
    def get(self, name: str) -> Optional[PrototypeDataType]:
        return self._data.get(name, None)
    
    def remove(self, name: str) -> None:
        self._data.pop(name, None)
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class DataBaseSystem:

    """
    将所有的数据存储在这里，以便于在游戏中使用。
    """

    def __init__(self) -> None:
        self._actors: MyDBSystem[ActorData] = MyDBSystem[ActorData]()
        self._stages: MyDBSystem[StageData] = MyDBSystem[StageData]()
        self._props: MyDBSystem[PropData] = MyDBSystem[PropData]()
        self._world_systems: MyDBSystem[WorldSystemData] = MyDBSystem[WorldSystemData]()
###############################################################################################################################################
    def add_actor(self, actor_name: str, actor_data: ActorData) -> None:
        self._actors.add(actor_name, actor_data)
###############################################################################################################################################
    def get_actor(self, actor_name: str) -> Optional[ActorData]:
        return self._actors.get(actor_name)
###############################################################################################################################################
    def add_stage(self, stage_name: str, stage_data: StageData) -> None:
        self._stages.add(stage_name, stage_data)
###############################################################################################################################################
    def get_stage(self, stage_name: str) -> Optional[StageData]:
        return self._stages.get(stage_name)
###############################################################################################################################################
    def add_prop(self, prop_name: str, prop_data: PropData) -> None:
        self._props.add(prop_name, prop_data)
###############################################################################################################################################
    def get_prop(self, prop_name: str) -> Optional[PropData]:
        return self._props.get(prop_name)
###############################################################################################################################################
    def add_world_system(self, world_system_name: str, world_system_data: WorldSystemData) -> None:
        self._world_systems.add(world_system_name, world_system_data)
###############################################################################################################################################
    def get_world_system(self, world_system_name: str) -> Optional[WorldSystemData]:
        return self._world_systems.get(world_system_name)
###############################################################################################################################################