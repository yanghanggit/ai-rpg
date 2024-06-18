import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional, cast
from budding_world.gen_funcs import (proxy_prop)
from budding_world.excel_data import ExcelDataActor, ExcelDataProp


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
        self._prop_data: List[ExcelDataProp] = []
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
        return cast(str, self._data.get("appearance", "")) 
#################################################################################################################################
    @property
    def attributes(self) -> str:
        assert self._data is not None
        return cast(str, self._data.get("attributes", ""))
#################################################################################################################################
    @property
    def kick_off_memory(self) -> str:
        assert self._data is not None
        return cast(str, self._data.get("kick_off_memory", ""))
#################################################################################################################################
    def parse_actor_prop(self) -> None:
        data: Optional[str] = self._data.get("actor_prop", None) 
        if data is None:
            return        
        names = data.split(";")
        for _n in names:
            if _n in self._prop_data_base:
                self._prop_data.append(self._prop_data_base[_n])
            else:
                logger.error(f"Invalid file: {_n}")
#################################################################################################################################
    def serialization_core(self, actor_data: Optional[ExcelDataActor]) -> Dict[str, str]:
        if actor_data is None:
            return {}
        _dt: Dict[str, str] = {}
        _dt["name"] = actor_data._name
        _dt["codename"] = actor_data._codename
        _dt["url"] = actor_data.localhost()
        _dt["kick_off_memory"] = self.kick_off_memory
        _dt["appearance"] = self.appearance
        _dt["actor_archives"] = ";".join(actor_data._actor_archives)
        _dt["stage_archives"] = ";".join(actor_data._stage_archives)
        _dt["attributes"] = self.attributes
        _dt["body"] = actor_data._body
        return _dt
#################################################################################################################################
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        _dt: Dict[str, Any] = {}
        _dt["actor"] = self.serialization_core(self.actor_data)
        return _dt
#################################################################################################################################
    # 核心函数！！！
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        #
        actor_proxy: Dict[str, str] = {}
        assert self.actor_data is not None
        actor_proxy['name'] = self.actor_data._name
        #
        props_proxy: List[Dict[str, str]] = []
        for prop in self._prop_data:
            #代理即可
            _dt = proxy_prop(prop)
            _dt["count"] = "99" #todo
            props_proxy.append(_dt) 
        #
        output["actor"] = actor_proxy
        output["props"] = props_proxy
        return output
#################################################################################################################################