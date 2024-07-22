from typing import Any, Optional, List, Set, Dict
from loguru import logger
from prototype_data.data_def import PropData, ActorData, StageData
from prototype_data.data_base_system import DataBaseSystem

class StageBuilder:
    
    """
    这是一个分析场景json的数据的类。
    """

    def __init__(self) -> None:
        self._raw_data: Optional[List[Dict[str, Any]]] = None
        self._stages: List[StageData] = []
###############################################################################################################################################
    # def __str__(self) -> str:
    #     return f"StageBuilder: {self._raw_data}"      
###############################################################################################################################################
    def props_proxy_in_stage(self, data: List[Any]) -> List[tuple[PropData, int]]:
        res: List[tuple[PropData, int]] = []
        for obj in data:
            res.append((PropData.create_proxy(obj["name"]), int(obj["count"])))
        return res
###############################################################################################################################################
    def actors_proxy_in_stage(self, data: List[Any]) -> Set[ActorData]:
        res: Set[ActorData] = set()
        for obj in data:
            res.add(ActorData.create_proxy(obj["name"]))
        return res
###############################################################################################################################################
    def build(self, raw_data: Any, data_base_system: DataBaseSystem) -> 'StageBuilder':
        self._raw_data = raw_data
        if self._raw_data is None:
            logger.error("StageBuilder: data is None.")
            return self

        # 清空之前的数据
        self._stages.clear()
        for stage_data_info in self._raw_data:

            core_stage_data = stage_data_info["stage"]    
            assert core_stage_data is not None    
            if core_stage_data is None:
                logger.error("Missing 'stage' key in stage block.")
                continue
            
            try:
                stage_data = data_base_system.get_stage(core_stage_data['name'])
                if stage_data is None:
                    raise ValueError(f"Stage {core_stage_data['name']} not found in database.")
                    continue
                
                #连接
                stage_data._props.clear() # 其实这一句是多余的，因为下面会重新赋值，习惯性的写上了
                stage_data._props = self.props_proxy_in_stage(core_stage_data["props"])
                
                #连接
                stage_data._actors.clear() # 其实这一句是多余的，因为下面会重新赋值，习惯性的写上了
                stage_data._actors = self.actors_proxy_in_stage(core_stage_data["actors"])

            except KeyError:
                logger.error("Missing 'stage' or 'name' key in stage block.")
                continue

            #添加场景
            self._stages.append(stage_data)

        return self
###############################################################################################################################################
