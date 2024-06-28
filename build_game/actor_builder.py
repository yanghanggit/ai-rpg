from typing import Any, Optional, List, Dict
from loguru import logger
from prototype_data.data_def import PropData, ActorData, PropDataProxy
from prototype_data.data_base_system import DataBaseSystem

class ActorBuilder:
    
    """
    这是一个分析角色json的数据的类。
    """

    def __init__(self) -> None:
        self._raw_data: Optional[Dict[str, Any]] = None
        self._actors: List[ActorData] = []
###############################################################################################################################################
    def __str__(self) -> str:
        return f"ActorBuilder: {self._raw_data}"       
###############################################################################################################################################
    def build(self, block_name: str, json_data: Dict[str, Any], data_base_system: DataBaseSystem) -> 'ActorBuilder':
        self._raw_data = json_data.get(block_name)
        if self._raw_data is None:
            logger.error(f"ActorBuilder: {block_name} data is None.")
            return self
        
        for _bk in self._raw_data:
            # Actor核心数据
            assert _bk.get("actor") is not None
            assert _bk.get("props") is not None
            actor_name = _bk.get("actor").get("name")
            actor_data = data_base_system.get_actor(actor_name)
            if actor_data is None:
                assert actor_data is not None
                logger.error(f"ActorBuilder: {actor_name} not found in database.")
                continue

            # 最终添加到列表
            self._actors.append(actor_data)

            # 分析道具
            actor_data._props.clear()
            for _pd in _bk.get("props"):
                proxy: PropData = PropDataProxy(_pd.get("name"))
                count: int = int(_pd.get("count"))
                actor_data._props.append((proxy, count)) # 连接道具         

        return self
###############################################################################################################################################
