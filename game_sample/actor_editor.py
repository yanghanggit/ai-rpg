import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional, cast
from game_sample.gen_funcs import (proxy_prop)
from game_sample.excel_data import ExcelDataActor, ExcelDataProp
from game_sample.utils import parse_prop_string

class ExcelEditorActor:

    def __init__(self, 
                 data: Any, 
                 actor_data_base: Dict[str, ExcelDataActor], 
                 prop_data_base: Dict[str, ExcelDataProp]) -> None:
        #
        if data["type"] not in ["Player", "Actor"]:
            assert False, f"Invalid actor type: {data['type']}"
        #
        self._data: Any = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._prop_data: List[tuple[ExcelDataProp, int]] = []
        # 解析道具
        self.parse_actor_prop()
#################################################################################################################################
    @property
    def actor_data(self) -> Optional[ExcelDataActor]:
        assert self._data is not None
        return self._actor_data_base[self._data["name"]]
#################################################################################################################################
    @property
    def appearance(self) -> str:
        assert self._data is not None
        val = self._data["appearance"]
        if val is None:
            return ""
        return str(val)
#################################################################################################################################
    @property
    def attributes(self) -> List[int]:
        assert self._data is not None
        data = cast(str, self._data["attributes"])
        assert ',' in data, f"raw_string_val: {data} is not valid."
        return [int(attr) for attr in data.split(',')]    
#################################################################################################################################
    @property
    def kick_off_memory(self) -> str:
        assert self._data is not None
        return cast(str, self._data["kick_off_memory"])
#################################################################################################################################
    def parse_actor_prop(self) -> None:

        data: Optional[str] = self._data["actor_prop"]
        if data is None:
            return        
        
        for prop_info_string in data.split(";"):
            parse = parse_prop_string(prop_info_string)
            prop_name = parse[0]
            prop_count = parse[1]

            if prop_name not in self._prop_data_base:
                logger.error(f"Invalid prop: {prop_name}")
                continue

            self._prop_data.append((self._prop_data_base[prop_name], prop_count))
#################################################################################################################################
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:

        assert self.actor_data is not None

        output: Dict[str, Any] = {}

        output["name"] = self.actor_data.name
        output["codename"] = self.actor_data.codename
        output["url"] = self.actor_data.localhost
        output["kick_off_memory"] = self.kick_off_memory
        output["appearance"] = self.appearance
        output["actor_archives"] = self.actor_data._actor_archives 
        output["stage_archives"] = self.actor_data._stage_archives 
        output["attributes"] = self.attributes
        output["body"] = self.actor_data.body

        return output
#################################################################################################################################
    # 核心函数！！！
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        #
        assert self.actor_data is not None
        output['name'] = self.actor_data.name
        #
        props_block: List[Dict[str, Any]] = []
        for tp in self._prop_data:
            #代理即可
            prop = tp[0]
            count = tp[1]
            dt = proxy_prop(prop)
            dt["count"] = count
            props_block.append(dt) 
        #
        output["props"] = props_block
        return output
#################################################################################################################################