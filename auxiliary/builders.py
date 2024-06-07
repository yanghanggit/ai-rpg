from typing import Any, Optional, List, Set, Dict
from loguru import logger
import json
from auxiliary.base_data import PropData, NPCData, StageData, NPCDataProxy, PropDataProxy
from auxiliary.data_base_system import DataBaseSystem

########################################################################################################################
########################################################################################################################
########################################################################################################################
class GameBuilder:

    def __init__(self, name: str, version: str, runtimepath: str, data_base_system: DataBaseSystem) -> None:
        self.name = name
        self.runtimepath = runtimepath
        self.version = version # version必须与生成的world.json文件中的version一致
        self._data: Any = None
        self.world_builder = NPCBuilder("worlds")
        self.player_builder = NPCBuilder("players")
        self.npc_buidler = NPCBuilder("npcs")
        self.stage_builder = StageBuilder()
        self.data_base_system = data_base_system ## 依赖注入的方式，将数据库系统注入到这里
        self.about_game: str = ""
###############################################################################################################################################
    def loadfile(self, world_data_path: str, check_version: bool) -> bool:
        try:
            with open(world_data_path, 'r', encoding="utf-8") as file:
                self._data = json.load(file)
                if self._data is None:
                    logger.error(f"File {world_data_path} is empty.")
                    return False
        except FileNotFoundError:
            logger.exception(f"File {world_data_path} not found.")
            return False
        
        if check_version:
            game_data_version: str = self._data['version']
            if self.version == game_data_version:
                return True
            else:
                logger.error(f'游戏数据(World.json)与Builder版本不匹配，请检查。')
                return False
        return True
###############################################################################################################################################
    def build(self) -> None:
        if self._data is None:
            logger.error("WorldDataBuilder: data is None.")
            return
        # 第一步，创建数据库
        self._create_data_base_system()
        # 第二步，创建配置
        self._build_config(self._data)
        # 第三步，创建世界级别的管理员
        self.world_builder.build(self._data, self.data_base_system)
        # 第四步，创建玩家与NPC
        self.player_builder.build(self._data, self.data_base_system)
        self.npc_buidler.build(self._data, self.data_base_system)
        # 第五步，创建场景
        self.stage_builder.build(self._data, self.data_base_system)
###############################################################################################################################################
    def _build_config(self, data: dict[str, Any]) -> None:
        self.about_game = data.get('about_game', "无关于游戏的信息。")
###############################################################################################################################################
    def _create_npc_data_base(self, npcs: Any) -> None:
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
            
            ## 设置（战斗）属性
            npc.build_attributes(npcdata.get("attributes"))
            self.data_base_system.add_npc(npc.name, npc)
###############################################################################################################################################
    def _create_stage_data_base(self, stages: Any) -> None:
        if stages is None:
            logger.error("没有场景数据内容(stages)，请检查World.json配置。")
            return
        
        for stage in stages:
            #print(stage)
            core_data = stage.get('stage', None)
            assert core_data is not None

            stage = StageData(core_data.get("name"), 
                            core_data.get("codename"), 
                            core_data.get("description"), 
                            core_data.get("url"), 
                            core_data.get("memory"), 
                            "", 
                            "", 
                            set(), 
                            set(),
                            "",
                            core_data.get('stage_entry_status'),
                            core_data.get('stage_entry_role_status'),
                            core_data.get('stage_entry_role_props'),
                            core_data.get('stage_exit_status'),
                            core_data.get('stage_exit_role_status'),
                            core_data.get('stage_exit_role_props'),
                            )
            
            # 做连接关系 目前仅用名字
            exit_of_portal_and_goto_stagename: str = core_data.get("exit_of_portal")
            if exit_of_portal_and_goto_stagename != "":
                stage.stage_as_exit_of_portal(exit_of_portal_and_goto_stagename)
            else:
                logger.debug(f"Stage {stage.name} has no exit_of_portal.")

            # 设置（战斗）属性
            stage.build_attributes(core_data.get("attributes"))

            # 添加到数据库
            self.data_base_system.add_stage(stage.name, stage)
###############################################################################################################################################
    def _create_prop_data_base(self, props: Any) -> None:
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
    def _create_data_base_system(self) -> None:
        database = self._data.get('database', None)
        if database is None:
            logger.error("没有数据库(database)，请检查World.json配置。")
            return
        self._create_npc_data_base(database.get('npcs', None))
        self._create_stage_data_base(database.get('stages', None))
        self._create_prop_data_base(database.get('props', None))
########################################################################################################################
class StageBuilder:
    def __init__(self) -> None:
        self.datalist: Optional[dict[str, Any]] = None
        self.stages: list[StageData] = []

    def __str__(self) -> str:
        return f"StageBuilder: {self.datalist}"      

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