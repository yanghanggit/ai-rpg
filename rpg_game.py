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
    SimpleRPGAttrComponent, 
    AppearanceComponent,
    StageExitCondStatusComponent,
    StageExitCondCheckActorStatusComponent,
    StageExitCondCheckActorPropsComponent,
    StageEntryCondStatusComponent,
    StageEntryCondCheckActorStatusComponent,
    StageEntryCondCheckActorPropsComponent,
    BodyComponent
    )
from auxiliary.extended_context import ExtendedContext
from auxiliary.game_builders import GameBuilder, StageBuilder, ActorBuilder, WorldSystemBuilder
from entitas.entity import Entity
from systems.agents_kick_off_system import AgentsKickOffSystem
from systems.actor_ready_for_planning_system import ActorReadyForPlanningSystem
from systems.stage_planning_system import StagePlanningSystem
from systems.actor_planning_system import ActorPlanningSystem
from systems.speak_action_system import SpeakActionSystem
from systems.attack_action_system import AttackActionSystem
from systems.go_to_action_system import GoToActionSystem
from systems.check_before_go_to_action_system import CheckBeforeGoToActionSystem
from systems.director_system import DirectorSystem
from systems.destroy_system import DestroySystem
from systems.stage_ready_for_planning_system import StageReadyForPlanningSystem
from systems.tag_action_system import TagActionSystem
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
from systems.agents_connect_system import AgentsConnectSystem
from auxiliary.file_system_helper import add_actor_archive_files
from systems.my_processors import MyProcessors
from systems.simple_rpg_pre_fight_system import SimpleRPGPreFightSystem
from systems.compress_chat_history_system import CompressChatHistorySystem
from systems.post_conversation_action_system import PostConversationActionSystem
from auxiliary.base_data import StageData
from systems.update_appearance_system import UpdateAppearanceSystem




UPDATE_APPEARANCE_SYSTEM_NAME = "角色外观生成器"


## RPG 的测试类游戏
## 尽量不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
class RPGGame(BaseGame):

    def __init__(self, name: str, context: ExtendedContext) -> None:
        super().__init__(name)
        self.extendedcontext: ExtendedContext = context
        self.builder: Optional[GameBuilder] = None
        self.processors: MyProcessors = self.create_processors(self.extendedcontext)
        self.user_ips: List[str] = [] # 临时写法，待重构
###############################################################################################################################################
    def create_processors(self, context: ExtendedContext) -> MyProcessors:

        # 处理用户输入
        from systems.handle_player_input_system import HandlePlayerInputSystem ### 不这样就循环引用
        from systems.update_client_message_system import UpdateClientMessageSystem
        from systems.dead_action_system import DeadActionSystem
        from systems.terminal_player_interrupt_and_wait_system import TerminalPlayerInterruptAndWaitSystem
        from systems.terminal_player_input_system import TerminalPlayerInputSystem
        from systems.save_system import SaveSystem

        processors = MyProcessors()
       
        ##调试用的系统。监视进入运行之前的状态
        processors.add(BeginSystem(context))
        
        #初始化系统########################
        processors.add(AgentsConnectSystem(context)) ### 连接所有agent
        processors.add(AgentsKickOffSystem(context)) ### 第一次读状态, initmemory
        processors.add(UpdateAppearanceSystem(context, UPDATE_APPEARANCE_SYSTEM_NAME)) ### 更新外观
        #########################################

       
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
        processors.add(SimpleRPGPreFightSystem(context)) #战斗之前需要更新装备
        processors.add(AttackActionSystem(context)) 
        processors.add(PostFightSystem(context))

        ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。
        
        processors.add(DeadActionSystem(context, self)) 
        
        # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行。。。
        processors.add(SearchActionSystem(context)) 
        processors.add(StealActionSystem(context))
        processors.add(TradeActionSystem(context))
        processors.add(UsePropActionSystem(context))
        processors.add(CheckStatusActionSystem(context)) # 道具交互类行为之后，可以发起自检

        # 场景切换类行为，非常重要而且必须在最后
        processors.add(PortalStepActionSystem(context)) 
        # 去往场景之前的检查与实际的执行
        processors.add(CheckBeforeGoToActionSystem(context)) 
        processors.add(GoToActionSystem(context))
        #
        processors.add(PerceptionActionSystem(context)) # 场景切换类行为之后可以发起感知

        processors.add(PostActionSystem(context)) ####### 在所有行动之后 #########################################
        #########################################

        #行动结束后导演
        processors.add(DirectorSystem(context))
        #行动结束后更新关系网，因为依赖Director所以必须在后面
        processors.add(UpdateArchiveSystem(context))

        ###最后删除entity与存储数据
        processors.add(DestroySystem(context))
        ##测试的系统，移除掉不太重要的提示词，例如一些上行命令的。
        processors.add(CompressChatHistorySystem(context)) ## 测试的系统
        ##调试用的系统。监视进入运行之后的状态
        processors.add(EndSystem(context))

        #保存系统，在所有系统之后
        processors.add(SaveSystem(context, self))

        # 开发专用，网页版本不需要
        processors.add(TerminalPlayerInterruptAndWaitSystem(context, self))
        #########################################

        #规划逻辑########################
        processors.add(PrePlanningSystem(context)) ######## 在所有规划之前
        processors.add(StageReadyForPlanningSystem(context))
        processors.add(StagePlanningSystem(context))
        processors.add(ActorReadyForPlanningSystem(context))
        processors.add(ActorPlanningSystem(context))
        processors.add(PostPlanningSystem(context)) ####### 在所有规划之后

        ## 第一次抓可以被player看到的信息
        processors.add(UpdateClientMessageSystem(context, self)) 

        ## 开发专用，网页版本不需要
        processors.add(TerminalPlayerInputSystem(context, self))
        
        return processors
###############################################################################################################################################
    def create_game(self, worlddata: GameBuilder) -> 'RPGGame':
        assert worlddata is not None
        assert worlddata._data is not None

        context = self.extendedcontext
        chaos_engineering_system = context.chaos_engineering_system
        
        # 第0步，yh 目前用于测试!!!!!!!，直接删worlddata.name的文件夹，保证每次都是新的 删除runtime_dir_for_world的文件夹
        if worlddata.runtime_dir.exists():
            #todo
            logger.warning(f"删除文件夹：{worlddata.runtime_dir}, 这是为了测试，后续得改！！！")
            shutil.rmtree(worlddata.runtime_dir)

        # 混沌系统，准备测试
        chaos_engineering_system.on_pre_create_game(context, worlddata)

        ## 第1步，设置根路径
        self.builder = worlddata
        context.agent_connect_system.set_runtime_dir(worlddata.runtime_dir)
        context.kick_off_memory_system.set_runtime_dir(worlddata.runtime_dir)
        context.file_system.set_runtime_dir(worlddata.runtime_dir)

        ## 第2步 创建管理员类型的角色，全局的AI
        self.create_world_system_entities(worlddata.world_system_builder)

        ## 第3步，创建actor，player是特殊的actor
        self.create_player_entities(worlddata.player_builder)
        self.create_actor_entities(worlddata.actor_buidler)
        self.add_code_name_component_to_world_and_actors()

        ## 第4步，创建stage
        self.create_stage_entities(worlddata.stage_builder)
        
        ## 第5步，最后处理因为需要上一阶段的注册流程
        self.add_code_name_component_stages()

        ## 最后！混沌系统，准备测试
        chaos_engineering_system.on_post_create_game(context, worlddata)

        return self
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
    def create_world_system_entities(self, actor_builder: WorldSystemBuilder) -> List[Entity]:
        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        code_name_component_system = context.code_name_component_system
        res: List[Entity] = []
        if actor_builder._data_list is None:
            raise ValueError("没有WorldBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in actor_builder._world_system_datas:
            worldentity = context.create_entity()
            res.append(worldentity)
            #必要组件
            worldentity.add(WorldComponent, builddata._name)
            #重构
            agent_connect_system.register_agent(builddata._name, builddata._url)
            code_name_component_system.register_code_name_component_class(builddata._name, builddata._codename)

        return res
###############################################################################################################################################
    def create_player_entities(self, actor_builder: ActorBuilder) -> List[Entity]:
        # 创建player 本质就是创建Actor
        create_result = self.create_actor_entities(actor_builder)
        for entity in create_result:
            actor_comp: ActorComponent = entity.get(ActorComponent)
            logger.info(f"创建Player Entity = {actor_comp.name}")
            entity.add(PlayerComponent, "")
        return create_result
###############################################################################################################################################
    def create_actor_entities(self, actor_builder: ActorBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system
        res: List[Entity] = []

        if actor_builder._data_block is None:
            raise ValueError("没有ActorBuilder数据，请检查World.json配置。")
            return res
        
        for actor_data in actor_builder._actors:
            _entity = context.create_entity()
            res.append(_entity)

            # 必要组件
            _entity.add(ActorComponent, actor_data._name, "")
            _entity.add(SimpleRPGAttrComponent, actor_data._name, 
                        actor_data.maxhp, 
                        actor_data.hp, 
                        actor_data.attack, 
                        actor_data.defense)
            _entity.add(AppearanceComponent, actor_data._appearance)
            _entity.add(BodyComponent, actor_data._body)

            #重构
            agent_connect_system.register_agent(actor_data._name, actor_data._url)
            memory_system.add_kick_off_memory(actor_data._name, actor_data._kick_off_memory)
            code_name_component_system.register_code_name_component_class(actor_data._name, actor_data._codename)
            
            # 添加道具
            for tp in actor_data._props:
                # 数组组织
                prop_proxy = tp[0]
                count = tp[1]
                ## 重构
                _pd = context.data_base_system.get_prop(prop_proxy._name)
                if _pd is None:
                    logger.error(f"没有从数据库找到道具：{prop_proxy._name}！！！！！！！！！")
                    continue
            
                prop_file = PropFile(prop_proxy._name, actor_data._name, _pd, count)
                file_system.add_prop_file(prop_file)
                code_name_component_system.register_code_name_component_class(_pd._name, _pd._codename)

            # 初步建立关系网（在编辑文本中提到的Actor名字）
            add_actor_archive_files(file_system, actor_data._name, actor_data._actor_archives)

        return res
###############################################################################################################################################
    def create_stage_entities(self, stagebuilder: StageBuilder) -> List[Entity]:

        context = self.extendedcontext
        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system
        res: List[Entity] = []

        if stagebuilder._data_block is None:
            raise ValueError("没有StageBuilder数据，请检查World.json配置。")
            return res
        
        # 创建stage相关配置
        for stage_data in stagebuilder._stages:
            #logger.debug(f"创建Stage：{builddata.name}")
            stageentity = context.create_entity()

            #必要组件
            stageentity.add(StageComponent, stage_data._name)
            stageentity.add(StageDirectorComponent, stage_data._name) ###
            stageentity.add(SimpleRPGAttrComponent, stage_data._name, 
                            stage_data.maxhp, 
                            stage_data.hp, 
                            stage_data.attack, 
                            stage_data.defense)
    
            ## 重新设置Actor和stage的关系
            for _actor in stage_data._actors:
                _name = _actor._name
                _entity: Optional[Entity] = context.get_actor_entity(_name)
                assert _entity is not None
                _entity.replace(ActorComponent, _name, stage_data._name)
                
            # 场景内添加道具
            for tp in stage_data._props:
                prop_proxy = tp[0]
                count = tp[1]
                # 直接使用文件系统
                _pd = context.data_base_system.get_prop(prop_proxy._name)
                if _pd is None:
                    logger.error(f"没有从数据库找到道具：{prop_proxy._name}！！！！！！！！！")
                    continue
                prop_file = PropFile(prop_proxy._name, stage_data._name, _pd, count)
                file_system.add_prop_file(prop_file)
                code_name_component_system.register_code_name_component_class(_pd._name, _pd._codename)

            # 添加场景的条件：包括进入和离开的条件，自身变化条件等等
            self.add_stage_conditions(stageentity, stage_data)

            ## 创建连接的场景用于PortalStepActionSystem, 目前如果添加就只能添加一个
            assert len(stage_data._exit_of_portal) <= 1
            if  len(stage_data._exit_of_portal) > 0:
                exit_portal_and_goto_stage =  next(iter(stage_data._exit_of_portal))
                stageentity.add(ExitOfPortalComponent, exit_portal_and_goto_stage._name)

            #重构
            agent_connect_system.register_agent(stage_data._name, stage_data._url)
            memory_system.add_kick_off_memory(stage_data._name, stage_data._kick_off_memory)
            code_name_component_system.register_code_name_component_class(stage_data._name, stage_data._codename)
            code_name_component_system.register_stage_tag_component_class(stage_data._name, stage_data._codename)

        return res
###############################################################################################################################################
    def add_stage_conditions(self, stageentity: Entity, builddata: StageData) -> None:

        logger.debug(f"添加Stage条件：{builddata._name}")
        if builddata._stage_entry_status != "":
            stageentity.add(StageEntryCondStatusComponent, builddata._stage_entry_status)
            logger.debug(f"如果进入场景，场景需要检查条件：{builddata._stage_entry_status}")
        if builddata._stage_entry_actor_status != "":
            stageentity.add(StageEntryCondCheckActorStatusComponent, builddata._stage_entry_actor_status)
            logger.debug(f"如果进入场景，需要检查角色符合条件：{builddata._stage_entry_actor_status}")
        if builddata._stage_entry_actor_props != "":
            stageentity.add(StageEntryCondCheckActorPropsComponent, builddata._stage_entry_actor_props)
            logger.debug(f"如果进入场景，需要检查角色拥有必要的道具：{builddata._stage_entry_actor_props}")

        if builddata._stage_exit_status != "":
            stageentity.add(StageExitCondStatusComponent, builddata._stage_exit_status)
            logger.debug(f"如果离开场景，场景需要检查条件：{builddata._stage_exit_status}")
        if builddata._stage_exit_actor_status != "":
            stageentity.add(StageExitCondCheckActorStatusComponent, builddata._stage_exit_actor_status)
            logger.debug(f"如果离开场景，需要检查角色符合条件：{builddata._stage_exit_actor_status}")
        if builddata._stage_exit_actor_props != "":
            stageentity.add(StageExitCondCheckActorPropsComponent, builddata._stage_exit_actor_props)
            logger.debug(f"如果离开场景，需要检查角色拥有必要的道具：{builddata._stage_exit_actor_props}")
###############################################################################################################################################
    def add_code_name_component_to_world_and_actors(self) -> None:
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
        actor_entities = context.get_group(Matcher(ActorComponent)).entities
        for entity in actor_entities:
            actor_comp: ActorComponent = entity.get(ActorComponent)
            codecompclass = code_name_component_system.get_component_class_by_name(actor_comp.name)
            if codecompclass is not None:
                entity.add(codecompclass, actor_comp.name)
###############################################################################################################################################
    def add_code_name_component_stages(self) -> None:
        context = self.extendedcontext
        code_name_component_system = context.code_name_component_system

        ## 重新设置actor和stage的关系
        actor_entities = context.get_group(Matcher(ActorComponent)).entities
        for entity in actor_entities:
            actor_comp: ActorComponent = entity.get(ActorComponent)
            context.change_stage_tag_component(entity, "", actor_comp.current_stage)

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