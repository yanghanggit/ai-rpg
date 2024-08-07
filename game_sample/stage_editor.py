import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent # 将项目根目录添加到sys.path
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional, cast
from game_sample.gen_funcs import (proxy_prop)
from game_sample.excel_data import ExcelDataActor, ExcelDataProp, ExcelDataStage
import pandas as pd
from game_sample.utils import parse_prop_string


class ExcelEditorStage:

    def __init__(self, 
                 data: Any, 
                 actor_data_base: Dict[str, ExcelDataActor], 
                 prop_data_base: Dict[str, ExcelDataProp], 
                 stage_data_base: Dict[str, ExcelDataStage]) -> None:
        
        if data["type"] not in ["Stage"]:
            assert False, f"Invalid Stage type: {data['type']}"
        #
        self._data: Any = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._stage_data_base: Dict[str, ExcelDataStage] = stage_data_base
        self._stage_prop: List[tuple[ExcelDataProp, int]] = []
        self._actors_in_stage: List[ExcelDataActor] = []
        #分析数据
        self.parse_stage_prop()
        self.parse_actors_in_stage()
#################################################################################################################################
    @property
    def attributes(self) -> List[int]:
        assert self._data is not None
        data = cast(str, self._data["attributes"])
        assert ',' in data, f"raw_string_val: {data} is not valid."
        return [int(attr) for attr in data.split(',')]    
################################################################################################################################
    def parse_stage_prop(self) -> None:
        data: Optional[str] = self._data["stage_prop"]
        if data is None:
            return
        _str_ = data.split(";")
        for _ss in _str_:
            _tp = parse_prop_string(_ss)
            _name = _tp[0]
            _count = _tp[1]
            if _name not in self._prop_data_base:
                continue
            self._stage_prop.append((self._prop_data_base[_name], _count))
################################################################################################################################
    def parse_actors_in_stage(self) -> None:
        data: Optional[str] = self._data["actors_in_stage"]
        if data is None:
            return
        names = data.split(";")
        for _n in names:
            if _n in self._actor_data_base:
                self._actors_in_stage.append(self._actor_data_base[_n])
            else:
                logger.error(f"Invalid actor: {_n}")
################################################################################################################################
    @property
    def kick_off_memory(self) -> str:
        assert self._data is not None
        return cast(str, self._data["kick_off_memory"])
################################################################################################################################
    @property
    def exit_of_portal(self) -> str:
        assert self._data is not None
        val = self._data["exit_of_portal"]
        if val is None:
            return ""
        return str(val)
################################################################################################################################
    def stage_props_proxy(self, props: List[tuple[ExcelDataProp, int]]) -> List[Dict[str, str]]:
        ls: List[Dict[str, str]] = []
        for tp in props:
            prop = tp[0]
            count = tp[1]
            _dt = proxy_prop(prop) #代理即可
            _dt["count"] = str(count)
            ls.append(_dt)
        return ls
################################################################################################################################
    ## 这里只做Actor引用，所以导出名字即可
    def stage_actors_proxy(self, actors: List[ExcelDataActor]) -> List[Dict[str, str]]:
        ls: List[Dict[str, str]] = []
        for _d in actors:
            _dt: Dict[str, str] = {} 
            _dt['name'] = _d.name  ## 这里只做引用，所以导出名字即可
            ls.append(_dt)
        return ls
################################################################################################################################
    def serialization(self) -> Dict[str, Any]:

        data_stage: ExcelDataStage = self._stage_data_base[self._data["name"]]

        _dt: Dict[str, Any] = {}
        _dt["name"] = data_stage.name
        _dt["codename"] = data_stage.codename
        _dt["description"] = data_stage.description
        _dt["url"] = data_stage.localhost
        _dt["kick_off_memory"] = self.kick_off_memory
        _dt["exit_of_portal"] = self.exit_of_portal
        _dt['attributes'] = self.attributes 

        # 添加新的场景限制条件
        _dt["stage_entry_status"] = self.stage_entry_status
        _dt["stage_entry_actor_status"] = self.stage_entry_actor_status
        _dt["stage_entry_actor_props"] = self.stage_entry_actor_props
        _dt["stage_exit_status"] = self.stage_exit_status
        _dt["stage_exit_actor_status"] = self.stage_exit_actor_status
        _dt["stage_exit_actor_props"] = self.stage_exit_actor_props

        return _dt
################################################################################################################################
    def proxy(self) -> Dict[str, Any]:
        
        data_stage: ExcelDataStage = self._stage_data_base[self._data["name"]]
        output: Dict[str, Any] = {}
        output["name"] = data_stage.name
        #
        props = self.stage_props_proxy(self._stage_prop)
        output["props"] = props
        #
        actors = self.stage_actors_proxy(self._actors_in_stage)
        output["actors"] = actors
        #
        return output
################################################################################################################################
    def safe_get_string(self, key: str) -> str:
        if pd.isna(self._data[key]):
            return ""
        return cast(str, self._data[key]) 
################################################################################################################################
    @property
    def stage_entry_status(self) -> str:
        return self.safe_get_string("stage_entry_status")
################################################################################################################################
    @property
    def stage_entry_actor_status(self) -> str:
        return self.safe_get_string("stage_entry_actor_status")
################################################################################################################################
    @property
    def stage_entry_actor_props(self) -> str:
        return self.safe_get_string("stage_entry_actor_props")
################################################################################################################################
    @property
    def stage_exit_status(self) -> str:
        return self.safe_get_string("stage_exit_status")
################################################################################################################################
    @property
    def stage_exit_actor_status(self) -> str:
        return self.safe_get_string("stage_exit_actor_status")
################################################################################################################################
    @property
    def stage_exit_actor_props(self) -> str:
        return self.safe_get_string("stage_exit_actor_props")
################################################################################################################################