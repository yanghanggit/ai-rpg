from typing import Any, Optional, List
from loguru import logger
import json
from auxiliary.base_data import StageConditionData, PropData, NPCData, StageData

########################################################################################################################
########################################################################################################################
########################################################################################################################
class WorldDataBuilder:
    def __init__(self, name: str, version: str, runtimepath: str) -> None:
        # version必须与生成的world.json文件中的version一致
        self.name = name
        self.runtimepath = runtimepath
        self.version = version
        #####
        self.data: dict[str, Any] = dict()
        self.admin_npc_builder = NPCBuilder("adminnpcs")
        self.player_npc_builder = NPCBuilder("playernpcs")
        self.npc_buidler = NPCBuilder("npcs")
        self.stage_builder = StageBuilder()

    def check_version_valid(self, world_data_path: str) -> bool:
        try:
            with open(world_data_path, 'r') as file:
                self.data = json.load(file)
                world_data_version: str = self.data['version']
            
        except FileNotFoundError:
            logger.exception(f"File {world_data_path} not found.")
            return False
        
        if self.version == world_data_version:
            return True
        else:
            logger.error(f'游戏数据(World.json)与Builder版本不匹配，请检查。')
            return False

    def build(self) -> None:
        self.admin_npc_builder.build(self.data)
        self.player_npc_builder.build(self.data)
        self.npc_buidler.build(self.data)
        self.stage_builder.build(self.data)

########################################################################################################################
########################################################################################################################
########################################################################################################################
class StageBuilder:
    def __init__(self) -> None:
        self.datalist: Optional[dict[str, Any]] = None
        self.stages: list[StageData] = []

    def __str__(self) -> str:
        return f"StageBuilder: {self.datalist}"      

    #
    def build_prop_conditions(self, condition_data: List[Any]) -> list[StageConditionData]: 
        res: list[StageConditionData] = []
        for data in condition_data:
            createcondition: StageConditionData = StageConditionData(data.get("name"), data.get("type"), data.get("propname"))
            res.append(createcondition)
        return res
    #
    def build_props_in_stage(self, props_data: List[Any]) -> set[PropData]:
        res: set[PropData] = set()
        for obj in props_data:
            prop = PropData(obj.get("name"), obj.get("codename"), obj.get("description"), obj.get("isunique"))
            res.add(prop)
        return res
    #
    def build_npcs_in_stage(self, npcs_data: List[Any]) -> set[NPCData]:
        res: set[NPCData] = set()
        for obj in npcs_data:
            npc = NPCData(obj.get("name"), obj.get("codename"), obj.get("url"), obj.get("memory"))
            res.add(npc)
        return res
    #
    def build(self, json_data: dict[str, Any]) -> None:
        self.datalist = json_data.get("stages")
        if self.datalist is None:
            logger.error("StageBuilder: stages data is None.")
            return

        for data in self.datalist:
            stagedata = data.get("stage")        
            entry_conditions_in_stage: list[StageConditionData] = self.build_prop_conditions(stagedata.get("entry_conditions"))
            exit_conditions_in_stage: list[StageConditionData] = self.build_prop_conditions( stagedata.get("exit_conditions")) 
            propsinstage: set[PropData] = self.build_props_in_stage(stagedata.get("props"))
            npcsinstage: set[NPCData] = self.build_npcs_in_stage(stagedata.get("npcs"))
            stage = StageData(  stagedata.get("name"), 
                            stagedata.get("codename"), 
                            stagedata.get("description"), 
                            stagedata.get("url"), 
                            stagedata.get("memory"), 
                            entry_conditions_in_stage, 
                            exit_conditions_in_stage, 
                            npcsinstage, 
                            propsinstage)
            self.stages.append(stage)
            
########################################################################################################################
########################################################################################################################
########################################################################################################################
class NPCBuilder:

    def __init__(self, dataname: str) -> None:
        self.datalist: Optional[dict[str, Any]] = None
        self.npcs: list[NPCData] = []
        self.dataname = dataname

    def __str__(self) -> str:
        return f"NPCBuilder2: {self.datalist}"       

    #
    def build(self, json_data: dict[str, Any]) -> None:
        self.datalist = json_data.get(self.dataname)
        if self.datalist is None:
            logger.error(f"NPCBuilder2: {self.dataname} data is None.")
            return
        for datablock in self.datalist:
            #yh 先不用做严格检查，因为自动化部分会做严格检查，比如第二阶段的自检过程，如果需要检查，可以单独开一个函数，就先检查一遍，这里就是集中行动
            propdata = datablock.get("props")
            npcprops: set[PropData] = set()
            for propdata in propdata:
                prop = PropData(propdata.get("name"), propdata.get("codename"),  propdata.get("description"), propdata.get("isunique"))
                npcprops.add(prop)
            #
            npc_data = datablock.get("npc")
            npc = NPCData(npc_data.get("name"), npc_data.get("codename"), npc_data.get("url"), npc_data.get("memory"), npcprops)
            self.npcs.append(npc)

########################################################################################################################
########################################################################################################################
########################################################################################################################





        