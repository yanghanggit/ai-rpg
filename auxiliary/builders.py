from typing import Any, Optional, List, Set
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
        self.world_npc_builder = NPCBuilder("worldnpcs")
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
        self.world_npc_builder.build(self.data)
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
            # 表达场景NPC的数据，其实需要的数据很少。主要是name
            npc = NPCData(obj.get("name"), "", "", "", set(), set(), set(), "")
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
            
            stage = StageData(stagedata.get("name"), 
                            stagedata.get("codename"), 
                            stagedata.get("description"), 
                            stagedata.get("url"), 
                            stagedata.get("memory"), 
                            entry_conditions_in_stage, 
                            exit_conditions_in_stage, 
                            npcsinstage, 
                            propsinstage)
            
             # 做连接关系 目前仅用名字
            exit_of_prison_and_goto_stagename: str = stagedata.get("exit_of_prison")
            if len(exit_of_prison_and_goto_stagename) > 0:
                stage.stage_as_exit_of_prison(exit_of_prison_and_goto_stagename)

            # 设置属性
            stage.buildattributes(stagedata.get("attributes"))

            #
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
            npcprops: set[PropData] = set()
            propdata = datablock.get("props")
            for propdata in propdata:
                prop = PropData(propdata.get("name"), propdata.get("codename"),  propdata.get("description"), propdata.get("isunique"))
                npcprops.add(prop)

            # NPC核心数据
            npcdata = datablock.get("npc")

            # 寻找人物关系
            mentioned_npcs: Set[str] = set()
            mentioned_npcs_str: str = npcdata.get("mentioned_npcs")
            if len(mentioned_npcs_str) > 0:
                 mentioned_npcs = set(mentioned_npcs_str.split(';'))

             # 寻找人物与场景的关系关系
            mentioned_stages: Set[str] = set()
            mentioned_stages_str: str = npcdata.get("mentioned_stages")
            if len(mentioned_stages_str) > 0:
                 mentioned_stages = set(mentioned_stages_str.split(';'))

            # 创建
            npc = NPCData(npcdata.get("name"), 
                          npcdata.get("codename"), 
                          npcdata.get("url"), 
                          npcdata.get("memory"), 
                          npcprops, 
                          mentioned_npcs,
                          mentioned_stages,
                          npcdata.get("role_appearance"))
            
            ## 设置属性
            npc.buildattributes(npcdata.get("attributes"))
            
            ###
            self.npcs.append(npc)

########################################################################################################################
########################################################################################################################
########################################################################################################################





        