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
    StageExitConditionComponent)
from auxiliary.actor_agent import ActorAgent
from auxiliary.extended_context import ExtendedContext
from auxiliary.builders import WorldDataBuilder, StageBuilder, NPCBuilder
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
from director_component import DirectorComponent
#from auxiliary.world_data_builder import Prop
from auxiliary.file_system import PropFile

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




        #"""
        #规划逻辑########################
        processors.add(StagePlanSystem(context))
        processors.add(NPCPlanSystem(context))
        #行动逻辑########################
        processors.add(TagActionSystem(context))
        processors.add(MindVoiceActionSystem(context))
        processors.add(WhisperActionSystem(context))
        processors.add(BroadcastActionSystem(context))
        processors.add(SpeakActionSystem(context))
        #死亡必须是战斗之后，因为如果死了就不能离开###############
        processors.add(FightActionSystem(context))
        processors.add(DeadActionSystem(context)) 
        #########################################
        # 处理搜寻道具行为
        processors.add(SearchPropsSystem(context))
        # 处理离开并去往的行为
        processors.add(LeaveForActionSystem(context))
        #行动结束后导演
        processors.add(DirectorSystem(context))
        #########################################
        #"""



        ###必须最后
        processors.add(DestroySystem(context))
        processors.add(DataSaveSystem(context))
###############################################################################################################################################
    def createworld(self, worlddata: WorldDataBuilder) -> None:
        if worlddata is None or worlddata.data is None:
            logger.error("没有WorldBuilder数据，请检查World.json配置。")
            return
        
        ## 必须最先调用 './budding_world/gen_runtimes/'
        self.worlddata = worlddata
        self.extendedcontext.memory_system.set_root_path(f"{worlddata.runtimepath}{worlddata.name}/")
        self.extendedcontext.file_system.set_root_path(f"{worlddata.runtimepath}{worlddata.name}/")

        ### 创建实体
        self.create_admin_npc_entities(worlddata.admin_npc_builder)
        self.create_player_npc_entities(worlddata.player_npc_builder)
        self.create_npc_entities(worlddata.npc_buidler)
        self.create_stage_entities(worlddata.stage_builder)
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
    def create_admin_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        res: List[Entity] = []
        
        if npcbuilder.datalist is None:
            raise ValueError("没有AdminNPCBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npcbuilder.npcs:
            logger.debug(f"创建World Entity = {builddata.name}")
            worldentity = context.create_entity()
            res.append(worldentity)

            #必要组件
            worldentity.add(WorldComponent, builddata.name)

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)
            
        return res
###############################################################################################################################################
    def create_player_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        res: List[Entity] = []

        if npcbuilder.datalist is None:
            raise ValueError("没有PlayerNPCBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npcbuilder.npcs:
            logger.debug(f"创建Player npc：{builddata.name}")
            playernpcentity = context.create_entity()
            res.append(playernpcentity)

            #必要组件
            playernpcentity.add(PlayerComponent, "player") 
            playernpcentity.add(SimpleRPGRoleComponent, builddata.name, 10000, 10000, 10, "")
            playernpcentity.add(NPCComponent, builddata.name, "")
            
            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)
            for prop in builddata.props:
                ## 重构
                createpropfile = PropFile(prop.name, builddata.name, prop)
                file_system.add_prop_file(createpropfile)

        return res
###############################################################################################################################################
    def create_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        res: List[Entity] = []

        if npcbuilder.datalist is None:
            raise ValueError("没有NPCBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npcbuilder.npcs:
            logger.debug(f"创建npc：{builddata.name}")
            npcentity = context.create_entity()
            res.append(npcentity)

            # 必要组件
            npcentity.add(NPCComponent, builddata.name, "")
            npcentity.add(SimpleRPGRoleComponent, builddata.name, 100, 100, 10, "")
       
            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.readmemory(builddata.name, builddata.memory)
            for prop in builddata.props:
                ## 重构
                createpropfile = PropFile(prop.name, builddata.name, prop)
                file_system.add_prop_file(createpropfile)
        return res
###############################################################################################################################################
    def create_stage_entities(self, stagebuilder: StageBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        res: List[Entity] = []

        if stagebuilder.datalist is None:
            raise ValueError("没有StageBuilder数据，请检查World.json配置。")
            return res
        
        # 创建stage相关配置
        for builddata in stagebuilder.stages:
            logger.debug(f"创建Stage：{builddata.name}")
            stageentity = context.create_entity()

            #必要组件
            stageentity.add(StageComponent, builddata.name, [])
            stageentity.add(DirectorComponent, builddata.name) ###
            stageentity.add(SimpleRPGRoleComponent, builddata.name, 10000, 10000, 1, "")
            
            ## 重新设置npc和stage的关系
            for npc in builddata.npcs:
                npcname = npc.name
                findnpcagain: Optional[Entity] = context.getnpc(npcname)
                if findnpcagain is None:
                    logger.error(f"没有找到npc：{npcname}")
                    continue

                ## 重新设置npc的stage，做覆盖处理
                findnpcagain.replace(NPCComponent, npcname, builddata.name)
                logger.debug(f"重新设置npc：{npcname}的stage为：{builddata.name}")
                    
            # 场景内添加道具
            for propinstage in builddata.props:
                # 直接使用文件系统
                createpropfile = PropFile(propinstage.name, builddata.name, propinstage)
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

