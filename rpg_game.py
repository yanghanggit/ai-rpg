import os
from typing import List, Optional
from entitas import Processors, Matcher #type: ignore
from loguru import logger
from auxiliary.components import (
    WorldComponent,
    StageComponent, 
    ConnectToStageComponent,
    NPCComponent, 
    PlayerComponent, 
    SimpleRPGRoleComponent, 
    StageEntryConditionComponent,
    StageExitConditionComponent)
from auxiliary.extended_context import ExtendedContext
from auxiliary.builders import WorldDataBuilder, StageBuilder, NPCBuilder
from entitas.entity import Entity
from systems.init_system import InitSystem
from systems.npc_ready_for_planning_system import NPCReadyForPlanningSystem
from systems.stage_planning_system import StagePlanningSystem
from systems.npc_planning_system import NPCPlanningSystem
from systems.speak_action_system import SpeakActionSystem
from systems.fight_action_system import FightActionSystem
from systems.leave_for_action_system import LeaveForActionSystem
from systems.pre_leave_for_system import PreLeaveForSystem
from systems.director_system import DirectorSystem
from systems.dead_action_system import DeadActionSystem
from systems.destroy_system import DestroySystem
from systems.stage_ready_for_planning_system import StageReadyForPlanningSystem
from systems.tag_action_system import TagActionSystem
from systems.data_save_system import DataSaveSystem
from systems.broadcast_action_system import BroadcastActionSystem  
from systems.whisper_action_system import WhisperActionSystem 
from systems.search_action_system import SearchActionSystem
from systems.mind_voice_action_system import MindVoiceActionSystem
from auxiliary.director_component import DirectorComponent
from auxiliary.file_def import PropFile, KnownNPCFile
from systems.begin_system import BeginSystem
from systems.end_system import EndSystem
import shutil
from systems.pre_planning_system import PrePlanningSystem
from systems.post_planning_system import PostPlanningSystem
from systems.pre_action_system import PreActionSystem
from systems.post_action_system import PostActionSystem
from systems.post_fight_system import PostFightSystem
from systems.known_information_system import KnownInformationSystem
from systems.prison_break_action_system import PrisonBreakActionSystem
from systems.perception_action_system import PerceptionActionSystem
from systems.steal_action_system import StealActionSystem
from systems.trade_action_system import TradeActionSystem
from systems.check_status_action_system import CheckStatusActionSystem
from base_game import BaseGame
from systems.post_conversational_action_system import PostConversationalActionSystem

## 控制流程和数据创建
class RPGGame(BaseGame):

    def __init__(self, name: str, context: ExtendedContext) -> None:
        super().__init__(name)
        # 不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
        self.extendedcontext: ExtendedContext = context
        self.worlddata: Optional[WorldDataBuilder] = None
        self.processors: Processors = self.createprocessors(self.extendedcontext)
###############################################################################################################################################
    def createprocessors(self, context: ExtendedContext) -> Processors:

        processors = Processors()
       
        ##调试用的系统。监视进入运行之前的状态
        processors.add(BeginSystem(context))
        
        #初始化系统########################
        processors.add(InitSystem(context))
       
        #规划逻辑########################
        processors.add(PrePlanningSystem(context)) ######## 在所有规划之前
        processors.add(StageReadyForPlanningSystem(context))
        processors.add(StagePlanningSystem(context))
        processors.add(NPCReadyForPlanningSystem(context))
        processors.add(NPCPlanningSystem(context))
        processors.add(PostPlanningSystem(context)) ####### 在所有规划之后

        #用户拿到相关的信息，并开始操作与输入!!!!!!!
        from systems.test_player_input_system import TestPlayerInputSystem ### 不这样就循环引用
        processors.add(TestPlayerInputSystem(context, self)) 

        #行动逻辑########################
        processors.add(PreActionSystem(context)) ######## 在所有行动之前 #########################################

        #获取状态与查找信息类的行为
        processors.add(CheckStatusActionSystem(context))
        processors.add(PerceptionActionSystem(context))

        #交流（与说话类）的行为
        processors.add(TagActionSystem(context))
        processors.add(MindVoiceActionSystem(context))
        processors.add(WhisperActionSystem(context))
        processors.add(BroadcastActionSystem(context))
        processors.add(SpeakActionSystem(context))
        processors.add(PostConversationalActionSystem(context))

        #战斗类的行为
        processors.add(FightActionSystem(context)) 
        processors.add(PostFightSystem(context))
        processors.add(DeadActionSystem(context)) 
        
        #交互类的行为，在死亡之后，因为死了就不能执行
        processors.add(SearchActionSystem(context)) 
        processors.add(StealActionSystem(context))
        processors.add(TradeActionSystem(context))

        #场景切换类行为，非常重要而且必须在最后
        processors.add(PrisonBreakActionSystem(context)) 
        processors.add(PreLeaveForSystem(context)) 
        processors.add(LeaveForActionSystem(context))

        processors.add(PostActionSystem(context)) ####### 在所有行动之后 #########################################
        #########################################

        #行动结束后导演
        processors.add(DirectorSystem(context))
        #行动结束后更新关系网
        processors.add(KnownInformationSystem(context))
        #########################################

        ###最后删除entity与存储数据
        processors.add(DestroySystem(context))
        processors.add(DataSaveSystem(context))

         ##调试用的系统。监视进入运行之后的状态
        processors.add(EndSystem(context))

        return processors
###############################################################################################################################################
    def createworld(self, worlddata: WorldDataBuilder) -> None:
        if worlddata is None or worlddata.data is None:
            logger.error("没有WorldBuilder数据，请检查World.json配置。")
            return
        
        context = self.extendedcontext
        chaos_engineering_system = context.chaos_engineering_system
        
        ## 实际运行的路径
        runtime_dir_for_world = f"{worlddata.runtimepath}{worlddata.name}/"

        # 第0步，yh 目前用于测试!!!!!!!，直接删worlddata.name的文件夹，保证每次都是新的 删除runtime_dir_for_world的文件夹
        if os.path.exists(runtime_dir_for_world):
            shutil.rmtree(runtime_dir_for_world)

        # 混沌系统，准备测试
        chaos_engineering_system.on_pre_create_world(context, worlddata)

        ## 第一步，设置根路径
        self.worlddata = worlddata
        context.agent_connect_system.set_root_path(runtime_dir_for_world)
        context.memory_system.set_root_path(runtime_dir_for_world)
        context.file_system.set_root_path(runtime_dir_for_world)

        ### 第二步 创建实体
        self.create_world_npc_entities(worlddata.world_npc_builder)
        self.create_player_npc_entities(worlddata.player_npc_builder)
        self.create_npc_entities(worlddata.npc_buidler)
        self.add_code_name_component_to_world_and_npcs_when_build()

        ### 第三步，创建stage
        self.create_stage_entities(worlddata.stage_builder)
        
        ## 第四步，最后处理因为需要上一阶段的注册流程
        self.add_code_name_component_stages_when_build()

        ## 混沌系统，准备测试
        chaos_engineering_system.on_post_create_world(context, worlddata)
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
    def create_world_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        code_name_component_system = context.code_name_component_system
        file_system = context.file_system

        res: List[Entity] = []
        
        if npcbuilder.datalist is None:
            raise ValueError("没有WorldNPCBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npcbuilder.npcs:
            #logger.debug(f"创建World Entity = {builddata.name}")
            worldentity = context.create_entity()
            res.append(worldentity)

            #必要组件
            worldentity.add(WorldComponent, builddata.name)

            #故意不加NPC组件！！

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.initmemory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)

            # 最后构建关系网
            for knownnpc in builddata.mentioned_npcs:
                create_known_npc_file = KnownNPCFile(knownnpc, builddata.name, knownnpc)
                file_system.add_known_npc_file(create_known_npc_file)
            
        return res
###############################################################################################################################################
    def create_player_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system
        res: List[Entity] = []

        if npcbuilder.datalist is None:
            raise ValueError("没有PlayerNPCBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npcbuilder.npcs:
            #logger.debug(f"创建Player npc：{builddata.name}")
            playernpcentity = context.create_entity()
            res.append(playernpcentity)

            #必要组件
            playernpcentity.add(PlayerComponent, "") ##此时没有被玩家控制
            playernpcentity.add(SimpleRPGRoleComponent, builddata.name, builddata.attributes[0], builddata.attributes[1], builddata.attributes[2])
            playernpcentity.add(NPCComponent, builddata.name, "")
            
            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.initmemory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)
           
            # 添加道具
            for prop in builddata.props:
                ## 重构
                createpropfile = PropFile(prop.name, builddata.name, prop)
                file_system.add_prop_file(createpropfile)
                code_name_component_system.register_code_name_component_class(prop.name, prop.codename)

            # 最后构建关系网
            for knownnpc in builddata.mentioned_npcs:
                create_known_npc_file = KnownNPCFile(knownnpc, builddata.name, knownnpc)
                file_system.add_known_npc_file(create_known_npc_file)

        return res
###############################################################################################################################################
    def create_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system
        res: List[Entity] = []

        if npcbuilder.datalist is None:
            raise ValueError("没有NPCBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in npcbuilder.npcs:
            #logger.debug(f"创建npc：{builddata.name}")
            npcentity = context.create_entity()
            res.append(npcentity)

            # 必要组件
            npcentity.add(NPCComponent, builddata.name, "")
            npcentity.add(SimpleRPGRoleComponent, builddata.name, builddata.attributes[0], builddata.attributes[1], builddata.attributes[2])
       
            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.initmemory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)
            
            # 添加道具
            for prop in builddata.props:
                ## 重构
                createpropfile = PropFile(prop.name, builddata.name, prop)
                file_system.add_prop_file(createpropfile)
                code_name_component_system.register_code_name_component_class(prop.name, prop.codename)

            # 最后构建关系网
            for knownnpc in builddata.mentioned_npcs:
                create_known_npc_file = KnownNPCFile(knownnpc, builddata.name, knownnpc)
                file_system.add_known_npc_file(create_known_npc_file)

        return res
###############################################################################################################################################
    def create_stage_entities(self, stagebuilder: StageBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system
        res: List[Entity] = []

        if stagebuilder.datalist is None:
            raise ValueError("没有StageBuilder数据，请检查World.json配置。")
            return res
        
        # 创建stage相关配置
        for builddata in stagebuilder.stages:
            #logger.debug(f"创建Stage：{builddata.name}")
            stageentity = context.create_entity()

            #必要组件
            stageentity.add(StageComponent, builddata.name)
            stageentity.add(DirectorComponent, builddata.name) ###
            stageentity.add(SimpleRPGRoleComponent, builddata.name, builddata.attributes[0], builddata.attributes[1], builddata.attributes[2])
    
            ## 重新设置npc和stage的关系
            for npc in builddata.npcs:
                npcname = npc.name
                findnpcagain: Optional[Entity] = context.getnpc(npcname)
                if findnpcagain is None:
                    #logger.error(f"没有找到npc：{npcname}！！！！！！！！！")
                    raise ValueError(f"没有找到npc：{npcname}！！！！！！！！！")
                    continue

                ## 重新设置npc的stage，做覆盖处理
                findnpcagain.replace(NPCComponent, npcname, builddata.name)
                #logger.debug(f"重新设置npc：{npcname}的stage为：{builddata.name}")
                    
            # 场景内添加道具
            for propinstage in builddata.props:
                # 直接使用文件系统
                createpropfile = PropFile(propinstage.name, builddata.name, propinstage)
                file_system.add_prop_file(createpropfile)
                code_name_component_system.register_code_name_component_class(propinstage.name, propinstage.codename)

            ## 创建入口条件
            enter_condition_set = set()
            for enter_condition in builddata.entry_conditions:
                enter_condition_set.add(enter_condition.name)
            if len(enter_condition_set) > 0:
                stageentity.add(StageEntryConditionComponent, enter_condition_set)
                #logger.debug(f"{builddata.name}的入口条件为：{enter_condition_set}")

            ## 创建出口条件
            exit_condition_set = set()
            for exit_condition in builddata.exit_conditions:
                exit_condition_set.add(exit_condition.name)
            if len(exit_condition_set) > 0:
                stageentity.add(StageExitConditionComponent, set(exit_condition_set))
                #logger.debug(f"{builddata.name}的出口条件为：{exit_condition_set}")

            ## 创建连接的场景用于PrisonBreakActionSystem
            for connectstage in builddata.connect_to_stage:
                stageentity.add(ConnectToStageComponent, connectstage.name)
                #logger.debug(f"{builddata.name}连接的场景为：{connectstage.name}, 用于PrisonBreakActionSystem使用。")
                break ### 就用第一个

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.initmemory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)
            code_name_component_system.register_stage_tag_component_class(builddata.name, builddata.codename)

        return res
###############################################################################################################################################
    def add_code_name_component_to_world_and_npcs_when_build(self) -> None:
        context = self.extendedcontext
        code_name_component_system = context.code_name_component_system

        #
        worldentities = context.get_group(Matcher(WorldComponent)).entities
        for entity in worldentities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            codecompclass = code_name_component_system.get_component_class_by_name(worldcomp.name)
            if codecompclass is not None:
                entity.add(codecompclass, worldcomp.name)

        #
        npcsentities = context.get_group(Matcher(NPCComponent)).entities
        for entity in npcsentities:
            npccomp: NPCComponent = entity.get(NPCComponent)
            codecompclass = code_name_component_system.get_component_class_by_name(npccomp.name)
            if codecompclass is not None:
                entity.add(codecompclass, npccomp.name)
###############################################################################################################################################
    def add_code_name_component_stages_when_build(self) -> None:
        context = self.extendedcontext
        code_name_component_system = context.code_name_component_system

        ## 重新设置npc和stage的关系
        npcsentities = context.get_group(Matcher(NPCComponent)).entities
        for entity in npcsentities:
            npccomp: NPCComponent = entity.get(NPCComponent)
            context.change_stage_tag_component(entity, "", npccomp.current_stage)

        ## 重新设置stage和stage的关系
        stagesentities = context.get_group(Matcher(StageComponent)).entities
        for entity in stagesentities:
            stagecomp: StageComponent = entity.get(StageComponent)
            codecompclass = code_name_component_system.get_component_class_by_name(stagecomp.name)
            if codecompclass is not None:
                entity.add(codecompclass, stagecomp.name)
###############################################################################################################################################
        

