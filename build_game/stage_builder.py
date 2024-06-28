from typing import Any, Optional, List, Set, Dict
from loguru import logger
from prototype_data.data_def import PropData, ActorData, StageData, ActorDataProxy, PropDataProxy
from prototype_data.data_base_system import DataBaseSystem

class StageBuilder:
    
    """
    这是一个分析场景json的数据的类。
    """

    def __init__(self) -> None:
        self._raw_data: Optional[Dict[str, Any]] = None
        self._stages: List[StageData] = []
###############################################################################################################################################
    def __str__(self) -> str:
        return f"StageBuilder: {self._raw_data}"      
###############################################################################################################################################
    def props_proxy_in_stage(self, data: List[Any]) -> List[tuple[PropData, int]]:
        res: List[tuple[PropData, int]] = []
        for obj in data:
            prop = PropDataProxy(obj.get("name"))
            count = int(obj.get("count"))
            res.append((prop, count))
        return res
###############################################################################################################################################
    def actors_proxy_in_stage(self, _data: List[Any]) -> Set[ActorData]:
        res: Set[ActorData] = set()
        for obj in _data:
            _d = ActorDataProxy(obj.get("name"))
            res.add(_d)
        return res
###############################################################################################################################################
    def build(self, block_name: str, json_data: Dict[str, Any], data_base_system: DataBaseSystem) -> 'StageBuilder':
        self._raw_data = json_data.get(block_name)
        if self._raw_data is None:
            logger.error("StageBuilder: stages data is None.")
            return self

        for _bk in self._raw_data:
            _da = _bk.get("stage")    
            assert _da is not None    
            #
            stage_data = data_base_system.get_stage(_da.get('name'))
            assert stage_data is not None
            #连接
            stage_data._props = self.props_proxy_in_stage(_da.get("props"))
            #连接
            actors_in_stage: Set[ActorData] = self.actors_proxy_in_stage(_da.get("actors"))
            stage_data._actors = actors_in_stage
            #添加场景
            self._stages.append(stage_data)

        return self
###############################################################################################################################################
