from typing import Any, Optional, List, Dict
from loguru import logger
from prototype_data.data_def import ActorData, PropDataProxy
from prototype_data.data_base_system import DataBaseSystem

class ActorBuilder:
    
    """
    这是一个分析角色json的数据的类。
    """

    def __init__(self) -> None:
        # 这个是从json中读取的数据, 只要我自己的这一块
        self._raw_data: Optional[List[Dict[str, Any]]] = None
        # 构建出来的数据
        self._actors: List[ActorData] = []
###############################################################################################################################################
    def __str__(self) -> str:
        return f"ActorBuilder: {self._raw_data}"
###############################################################################################################################################
    def build(self, 
              my_attention_key_name: str, 
              game_builder_data: Dict[str, Any], 
              data_base_system: DataBaseSystem) -> 'ActorBuilder':
        try:
            # 从大的数据结构中，只拿出我自己关心的那一块
            self._raw_data = game_builder_data[my_attention_key_name]
        except KeyError:
            logger.error(f"ActorBuilder: {my_attention_key_name} data is missing in JSON.")
            return self
        
        if self._raw_data is None:
            logger.error("ActorBuilder: data is None.")
            return self

        # 清空之前的数据
        self._actors.clear()
        for actor_info in self._raw_data:
            try:
                actor_data = data_base_system.get_actor(actor_info['actor']['name'])
                if actor_data is None:
                    raise ValueError(f"Actor {actor_info['actor']['name']} not found in database.")
            except KeyError:
                logger.error("Missing 'actor' or 'name' key in actor block.")
                continue
            
            # 清空之前的数据
            actor_data._props.clear()
            try:
                for prop in actor_info['props']:
                    proxy = PropDataProxy(prop['name'])
                    count = int(prop['count'])
                    # 添加到列表
                    actor_data._props.append((proxy, count))
            except KeyError:
                logger.error("Missing 'props' key or 'name'/'count' in props block.")
                continue
            except ValueError:
                logger.error("Invalid 'count' value. Must be an integer.")
                continue
            
            # 添加到列表
            self._actors.append(actor_data)

        return self
###############################################################################################################################################
