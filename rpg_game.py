from typing import List, Optional
from entitas import Processors #type: ignore
from loguru import logger
from auxiliary.components import (
    WorldComponent,
    StageComponent, 
    NPCComponent, 
    PlayerComponent, 
    SimpleRPGRoleComponent, 
    # PropComponent,
    # UniquePropComponent,
    #BackpackComponent,
    StageEntryConditionComponent,
    StageExitConditionComponent,
    DirectorComponent)
from auxiliary.actor_agent import ActorAgent
from auxiliary.extended_context import ExtendedContext
from auxiliary.world_data_builder import WorldDataBuilder, AdminNpcBuilder, StageBuilder, PlayerNpcBuilder, NpcBuilder
from entitas.entity import Entity
from systems.init_system import InitSystem
from systems.stage_plan_system import StagePlanSystem
from systems.npc_plan_system import NPCPlanSystem
from systems.speak_action_system import SpeakActionSystem
from systems.fight_action_system import FightActionSystem
from systems.leave_for_action_system import LeaveForActionSystem
from systems.director_system import DirectorSystem
from systems.dead_action_system import DeadActionSystem
from systems.destroy_system import DestroySystem
from systems.tag_action_system import TagActionSystem
from systems.data_save_system import DataSaveSystem
from systems.broadcast_action_system import BroadcastActionSystem  
from systems.whisper_action_system import WhisperActionSystem 
from systems.search_props_system import SearchPropsSystem
from systems.mind_voice_action_system import MindVoiceActionSystem
from director import Director
from auxiliary.world_data_builder import Prop
from auxiliary.file_system import FileSystem, PropFile

class RPGGame:

    def __init__(self, name: str) -> None:
        self.name = name
        self.extendedcontext: ExtendedContext = ExtendedContext()
        self.processors: Processors = Processors()
        self.started: bool = False
        self.inited: bool = False
        self.worlddata: Optional[WorldDataBuilder] = None
        ### 做一些初始化
        self.createprocessors()
###############################################################################################################################################
    def createprocessors(self) -> None:
        processors = self.processors
        context = self.extendedcontext

        #初始化系统########################
        processors.add(InitSystem(context))


        #规划逻辑########################
        # processors.add(StagePlanSystem(context))
        # processors.add(NPCPlanSystem(context))
        # #行动逻辑########################
        # processors.add(TagActionSystem(context))
        # processors.add(MindVoiceActionSystem(context))
        # processors.add(WhisperActionSystem(context))
        # processors.add(BroadcastActionSystem(context))
        # processors.add(SpeakActionSystem(context))
        # #死亡必须是战斗之后，因为如果死了就不能离开###############
        # processors.add(FightActionSystem(context))
        # processors.add(DeadActionSystem(context)) 
        # #########################################
        # # 处理搜寻道具行为
        # processors.add(SearchPropsSystem(context))
        # # 处理离开并去往的行为
        # processors.add(LeaveForActionSystem(context))
        # #行动结束后导演
        # processors.add(DirectorSystem(context))
        #########################################


        ###必须最后
        processors.add(DestroySystem(context))
       
       # processors.add(DataSaveSystem(context))
###############################################################################################################################################
    def createworld(self, worlddata: WorldDataBuilder) -> None:
        if worlddata is None or worlddata.data is None:
            logger.error("没有WorldBuilder数据，请检查World.json配置。")
            return
        
        ## 必须最先调用
        self.worlddata = worlddata
        self.extendedcontext.memory_system.set_root_path(worlddata.runtimepath)
        self.extendedcontext.file_system.set_root_path(worlddata.runtimepath)

        ### 创建实体
        adminnpcs = self.create_admin_npc_entities(worlddata.admin_npc_builder)
        playernpcs = self.create_player_npc_entities(worlddata.player_npc_builder)
        npcs = self.create_npc_entities(worlddata.npc_buidler)
        stages = self.create_stage_entities(worlddata.stage_builder)
###############################################################################################################################################
    def execute(self) -> None:
        #顺序不要动！！！！！！！！！
        if not self.inited:
            self.inited = True
            self.processors.activate_reactive_processors()
            self.processors.initialize()
        
        self.processors.execute()
        self.processors.cleanup()
        self.started = True
###############################################################################################################################################
    def exit(self) -> None:
        self.processors.clear_reactive_processors()
        self.processors.tear_down()
        logger.info(f"{self.name}, game over")
###############################################################################################################################################
    def create_admin_npc_entities(self, admin_npc_builder: AdminNpcBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        res: List[Entity] = []
        
        if context is None or admin_npc_builder.data is None:
            logger.error("没有AdminNpcBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in admin_npc_builder.npcs:
            worldentity = context.create_entity()
            res.append(worldentity)

            worldentity.add(WorldComponent, builddata.name)
            logger.debug(f"创建World Entity = {builddata.name}")

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)
            
        return res
###############################################################################################################################################
    def create_player_npc_entities(self, player_npc_builder: PlayerNpcBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        res: List[Entity] = []

        if player_npc_builder.data is None:
            logger.error("没有PlayerNpcBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in player_npc_builder.npcs:
            playernpcentity = context.create_entity()
            res.append(playernpcentity)

            playernpcentity.add(PlayerComponent, "player") 
            playernpcentity.add(SimpleRPGRoleComponent, builddata.name, 10000, 10000, 10, "")
            playernpcentity.add(NPCComponent, builddata.name, "")
            #playernpcentity.add(BackpackComponent, builddata.name)

            #file_system.init_backpack_component(playernpcentity.get(BackpackComponent))
            logger.debug(f"创建Player npc：{builddata.name}")
            if len(builddata.props) > 0:
                for prop in builddata.props:
                    # file_system.add_content_into_backpack(playernpcentity.get(BackpackComponent), prop.name)
                    # logger.debug(f"{builddata.name}的背包中有：{prop.name}")

                    ## 重构
                    createpropfile = PropFile(prop.name, builddata.name, prop)
                    file_system.add_prop_file(createpropfile)

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)

        return res
###############################################################################################################################################
    def create_npc_entities(self, npc_builder: NpcBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        res: List[Entity] = []

        if npc_builder.data is None:
            logger.error("没有NpcBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npc_builder.npcs:
            npcentity = context.create_entity()
            res.append(npcentity)

            npcentity.add(NPCComponent, builddata.name, "")
            npcentity.add(SimpleRPGRoleComponent, builddata.name, 100, 100, 10, "")
            #npcentity.add(BackpackComponent, builddata.name)

            #file_system.init_backpack_component(npcentity.get(BackpackComponent))
            logger.debug(f"创建npc：{builddata.name}")
            if len(builddata.props) > 0:
                for prop in builddata.props:
                    # file_system.add_content_into_backpack(npcentity.get(BackpackComponent), prop.name)
                    # logger.debug(f"{builddata.name}的背包中有：{prop.name}")

                    ## 重构
                    createpropfile = PropFile(prop.name, builddata.name, prop)
                    file_system.add_prop_file(createpropfile)

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)
                
        return res
###############################################################################################################################################
    def create_stage_entities(self, stage_builder: StageBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        res: List[Entity] = []

        if stage_builder.data is None:
            logger.error("没有StageBuilder数据，请检查World.json配置。")
            return res
        
        # 创建stage相关配置
        for builddata in stage_builder.stages:

            stageentity = context.create_entity()
            stageentity.add(StageComponent, builddata.name, [])
            stageentity.add(DirectorComponent, builddata.name, Director(builddata.name)) ###
            stageentity.add(SimpleRPGRoleComponent, builddata.name, 10000, 10000, 1, "")
            #stageentity.add(BackpackComponent, builddata.name) ### 场景也可以有背包，容纳道具
            logger.debug(f"创建Stage：{builddata.name}")

            ## 重新设置npc和stage的关系
            for npc in builddata.npcs:
                if isinstance(npc, dict):
                    npcname = npc.get("name", "")

                    findnpcagain: Optional[Entity] = context.getnpc(npcname)
                    if findnpcagain is None:
                        continue
                    if findnpcagain.has(NPCComponent):
                        findnpcagain.replace(NPCComponent, npcname, builddata.name)
                        logger.debug(f"重新设置npc：{npcname}的stage为：{builddata.name}")

            # 场景内添加道具，如地图？？
            for unique_prop in builddata.props:
                #propentity = context.create_entity()
                # if isinstance(unique_prop, dict):
                #     prop_entity.add(UniquePropComponent, unique_prop.get("name"))
                #     logger.debug(f'创建道具：{unique_prop.get("name")}')
                # else:
                #     logger.error(f"道具配置错误：{unique_prop}")
                # propentity.add(PropComponent, unique_prop.name) # 是一个道具
                # propentity.add(UniquePropComponent, unique_prop.name) # 是一个唯一道具，不可复制。目前这么写是有问题的，所有道具都是唯一道具
                createpropfile = PropFile(unique_prop.name, builddata.name, unique_prop)
                file_system.add_prop_file(createpropfile)

            ## 创建入口条件和出口条件
            enter_condition_set = set()
            for enter_condition in builddata.entry_conditions:
                enter_condition_set.add(enter_condition.name)
            if len(enter_condition_set) > 0:
                stageentity.add(StageEntryConditionComponent, enter_condition_set)
                logger.debug(f"{builddata.name}的入口条件为：{enter_condition_set}")

            exit_condition_set = set()
            for exit_condition in builddata.exit_conditions:
                exit_condition_set.add(exit_condition.name)
            if len(exit_condition_set) > 0:
                stageentity.add(StageExitConditionComponent, set(exit_condition_set))
                logger.debug(f"{builddata.name}的出口条件为：{exit_condition_set}")

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)

        return res
###############################################################################################################################################

