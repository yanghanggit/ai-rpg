from typing import Any, Optional, List, Dict
from loguru import logger
from prototype_data.data_def import WorldSystemData
from prototype_data.data_base_system import DataBaseSystem


class WorldSystemBuilder:
    
    """
    这是一个分析世界系统json的数据的类。
    """

    def __init__(self) -> None:
        self._raw_data: Optional[List[Dict[str, Any]]] = None
        self._world_systems: List[WorldSystemData] = []
###############################################################################################################################################
    def build(self, raw_data: Any, data_base_system: DataBaseSystem) -> 'WorldSystemBuilder':
        self._raw_data = raw_data
        if self._raw_data is None:
            logger.error("WorldSystemBuilder: data is None.")
            return self
        
        for _d in self._raw_data:
            _core_ = _d["world_system"]
            _name = _core_["name"]
            world_system_data = data_base_system.get_world_system(_name)
            if world_system_data is None:
                logger.error(f"WorldSystemBuilder: {_name} not found in database.")
                continue
     
            self._world_systems.append(world_system_data)

        return self
###############################################################################################################################################