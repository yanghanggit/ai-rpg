import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional, cast
#from game_sample.gen_funcs import (proxy_prop)
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.utils import parse_prop_string
from game_sample.excel_data_actor import ExcelDataActor

class ExcelEditorActor:

    def __init__(self, 
                 my_data: Any, 
                 actor_data_base: Dict[str, ExcelDataActor], 
                 prop_data_base: Dict[str, ExcelDataProp]) -> None:
        #
        if my_data["type"] not in ["Player", "Actor"]:
            assert False, f"Invalid actor type: {my_data['type']}"
        #
        self._my_data: Any = my_data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._prop_data: List[tuple[ExcelDataProp, int]] = []
        # 解析道具
        self.parse_actor_prop()
#################################################################################################################################
    @property
    def excel_data(self) -> Optional[ExcelDataActor]:
        assert self._my_data is not None
        return self._actor_data_base[self._my_data["name"]]
#################################################################################################################################
    @property
    def appearance(self) -> str:
        assert self._my_data is not None
        val = self._my_data["appearance"]
        if val is None:
            return ""
        return str(val)
#################################################################################################################################
    @property
    def attributes(self) -> List[int]:
        assert self._my_data is not None
        data = cast(str, self._my_data["attributes"])
        assert ',' in data, f"raw_string_val: {data} is not valid."
        return [int(attr) for attr in data.split(',')]    
#################################################################################################################################
    @property
    def kick_off_message(self) -> str:
        assert self._my_data is not None
        return cast(str, self._my_data["kick_off_message"])
#################################################################################################################################
    @property
    def actor_current_using_prop(self) -> List[str]:
        assert self._my_data is not None
        raw_string = cast(str, self._my_data["actor_current_using_prop"])
        if raw_string is None:
            return []
        return [str(attr) for attr in raw_string.split(';')]    
#################################################################################################################################
    def parse_actor_prop(self) -> None:

        data: Optional[str] = self._my_data["actor_prop"]
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

        assert self.excel_data is not None

        output: Dict[str, Any] = {}

        output["name"] = self.excel_data.name
        output["codename"] = self.excel_data.codename
        output["url"] = self.excel_data.localhost
        output["kick_off_message"] = self.kick_off_message
        output["appearance"] = self.appearance
        output["actor_archives"] = self.excel_data._actor_archives 
        output["stage_archives"] = self.excel_data._stage_archives 
        output["attributes"] = self.attributes
        output["body"] = self.excel_data.body

        return output
#################################################################################################################################
    # 核心函数！！！
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        #
        assert self.excel_data is not None
        output["name"] = self.excel_data.name
        #
        props_data: List[Dict[str, Any]] = []
        for tp in self._prop_data:
            dt = tp[0].proxy()
            dt["count"] = tp[1]
            props_data.append(dt) 
        #
        output["props"] = props_data
        output["actor_current_using_prop"] = self.actor_current_using_prop
        return output
#################################################################################################################################
    @property
    def gen_agentpy_path(self) -> Path:
        assert self.excel_data is not None
        return self.excel_data.gen_agentpy_path
#################################################################################################################################
    @property
    def name(self) -> str:
        assert self.excel_data is not None
        return self.excel_data.name
#################################################################################################################################