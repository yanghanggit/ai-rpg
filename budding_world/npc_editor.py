import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional
from budding_world.utils import (serialization_prop)
from budding_world.excel_data import ExcelDataNPC, ExcelDataProp


################################################################################################################   
class ExcelEditorNPC:
    def __init__(self, data: Any, npc_data_base: Dict[str, ExcelDataNPC], prop_data_base: Dict[str, ExcelDataProp]) -> None:
        #
        self.data: Any = data
        self.npc_data_base = npc_data_base
        self.prop_data_base = prop_data_base
        #
        self.excelnpc: Optional[ExcelDataNPC] = None
        self.excelprops: List[ExcelDataProp] = []
        self.initialization_memory: str = ""
        self.npc_role_appearance: str = ""
        #
        if self.data["type"] not in ["World", "Player", "NPC"]:
            logger.error(f"Invalid NPC type: {self.data['type']}")
            return
        
        self.excelnpc = self.npc_data_base[self.data["name"]]
        self.parse_props_on_npc()
        self.parse_initialization_memory()
        self.parse_npc_role_appearance()
        
    def parse_props_on_npc(self) -> None:
        data: str = self.data["props_on_npc"]
        if data is None:
            return        
        propfiles = data.split(";")
        for file in propfiles:
            if file in self.prop_data_base:
                self.excelprops.append(self.prop_data_base[file])
            else:
                logger.error(f"Invalid file: {file}")

    def parse_initialization_memory(self) -> None:
        initialization_memory = self.data["initialization_memory"]
        if initialization_memory is None:
            return
        self.initialization_memory = str(initialization_memory)
    
    def parse_npc_role_appearance(self) -> None:
        npc_role_appearance = self.data["npc_role_appearance"]
        if npc_role_appearance is None:
            return
        self.npc_role_appearance = str(npc_role_appearance)

    def __str__(self) -> str:
        propsstr = ', '.join(str(prop) for prop in self.excelprops)
        return f"ExcelEditorNPC({self.data['name']}, {self.data['type']}, files: {propsstr})"
    
    def serialization_core(self, target: Optional[ExcelDataNPC]) -> Dict[str, str]:
        if target is None:
            return {}
        dict: Dict[str, str] = {}
        dict['name'] = target.name
        dict['codename'] = target.codename
        dict['url'] = target.localhost_api()
        dict['memory'] = self.initialization_memory
        dict['role_appearance'] = self.npc_role_appearance
        dict['mentioned_npcs'] = ";".join(target.mentioned_npcs)
        dict['mentioned_stages'] = ";".join(target.mentioned_stages)
        dict['attributes'] = target.attributes
        return dict
    
    def serialization_my_props(self, excelprops: List[ExcelDataProp]) -> List[Dict[str, str]]:
        props: List[Dict[str, str]] = []
        for prop in excelprops:
            dict = serialization_prop(prop)
            props.append(dict)
        return props

    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        npc = self.serialization_core(self.excelnpc)
        props = self.serialization_my_props(self.excelprops)
        dict: Dict[str, Any] = {}
        dict["npc"] = npc
        dict["props"] = props
        return dict
