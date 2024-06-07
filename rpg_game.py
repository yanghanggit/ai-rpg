import os
from typing import List, Optional

from overrides import override
from entitas import Matcher #type: ignore
from loguru import logger
from auxiliary.components import (
    WorldComponent,
    StageComponent, 
    ExitOfPortalComponent,
    ActorComponent, 
    PlayerComponent, 
    SimpleRPGRoleComponent, 
    AppearanceComponent,
    StageExitCondStatusComponent,
    StageExitCondCheckRoleStatusComponent,
    StageExitCondCheckRolePropsComponent,
    StageEntryCondStatusComponent,
    StageEntryCondCheckRoleStatusComponent,
    StageEntryCondCheckRolePropsComponent,
    )
from auxiliary.extended_context import ExtendedContext
from auxiliary.builders import GameBuilder, StageBuilder, NPCBuilder
from entitas.entity import Entity
from systems.init_memory_system import InitMemorySystem
from systems.npc_ready_for_planning_system import NPCReadyForPlanningSystem
from systems.stage_planning_system import StagePlanningSystem
from systems.npc_planning_system import NPCPlanningSystem
from systems.speak_action_system import SpeakActionSystem
from systems.attack_action_system import AttackActionSystem
from systems.leave_for_action_system import LeaveForActionSystem
from systems.pre_leave_for_system import PreLeaveForSystem
from systems.director_system import DirectorSystem
from systems.destroy_system import DestroySystem
from systems.stage_ready_for_planning_system import StageReadyForPlanningSystem
from systems.tag_action_system import TagActionSystem
#from systems.data_save_system import DataSaveSystem
from systems.broadcast_action_system import BroadcastActionSystem  
from systems.use_prop_action_system import UsePropActionSystem
from systems.whisper_action_system import WhisperActionSystem 
from systems.search_action_system import SearchActionSystem
from systems.mind_voice_action_system import MindVoiceActionSystem
from auxiliary.director_component import StageDirectorComponent
from auxiliary.file_def import PropFile
from systems.begin_system import BeginSystem
from systems.end_system import EndSystem
import shutil
from systems.pre_planning_system import PrePlanningSystem
from systems.post_planning_system import PostPlanningSystem
from systems.pre_action_system import PreActionSystem
from systems.post_action_system import PostActionSystem
from systems.post_fight_system import PostFightSystem
from systems.update_archive_system import UpdateArchiveSystem
from systems.portal_step_action_system import PortalStepActionSystem
from systems.perception_action_system import PerceptionActionSystem
from systems.steal_action_system import StealActionSystem
from systems.trade_action_system import TradeActionSystem
from systems.check_status_action_system import CheckStatusActionSystem
from base_game import BaseGame
from systems.init_agents_system import InitAgentsSystem
from auxiliary.file_system_helper import add_npc_archive_files
from systems.my_processors import MyProcessors
from systems.simple_rpg_role_pre_fight_system import SimpleRPGRolePreFightSystem
from systems.update_client_message_system import UpdateClientMessageSystem
from systems.terminal_player_interrupt_and_wait_system import TerminalPlayerInterruptAndWaitSystem
from systems.compress_chat_history_system import CompressChatHistorySystem
from systems.terminal_player_input_system import TerminalPlayerInputSystem
from systems.post_conversation_action_system import PostConversationActionSystem
from auxiliary.base_data import StageData



## RPG 的测试类游戏
## 尽量不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
class RPGGame(BaseGame):

    def __init__(self, name: str, context: ExtendedContext) -> None:
        super().__init__(name)
        self.extendedcontext: ExtendedContext = context
        self.builder: Optional[GameBuilder] = None
        self.processors: MyProcessors = self.create_processors(self.extendedcontext)
###############################################################################################################################################
    def create_processors(self, context: ExtendedContext) -> MyProcessors:

        processors = MyProcessors()
       
        ##调试用的系统。监视进入运行之前的状态
        processors.add(BeginSystem(context))
        
        #初始化系统########################
        processors.add(InitAgentsSystem(context)) ### 连接所有agent
        processors.add(InitMemorySystem(context)) ### 第一次读状态, initmemory
        #########################################

        # 处理用户输入
        from systems.handle_player_input_system import HandlePlayerInputSystem ### 不这样就循环引用
        processors.add(HandlePlayerInputSystem(context, self)) 

        # 行动逻辑################################################################################################
        processors.add(PreActionSystem(context)) ######## 在所有行动之前 #########################################

        #交流（与说话类）的行为
        processors.add(TagActionSystem(context))
        processors.add(MindVoiceActionSystem(context))
        processors.add(WhisperActionSystem(context))
        processors.add(BroadcastActionSystem(context))
        processors.add(SpeakActionSystem(context))

        # 这里必须在所有对话之后，目前是防止用户用对话行为说出不符合政策的话
        processors.add(PostConversationActionSystem(context))

        #战斗类的行为 ##########
        processors.add(SimpleRPGRolePreFightSystem(context)) #战斗之前需要更新装备
        processors.add(AttackActionSystem(context)) 
        processors.add(PostFightSystem(context))

        ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。
        from systems.dead_action_system import DeadActionSystem
        processors.add(DeadActionSystem(context, self)) 
        
        # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行。。。
        processors.add(SearchActionSystem(context)) 
        processors.add(StealActionSystem(context))
        processors.add(TradeActionSystem(context))
        processors.add(UsePropActionSystem(context))
        processors.add(CheckStatusActionSystem(context)) # 道具交互类行为之后，可以发起自检

        # 场景切换类行为，非常重要而且必须在最后
        processors.add(PortalStepActionSystem(context)) 
        processors.add(PreLeaveForSystem(context)) 
        processors.add(LeaveForActionSystem(context))
        processors.add(PerceptionActionSystem(context)) # 场景切换类行为之后可以发起感知

        processors.add(PostActionSystem(context)) ####### 在所有行动之后 #########################################
        #########################################

        #行动结束后导演
        processors.add(DirectorSystem(context))
        #行动结束后更新关系网，因为依赖Director所以必须在后面
        processors.add(UpdateArchiveSystem(context))

        ###最后删除entity与存储数据
        processors.add(DestroySystem(context))
        #processors.add(DataSaveSystem(context))

        ##测试的系统，移除掉不太重要的提示词，例如一些上行命令的。
        processors.add(CompressChatHistorySystem(context)) ## 测试的系统
        ##调试用的系统。监视进入运行之后的状态
        processors.add(EndSystem(context))

        # 开发专用，网页版本不需要
        processors.add(TerminalPlayerInterruptAndWaitSystem(context))
        #########################################

        #规划逻辑########################
        processors.add(PrePlanningSystem(context)) ######## 在所有规划之前
        processors.add(StageReadyForPlanningSystem(context))
        processors.add(StagePlanningSystem(context))
        processors.add(NPCReadyForPlanningSystem(context))
        processors.add(NPCPlanningSystem(context))
        processors.add(PostPlanningSystem(context)) ####### 在所有规划之后

        ## 第一次抓可以被player看到的信息
        processors.add(UpdateClientMessageSystem(context)) 

        ## 开发专用，网页版本不需要
        processors.add(TerminalPlayerInputSystem(context, self))
        
        return processors
###############################################################################################################################################
    def create_game(self, worlddata: GameBuilder) -> None:
        assert worlddata is not None
        assert worlddata._data is not None
        # if worlddata is None or worlddata._data is None:
        #     logger.error("没有WorldBuilder数据，请检查World.json配置。")
        #     return
        
        context = self.extendedcontext
        chaos_engineering_system = context.chaos_engineering_system
        
        ## 实际运行的路径
        runtime_dir_for_world = f"{worlddata.runtimepath}{worlddata.name}/"

        # 第0步，yh 目前用于测试!!!!!!!，直接删worlddata.name的文件夹，保证每次都是新的 删除runtime_dir_for_world的文件夹
        if os.path.exists(runtime_dir_for_world):
            shutil.rmtree(runtime_dir_for_world)

        # 混沌系统，准备测试
        chaos_engineering_system.on_pre_create_game(context, worlddata)

        ## 第1步，设置根路径
        self.builder = worlddata
        context.agent_connect_system.set_root_path(runtime_dir_for_world)
        context.kick_off_memory_system.set_root_path(runtime_dir_for_world)
        context.file_system.set_root_path(runtime_dir_for_world)

        ## 第2步 创建管理员类型的角色，全局的AI
        self.create_world_entities(worlddata.world_builder)

        ## 第3步，创建NPC，player是特殊的NPC
        self.create_player_entities(worlddata.player_builder)
        self.create_npc_entities(worlddata.npc_buidler)
        self.add_code_name_component_to_world_and_npcs()

        ## 第4步，创建stage
        self.create_stage_entities(worlddata.stage_builder)
        
        ## 第5步，最后处理因为需要上一阶段的注册流程
        self.add_code_name_component_stages()

        ## 最后！混沌系统，准备测试
        chaos_engineering_system.on_post_create_game(context, worlddata)
###############################################################################################################################################
    @override
    def execute(self) -> None:
        self.started = True

        #顺序不要动！！！！！！！！！
        if not self.inited:
            self.inited = True
            self.processors.activate_reactive_processors()
            self.processors.initialize()
        
        self.processors.execute()
        self.processors.cleanup()
###############################################################################################################################################
    @override
    async def async_execute(self) -> None:
        self.started = True

        #顺序不要动！！！！！！！！！
        if not self.inited:
            self.inited = True
            self.processors.activate_reactive_processors()
            self.processors.initialize()
        
        await self.processors.async_execute()
        self.processors.cleanup()
###############################################################################################################################################
    @override
    def exit(self) -> None:
        self.processors.clear_reactive_processors()
        self.processors.tear_down()
        logger.info(f"{self.name}, game over")
###############################################################################################################################################
    def create_world_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
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
            logger.info(f"创建World Entity = {builddata.name}, 故意不加NPC组件")

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.add_kick_off_memory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)

            # 初步建立关系网（在编辑文本中提到的NPC名字）
            add_npc_archive_files(file_system, builddata.name, builddata.npc_names_mentioned_during_editing_or_for_agent)
            
        return res
###############################################################################################################################################
    def create_player_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:
        # 创建player 本质就是创建NPC
        create_result = self.create_npc_entities(npcbuilder)
        for entity in create_result:
            npccomp: ActorComponent = entity.get(ActorComponent)
            logger.info(f"创建Player Entity = {npccomp.name}")
            entity.add(PlayerComponent, "")
        return create_result
###############################################################################################################################################
    def create_npc_entities(self, npcbuilder: NPCBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
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
            npcentity.add(ActorComponent, builddata.name, "")
            npcentity.add(SimpleRPGRoleComponent, builddata.name, builddata.attributes[0], builddata.attributes[1], builddata.attributes[2], builddata.attributes[3])
            npcentity.add(AppearanceComponent, builddata.role_appearance)

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.add_kick_off_memory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)
            
            # 添加道具
            for prop_proxy in builddata.props:
                ## 重构
                prop_data_from_data_base = context.data_base_system.get_prop(prop_proxy.name)
                if prop_data_from_data_base is None:
                    logger.error(f"没有从数据库找到道具：{prop_proxy.name}！！！！！！！！！")
                    continue
            
                create_prop_file = PropFile(prop_proxy.name, builddata.name, prop_data_from_data_base)
                file_system.add_prop_file(create_prop_file)
                code_name_component_system.register_code_name_component_class(prop_data_from_data_base.name, prop_data_from_data_base.codename)

            # 初步建立关系网（在编辑文本中提到的NPC名字）
            add_npc_archive_files(file_system, builddata.name, builddata.npc_names_mentioned_during_editing_or_for_agent)

        return res
###############################################################################################################################################
    def create_stage_entities(self, stagebuilder: StageBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
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
            stageentity.add(StageDirectorComponent, builddata.name) ###
            stageentity.add(SimpleRPGRoleComponent, builddata.name, builddata.attributes[0], builddata.attributes[1], builddata.attributes[2], builddata.attributes[3])
    
            ## 重新设置npc和stage的关系
            for npc in builddata.npcs:
                npcname = npc.name
                findnpcagain: Optional[Entity] = context.getnpc(npcname)
                if findnpcagain is None:
                    #logger.error(f"没有找到npc：{npcname}！！！！！！！！！")
                    raise ValueError(f"没有找到npc：{npcname}！！！！！！！！！")
                    continue

                ## 重新设置npc的stage，做覆盖处理
                findnpcagain.replace(ActorComponent, npcname, builddata.name)
                #logger.debug(f"重新设置npc：{npcname}的stage为：{builddata.name}")
                    
            # 场景内添加道具
            for prop_proxy_in_stage in builddata.props:
                # 直接使用文件系统
                prop_data_from_data_base = context.data_base_system.get_prop(prop_proxy_in_stage.name)
                if prop_data_from_data_base is None:
                    logger.error(f"没有从数据库找到道具：{prop_proxy_in_stage.name}！！！！！！！！！")
                    continue
                create_prop_file = PropFile(prop_proxy_in_stage.name, builddata.name, prop_data_from_data_base)
                file_system.add_prop_file(create_prop_file)
                code_name_component_system.register_code_name_component_class(prop_data_from_data_base.name, prop_data_from_data_base.codename)

            # 添加场景的条件：包括进入和离开的条件，自身变化条件等等
            self.add_stage_conditions(stageentity, builddata)

            ## 创建连接的场景用于PortalStepActionSystem, 目前如果添加就只能添加一个
            assert len(builddata.exit_of_portal) <= 1
            if  len(builddata.exit_of_portal) > 0:
                exit_portal_and_goto_stage =  next(iter(builddata.exit_of_portal))
                stageentity.add(ExitOfPortalComponent, exit_portal_and_goto_stage.name)

            #重构
            agent_connect_system.register_actor_agent(builddata.name, builddata.url)
            memory_system.add_kick_off_memory(builddata.name, builddata.memory)
            code_name_component_system.register_code_name_component_class(builddata.name, builddata.codename)
            code_name_component_system.register_stage_tag_component_class(builddata.name, builddata.codename)

        return res
###############################################################################################################################################
    def add_stage_conditions(self, stageentity: Entity, builddata: StageData) -> None:

        logger.debug(f"添加Stage条件：{builddata.name}")
        if builddata.stage_entry_status != "":
            stageentity.add(StageEntryCondStatusComponent, builddata.stage_entry_status)
            logger.debug(f"如果进入场景，场景需要检查条件：{builddata.stage_entry_status}")
        if builddata.stage_entry_role_status != "":
            stageentity.add(StageEntryCondCheckRoleStatusComponent, builddata.stage_entry_role_status)
            logger.debug(f"如果进入场景，需要检查角色符合条件：{builddata.stage_entry_role_status}")
        if builddata.stage_entry_role_props != "":
            stageentity.add(StageEntryCondCheckRolePropsComponent, builddata.stage_entry_role_props)
            logger.debug(f"如果进入场景，需要检查角色拥有必要的道具：{builddata.stage_entry_role_props}")

        if builddata.stage_exit_status != "":
            stageentity.add(StageExitCondStatusComponent, builddata.stage_exit_status)
            logger.debug(f"如果离开场景，场景需要检查条件：{builddata.stage_exit_status}")
        if builddata.stage_exit_role_status != "":
            stageentity.add(StageExitCondCheckRoleStatusComponent, builddata.stage_exit_role_status)
            logger.debug(f"如果离开场景，需要检查角色符合条件：{builddata.stage_exit_role_status}")
        if builddata.stage_exit_role_props != "":
            stageentity.add(StageExitCondCheckRolePropsComponent, builddata.stage_exit_role_props)
            logger.debug(f"如果离开场景，需要检查角色拥有必要的道具：{builddata.stage_exit_role_props}")
###############################################################################################################################################
    def add_code_name_component_to_world_and_npcs(self) -> None:
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
        npcsentities = context.get_group(Matcher(ActorComponent)).entities
        for entity in npcsentities:
            npccomp: ActorComponent = entity.get(ActorComponent)
            codecompclass = code_name_component_system.get_component_class_by_name(npccomp.name)
            if codecompclass is not None:
                entity.add(codecompclass, npccomp.name)
###############################################################################################################################################
    def add_code_name_component_stages(self) -> None:
        context = self.extendedcontext
        code_name_component_system = context.code_name_component_system

        ## 重新设置npc和stage的关系
        npcsentities = context.get_group(Matcher(ActorComponent)).entities
        for entity in npcsentities:
            npccomp: ActorComponent = entity.get(ActorComponent)
            context.change_stage_tag_component(entity, "", npccomp.current_stage)

        ## 重新设置stage和stage的关系
        stagesentities = context.get_group(Matcher(StageComponent)).entities
        for entity in stagesentities:
            stagecomp: StageComponent = entity.get(StageComponent)
            codecompclass = code_name_component_system.get_component_class_by_name(stagecomp.name)
            if codecompclass is not None:
                entity.add(codecompclass, stagecomp.name)
###############################################################################################################################################
    @override
    def on_exit(self) -> None:
        logger.debug(f"{self.name} on_exit")
###############################################################################################################################################
    @property
    def about_game(self) -> str:
        if self.builder is None:
            return ""
        return self.builder.about_game
###############################################################################################################################################