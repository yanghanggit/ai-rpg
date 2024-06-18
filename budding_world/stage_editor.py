import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent # 将项目根目录添加到sys.path
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional, cast
from budding_world.gen_funcs import (proxy_prop)
from budding_world.excel_data import ExcelDataActor, ExcelDataProp, ExcelDataStage
import pandas as pd


class ExcelEditorStage:

    def __init__(self, data: Any, actor_data_base: Dict[str, ExcelDataActor], prop_data_base: Dict[str, ExcelDataProp], stage_data_base: Dict[str, ExcelDataStage]) -> None:
        self.data: Any = data
        self.actor_data_base = actor_data_base
        self.prop_data_base = prop_data_base
        self.stage_data_base = stage_data_base
        self.props_in_stage: List[ExcelDataProp] = []
        self.actors_in_stage: List[ExcelDataActor] = []
        self.kick_off_memory: str = ""
        self.exit_of_portal: str = ""

        if self.data["type"] not in ["Stage"]:
            logger.error(f"Invalid Stage type: {self.data['type']}")
            return

        #分析数据
        self.parse_props_in_stage()
        self.parse_actors_in_stage()
        self.parse_kick_off_memory()
        self.parse_exit_of_portal()

        ### 这里可以添加属性？？？
        self.attributes: str = data.get("attributes", "")
        logger.debug(f"Stage: {self.data['name']} has attributes: {self.attributes}")
################################################################################################################################
    def parse_props_in_stage(self) -> None:
        props_in_stage: Optional[str] = self.data["stage_prop"]
        if props_in_stage is None:
            return
        list_props_in_stage = props_in_stage.split(";")
        for prop in list_props_in_stage:
            if prop in self.prop_data_base:
                self.props_in_stage.append(self.prop_data_base[prop])
            else:
                logger.error(f"Invalid prop: {prop}")
################################################################################################################################
    def parse_actors_in_stage(self) -> None:
        actors_in_stage: Optional[str] = self.data["actors_in_stage"]
        if actors_in_stage is None:
            return
        list_actors_in_stage = actors_in_stage.split(";")
        for actor in list_actors_in_stage:
            if actor in self.actor_data_base:
                self.actors_in_stage.append(self.actor_data_base[actor])
            else:
                logger.error(f"Invalid actor: {actor}")
################################################################################################################################
    def parse_kick_off_memory(self) -> None:
        kick_off_memory = self.data["kick_off_memory"]
        if kick_off_memory is None:
            return
        self.kick_off_memory = str(kick_off_memory)
################################################################################################################################
    def parse_exit_of_portal(self) -> None:
        attrname = "exit_of_portal"
        if attrname in self.data and self.data[attrname] is not None:
           self.exit_of_portal = str(self.data[attrname])
################################################################################################################################
    def __str__(self) -> str:
        propsstr = ', '.join(str(prop) for prop in self.props_in_stage)
        actor_str = ', '.join(str(actor) for actor in self.actors_in_stage)
        return "ExcelEditorStage({}, {}, props_in_stage: {}, actors_in_stage: {})".format(self.data["name"], self.data["type"], propsstr, actor_str)
################################################################################################################################
    def stage_props_proxy(self, props: List[ExcelDataProp]) -> List[Dict[str, str]]:
        ls: List[Dict[str, str]] = []
        for prop in props:
            _dt = proxy_prop(prop) #代理即可
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
        data_stage: ExcelDataStage = self.stage_data_base[self.data["name"]]

        _dt: Dict[str, Any] = {}
        _dt["name"] = data_stage.name
        _dt["codename"] = data_stage.codename
        _dt["description"] = data_stage.description
        _dt["url"] = data_stage.localhost_api()
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

        output_dict: Dict[str, Any] = {}
        output_dict["stage"] = _dt
        return output_dict
################################################################################################################################
    def proxy(self) -> Dict[str, Any]:
        data_stage: ExcelDataStage = self.stage_data_base[self.data["name"]]
        _dt: Dict[str, Any] = {}
        _dt["name"] = data_stage.name
        props = self.stage_props_proxy(self.props_in_stage)
        actors = self.stage_actors_proxy(self.actors_in_stage)
        _dt["props"] = props
        _dt["actors"] = actors
        output_dict: Dict[str, Any] = {}
        output_dict["stage"] = _dt
        return output_dict
################################################################################################################################
    def safe_get_string(self, key: str) -> str:
        if pd.isna(self.data[key]):
            return ""
        return cast(str, self.data[key]) 
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