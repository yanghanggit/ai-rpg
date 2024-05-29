from typing import Any, Optional, List, Set
from loguru import logger
import json
from auxiliary.base_data import StageConditionData, PropData, NPCData, StageData, NPCDataProxy, PropDataProxy
from auxiliary.data_base_system import DataBaseSystem

########################################################################################################################
########################################################################################################################
########################################################################################################################
class WorldDataBuilder:
    def __init__(self, name: str, version: str, runtimepath: str, data_base_system: DataBaseSystem) -> None:
        # version必须与生成的world.json文件中的version一致
        self.name = name
        self.runtimepath = runtimepath
        self.version = version
        #####
        self.data: dict[str, Any] = dict()
        self.world_npc_builder = NPCBuilder("worlds")
        self.player_npc_builder = NPCBuilder("players")
        self.npc_buidler = NPCBuilder("npcs")
        self.stage_builder = StageBuilder()
        ####依赖注入的方式，将数据库系统注入到这里
        self.data_base_system = data_base_system

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
###############################################################################################################################################
    def build(self) -> None:
        self.create_data_base_system()
        self.world_npc_builder.build(self.data, self.data_base_system)
        self.player_npc_builder.build(self.data, self.data_base_system)
        self.npc_buidler.build(self.data, self.data_base_system)
        self.stage_builder.build(self.data, self.data_base_system)
###############################################################################################################################################
    def create_npc_data_base(self, npcs: Any) -> None:
        if npcs is None:
            logger.error("没有NPC数据内容(npcs)，请检查World.json配置。")
            return
        
        for npc in npcs:
            npcdata = npc.get('npc', None)
            assert npcdata is not None

            # 寻找角色关系
            mentioned_npcs: Set[str] = set()
            mentioned_npcs_str: str = npcdata.get("mentioned_npcs")
            if len(mentioned_npcs_str) > 0:
                 mentioned_npcs = set(mentioned_npcs_str.split(';'))

             # 寻找角色与场景的关系关系
            mentioned_stages: Set[str] = set()
            mentioned_stages_str: str = npcdata.get("mentioned_stages")
            if len(mentioned_stages_str) > 0:
                 mentioned_stages = set(mentioned_stages_str.split(';'))

            # 创建
            npc = NPCData(npcdata.get("name"), 
                          npcdata.get("codename"), 
                          npcdata.get("url"), 
                          npcdata.get("memory"), 
                          set(), 
                          mentioned_npcs,
                          mentioned_stages,
                          npcdata.get("role_appearance"))
            
            ## 设置属性
            npc.build_attributes(npcdata.get("attributes"))
            self.data_base_system.add_npc(npcdata.get('name'), npc)
###############################################################################################################################################
    def create_stage_data_base(self, stages: Any) -> None:
        if stages is None:
            logger.error("没有场景数据内容(stages)，请检查World.json配置。")
            return
        
        for stage in stages:
            #print(stage)
            stagedata = stage.get('stage', None)
            assert stagedata is not None

            entry_conditions_in_stage: list[StageConditionData] = self.build_prop_conditions(stagedata.get("entry_conditions"))
            exit_conditions_in_stage: list[StageConditionData] = self.build_prop_conditions( stagedata.get("exit_conditions")) 
            
            stage = StageData(stagedata.get("name"), 
                            stagedata.get("codename"), 
                            stagedata.get("description"), 
                            stagedata.get("url"), 
                            stagedata.get("memory"), 
                            entry_conditions_in_stage, 
                            exit_conditions_in_stage, 
                            set(), 
                            set(),
                            stagedata.get('interactive_props'))
            
             # 做连接关系 目前仅用名字
            exit_of_prison_and_goto_stagename: str = stagedata.get("exit_of_prison")
            if len(exit_of_prison_and_goto_stagename) > 0:
                stage.stage_as_exit_of_prison(exit_of_prison_and_goto_stagename)

            # 设置属性
            stage.build_attributes(stagedata.get("attributes"))

            # 添加
            self.data_base_system.add_stage(stagedata.get('name'), stage)
###############################################################################################################################################
    def create_prop_data_base(self, props: Any) -> None:
        if props is None:
            logger.error("没有道具数据内容(props)，请检查World.json配置。")
            return

        for prop_data in props:
            self.data_base_system.add_prop(prop_data.get('name'), PropData(
                prop_data.get('name'), 
                prop_data.get('codename'), 
                prop_data.get('description'), 
                prop_data.get('isunique'), 
                prop_data.get('type'), 
                prop_data.get('attributes')))
###############################################################################################################################################
    def create_data_base_system(self) -> None:
        database = self.data.get('database', None)
        if database is None:
            logger.error("没有数据库(database)，请检查World.json配置。")
            return
        self.create_npc_data_base(database.get('npcs', None))
        self.create_stage_data_base(database.get('stages', None))
        self.create_prop_data_base(database.get('props', None))
        #logger.info("创建数据库成功。")
########################################################################################################################
    def build_prop_conditions(self, condition_data: List[Any]) -> list[StageConditionData]: 
        res: list[StageConditionData] = []
        for data in condition_data:
            createcondition: StageConditionData = StageConditionData(data.get("name"), data.get("type"), data.get("propname"))
            res.append(createcondition)
        return res
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
    def props_proxy_in_stage(self, props_data: List[Any]) -> set[PropData]:
        res: set[PropData] = set()
        for obj in props_data:
            prop = PropDataProxy(obj.get("name"))
            res.add(prop)
        return res
    #
    def npcs_proxy_in_stage(self, npcs_data: List[Any]) -> set[NPCData]:
        res: set[NPCData] = set()
        for obj in npcs_data:
            npc = NPCDataProxy(obj.get("name"))
            res.add(npc)
        return res
    #
    def build(self, json_data: dict[str, Any], data_base_system: DataBaseSystem) -> None:
        self.datalist = json_data.get("stages")
        if self.datalist is None:
            logger.error("StageBuilder: stages data is None.")
            return

        for data in self.datalist:
            stagedata = data.get("stage")    
            assert stagedata is not None    
            #
            stage = data_base_system.get_stage(stagedata.get('name'))
            assert stage is not None
            #连接
            propsinstage: set[PropData] = self.props_proxy_in_stage(stagedata.get("props"))
            stage.props = propsinstage
            #连接
            npcsinstage: set[NPCData] = self.npcs_proxy_in_stage(stagedata.get("npcs"))
            stage.npcs = npcsinstage
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
    def build(self, json_data: dict[str, Any], data_base_system: DataBaseSystem) -> None:
        self.datalist = json_data.get(self.dataname)
        if self.datalist is None:
            logger.error(f"NPCBuilder2: {self.dataname} data is None.")
            return
        
        for datablock in self.datalist:
            npcprops: set[PropData] = set()
            propdata = datablock.get("props")
            for propdata in propdata:
                prop = PropDataProxy(propdata.get("name"))
                npcprops.add(prop)

            # NPC核心数据
            npcblock = datablock.get("npc")
            npcname = npcblock.get("name")
            npcdata = data_base_system.get_npc(npcname)
            if npcdata is None:
                logger.error(f"NPCBuilder2: {npcname} not found in database.")
                continue
            # 连接
            npcdata.props = npcprops
            #
            self.npcs.append(npcdata)
########################################################################################################################
########################################################################################################################
########################################################################################################################





        