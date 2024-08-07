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
        _str_ = data.split(";")
        for _ss in _str_:
            _tp = parse_prop_string(_ss)
            _name = _tp[0]
            _count = _tp[1]
            if _name not in self._prop_data_base:
                logger.error(f"Invalid prop: {_name}")
                continue
            self._prop_data.append((self._prop_data_base[_name], _count))
#################################################################################################################################
    def serialization_core(self, actor_data: Optional[ExcelDataActor]) -> Dict[str, Any]:
        if actor_data is None:
            return {}
        out_put: Dict[str, Any] = {}
        out_put["name"] = actor_data._name
        out_put["codename"] = actor_data._codename
        out_put["url"] = actor_data.localhost()
        out_put["kick_off_memory"] = self.kick_off_memory
        out_put["appearance"] = self.appearance
        out_put["actor_archives"] = actor_data._actor_archives 
        out_put["stage_archives"] = actor_data._stage_archives 
        out_put["attributes"] = self.attributes
        out_put["body"] = actor_data._body
        return out_put
#################################################################################################################################
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        return self.serialization_core(self.actor_data)
#################################################################################################################################
    # 核心函数！！！
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        #
        assert self.actor_data is not None
        output['name'] = self.actor_data._name
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