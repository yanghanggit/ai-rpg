import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional
from budding_world.gen_funcs import (serialization_prop, proxy_prop)
from budding_world.excel_data import ExcelDataActor, ExcelDataProp


################################################################################################################   
class ExcelEditorActor:
    def __init__(self, data: Any, actor_data_base: Dict[str, ExcelDataActor], prop_data_base: Dict[str, ExcelDataProp]) -> None:
        #
        self.data: Any = data
        self.actor_data_base = actor_data_base
        self.prop_data_base = prop_data_base
        #
        self.excelactor: Optional[ExcelDataActor] = None
        self.excelprops: List[ExcelDataProp] = []
        self.kick_off_memory: str = ""
        self._appearance: str = ""
        #
        if self.data["type"] not in ["Player", "Actor"]:
            logger.error(f"Invalid type: {self.data['type']}")
            return
        
        self.excelactor = self.actor_data_base[self.data["name"]]
        self.parse_props_on_actor()
        self.parse_kick_off_memory()
        self.parse_appearance()

        ### 这里可以添加属性？？？
        self.attributes: str = data.get("attributes", "")
        logger.debug(f"Stage: {self.data['name']} has attributes: {self.attributes}")

    def parse_props_on_actor(self) -> None:
        data: str = self.data["actor_prop"]
        if data is None:
            return        
        propfiles = data.split(";")
        for file in propfiles:
            if file in self.prop_data_base:
                self.excelprops.append(self.prop_data_base[file])
            else:
                logger.error(f"Invalid file: {file}")

    def parse_kick_off_memory(self) -> None:
        kick_off_memory = self.data["kick_off_memory"]
        if kick_off_memory is None:
            return
        self.kick_off_memory = str(kick_off_memory)
    
    def parse_appearance(self) -> None:
        _appearance = self.data["appearance"]
        if _appearance is None:
            return
        self._appearance = str(_appearance)

    def __str__(self) -> str:
        propsstr = ', '.join(str(prop) for prop in self.excelprops)
        return f"ExcelEditorActor({self.data['name']}, {self.data['type']}, files: {propsstr})"
    
    def serialization_core(self, target: Optional[ExcelDataActor]) -> Dict[str, str]:
        if target is None:
            return {}
        _dt: Dict[str, str] = {}
        _dt['name'] = target.name
        _dt['codename'] = target.codename
        _dt['url'] = target.localhost_api()
        _dt["kick_off_memory"] = self.kick_off_memory
        _dt['appearance'] = self._appearance
        _dt['mentioned_actors'] = ";".join(target.mentioned_actors)
        _dt['mentioned_stages'] = ";".join(target.mentioned_stages)
        _dt['attributes'] = self.attributes #target.attributes
        _dt['body'] = target._body
        return _dt
    
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        _dt: Dict[str, Any] = {}
        _dt["actor"] = self.serialization_core(self.excelactor)
        return _dt
    
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        #
        actor_proxy: Dict[str, str] = {}
        assert self.excelactor is not None
        actor_proxy['name'] = self.excelactor.name
        #
        props_proxy: List[Dict[str, str]] = []
        for prop in self.excelprops:
            props_proxy.append(proxy_prop(prop))#代理即可
        #
        output["actor"] = actor_proxy
        output["props"] = props_proxy
        return output
