import sys
from pathlib import Path
# 将项目根目录添加到sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional
from auxiliary.format_of_complex_stage_entry_and_exit_conditions import parse_complex_stage_condition
from budding_world.utils import (serialization_prop)
from budding_world.excel_data import ExcelDataNPC, ExcelDataProp, ExcelDataStage



class ExcelEditorStageCondition:
    def __init__(self, name: str, type: str, prop_data_base: Dict[str, ExcelDataProp]) -> None:
        self.name: str = name
        self.type: str = type
        self.prop_data_base = prop_data_base
        self.exceldataprop: Optional[ExcelDataProp] = None
        self.parse_condition()
################################################################################################################
    def parse_condition(self) -> None:
        if self.type == "Prop":
            self.exceldataprop = self.prop_data_base.get(self.name, None)
        else:
            logger.error(f"Invalid condition type: {self.type}")
################################################################################################################ 
    def __str__(self) -> str:
        return f"ExcelEditorStageCondition({self.name}, {self.type})"    
################################################################################################################  
    def serialization(self) -> Dict[str, str]:
        dict: Dict[str, str] = {}
        if self.exceldataprop is not None:
            logger.debug(f"这是一个普通的场景条件: {self.name}")
            dict['name'] = self.name
            dict['type'] = self.type
            dict['propname'] = self.exceldataprop.name
        else:
            logger.warning(f"这是一个复杂的场景条件: {self.name}")
            res = parse_complex_stage_condition(self.name)
            parsename = res[0]
            parsecondition = str(self.name)
            dict['name'] = parsename
            dict['type'] = self.type
            dict['propname'] = parsecondition
        return dict
    



class ExcelEditorStage:

    def __init__(self, data: Any, npc_data_base: Dict[str, ExcelDataNPC], prop_data_base: Dict[str, ExcelDataProp], stage_data_base: Dict[str, ExcelDataStage]) -> None:
        self.data: Any = data
        self.npc_data_base = npc_data_base
        self.prop_data_base = prop_data_base
        self.stage_data_base = stage_data_base

        #数据
        self.stage_entry_conditions: List[ExcelEditorStageCondition] = []
        self.stage_exit_conditions: List[ExcelEditorStageCondition] = []
        self.props_in_stage: List[ExcelDataProp] = []
        self.npcs_in_stage: List[ExcelDataNPC] = []
        self.initialization_memory: str = ""
        self.exit_of_prison: str = ""
        self.raw_interactive_props_data: str = ""
        self.interactive_props: List[ExcelDataProp] = []

        if self.data["type"] not in ["Stage"]:
            logger.error(f"Invalid Stage type: {self.data['type']}")
            return

        #分析数据
        self.parse_stage_entry_conditions()
        self.parse_stage_exit_conditions()
        self.parse_props_in_stage()
        self.parse_npcs_in_stage()
        self.parse_initialization_memory()
        self.parse_exit_of_prison()
        self.parse_interactive_props()

    def parse_stage_entry_conditions(self) -> None:
        stage_entry_conditions: Optional[str] = self.data["stage_entry_conditions"]
        if stage_entry_conditions is None:
            return        
        list_stage_entry_conditions = stage_entry_conditions.split(";")
        for condition in list_stage_entry_conditions:
            if condition in self.prop_data_base:
                self.stage_entry_conditions.append(ExcelEditorStageCondition(condition, "Prop", self.prop_data_base))
            else:
                logger.error(f"Invalid condition: {condition}")

    def parse_stage_exit_conditions(self) -> None:
        
        stage_exit_conditions = self.data["stage_exit_conditions"]
        if stage_exit_conditions is None:
            return
        
        list_stage_exit_conditions = stage_exit_conditions.split(";")
        for condition in list_stage_exit_conditions:
            if condition not in self.prop_data_base:
                logger.warning(f"无法直接匹配道具名字，可能是是一个复杂条件: {condition}")
            self.stage_exit_conditions.append(ExcelEditorStageCondition(condition, "Prop", self.prop_data_base))
    #
    def parse_props_in_stage(self) -> None:
        props_in_stage: Optional[str] = self.data["props_in_stage"]
        if props_in_stage is None:
            return
        list_props_in_stage = props_in_stage.split(";")
        for prop in list_props_in_stage:
            if prop in self.prop_data_base:
                self.props_in_stage.append(self.prop_data_base[prop])
            else:
                logger.error(f"Invalid prop: {prop}")

    def parse_npcs_in_stage(self) -> None:
        npcs_in_stage: Optional[str] = self.data["npcs_in_stage"]
        if npcs_in_stage is None:
            return
        list_npcs_in_stage = npcs_in_stage.split(";")
        for npc in list_npcs_in_stage:
            if npc in self.npc_data_base:
                self.npcs_in_stage.append(self.npc_data_base[npc])
            else:
                logger.error(f"Invalid npc: {npc}")

    def parse_initialization_memory(self) -> None:
        initialization_memory = self.data["initialization_memory"]
        if initialization_memory is None:
            return
        self.initialization_memory = str(initialization_memory)

    def parse_exit_of_prison(self) -> None:
        attrname = "exit_of_prison"
        if attrname in self.data and self.data[attrname] is not None:
           self.exit_of_prison = str(self.data[attrname])

    def parse_interactive_props(self) -> None:
        attrname = "interactive_props"
        if attrname not in self.data and self.data[attrname] is None:
            return
        self.raw_interactive_props_data = str(self.data[attrname])
        if self.raw_interactive_props_data == "None":
            #空的不用继续了
            return
        
        raw_data = self.raw_interactive_props_data
        
        ###写点啥
        parse_res = parse_complex_stage_condition(raw_data)
        if len(parse_res) != 2:
            logger.error(f"复杂条件: {raw_data}")
            return
        
        propname1 = parse_res[0]
        prop1 = self.prop_data_base.get(propname1, None)
        if prop1 is not None:
            self.interactive_props.append(prop1)
        else:
            logger.error(f"Invalid prop: {propname1}")
        
        propname2 = parse_res[1]
        prop2 = self.prop_data_base.get(propname2, None)
        if prop2 is not None:
            self.interactive_props.append(prop2)
        else:
            logger.error(f"Invalid prop: {propname2}")
        
    def __str__(self) -> str:
        propsstr = ', '.join(str(prop) for prop in self.props_in_stage)
        npcsstr = ', '.join(str(npc) for npc in self.npcs_in_stage)
        entrystr = ', '.join(str(condition) for condition in self.stage_entry_conditions)
        exitstr = ', '.join(str(condition) for condition in self.stage_exit_conditions)
        return "ExcelEditorStage({}, {}, stage_entry_conditions: {}, stage_exit_conditions: {}, props_in_stage: {}, npcs_in_stage: {})".format(self.data["name"], self.data["type"], entrystr, exitstr, propsstr, npcsstr)

    def serialization_stage_conditions(self, conditions: List[ExcelEditorStageCondition]) -> List[Dict[str, str]]:
        list: List[Dict[str, str]] = []
        for condition in conditions:
            list.append(condition.serialization())
        return list
    
    def serialization_stage_props(self, props: List[ExcelDataProp]) -> List[Dict[str, str]]:
        list: List[Dict[str, str]] = []
        for prop in props:
            dict = serialization_prop(prop)
            list.append(dict)
        return list
    
    ## 这里只做NPC引用，所以导出名字即可
    def serialization_stage_npcs(self, npcs: List[ExcelDataNPC]) -> List[Dict[str, str]]:
        list: List[Dict[str, str]] = []
        for npc in npcs:
            dict: Dict[str, str] = {} 
            dict['name'] = npc.name  ## 这里只做NPC引用，所以导出名字即可
            list.append(dict)
        return list
     
    def serialization(self) -> Dict[str, Any]:
        data_stage: ExcelDataStage = self.stage_data_base[self.data["name"]]

        dict: Dict[str, Any] = {}
        dict["name"] = data_stage.name
        dict["codename"] = data_stage.codename
        dict["description"] = data_stage.description
        dict["url"] = data_stage.localhost_api()
        dict["memory"] = self.initialization_memory
        dict["exit_of_prison"] = self.exit_of_prison
        dict["interactive_props"] = self.raw_interactive_props_data
        
        entry_conditions = self.serialization_stage_conditions(self.stage_entry_conditions)
        exit_conditions = self.serialization_stage_conditions(self.stage_exit_conditions)
        props = self.serialization_stage_props(self.props_in_stage)
        npcs = self.serialization_stage_npcs(self.npcs_in_stage)

        dict["entry_conditions"] = entry_conditions
        dict["exit_conditions"] = exit_conditions
        dict["props"] = props
        dict["npcs"] = npcs
        dict['attributes'] = data_stage.attributes

        output_dict: Dict[str, Any] = {}
        output_dict["stage"] = dict
        return output_dict