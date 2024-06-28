from typing import List, Optional
from overrides import override
from entitas import Matcher #type: ignore
from loguru import logger
from systems.components import (
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
    BodyComponent,
    GUIDComponent
    )
from my_entitas.extended_context import ExtendedContext
from build_game.game_builder import GameBuilder
from build_game.stage_builder import StageBuilder
from build_game.actor_builder import ActorBuilder
from build_game.world_system_builder import WorldSystemBuilder
from entitas.entity import Entity
from systems.stage_director_component import StageDirectorComponent
from file_system.files_def import PropFile
import shutil
from rpg_game.base_game import BaseGame
from file_system.helper import add_actor_archive_files
from my_entitas.extended_processors import ExtendedProcessors
from prototype_data.data_def import StageData, ActorData, WorldSystemData
from auxiliary.guid_generator import _GUIDGenerator_
from rpg_game.rpg_game_processors import create_rpg_processors


## RPG 的测试类游戏
## 尽量不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
class RPGGame(BaseGame):

    def __init__(self, name: str, context: ExtendedContext) -> None:
        super().__init__(name)
        self.extended_context: ExtendedContext = context
        self.builder: Optional[GameBuilder] = None
        self.processors: ExtendedProcessors = create_rpg_processors(self, context)
        self.user_ips: List[str] = [] # 临时写法，待重构
###############################################################################################################################################
    def create_game(self, worlddata: GameBuilder) -> 'RPGGame':

        context = self.extended_context
        chaos_engineering_system = context.chaos_engineering_system
        
        # 第0步，yh 目前用于测试!!!!!!!，直接删worlddata.name的文件夹，保证每次都是新的 删除runtime_dir_for_world的文件夹
        if worlddata._runtime_dir.exists():
            #todo
            logger.warning(f"删除文件夹：{worlddata._runtime_dir}, 这是为了测试，后续得改！！！")
            shutil.rmtree(worlddata._runtime_dir)

        # 混沌系统，准备测试
        chaos_engineering_system.on_pre_create_game(context, worlddata)

        ## 第1步，设置根路径
        self.builder = worlddata
        context.agent_connect_system.set_runtime_dir(worlddata._runtime_dir)
        context.kick_off_memory_system.set_runtime_dir(worlddata._runtime_dir)
        context.file_system.set_runtime_dir(worlddata._runtime_dir)

        ## 第2步 创建管理员类型的角色，全局的AI
        self.create_world_system_entities(worlddata._world_system_builder)

        ## 第3步，创建actor，player是特殊的actor
        self.create_player_entities(worlddata._player_builder)
        self.create_actor_entities(worlddata._actor_buidler)
        self.add_code_name_component_to_world_and_actors()

        ## 第4步，创建stage
        self.create_stage_entities(worlddata._stage_builder)
        
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
        res: List[Entity] = []
       
        if actor_builder._raw_data is None:
            logger.error("没有WorldSystemBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in actor_builder._world_systems:
            world_entity = self.create_world_system_entity(builddata, self.extended_context) #
            res.append(world_entity)
        
        return res
###############################################################################################################################################
    def create_world_system_entity(self, world_system_data: WorldSystemData, context: ExtendedContext) -> Entity:
        context = self.extended_context
        agent_connect_system = context.agent_connect_system
        code_name_component_system = context.code_name_component_system
    
        world_entity = context.create_entity()
        #必要组件
        world_entity.add(GUIDComponent, _GUIDGenerator_.generate_string())
        world_entity.add(WorldComponent, world_system_data._name)
        #重构
        agent_connect_system.register_agent(world_system_data._name, world_system_data._url)
        code_name_component_system.register_code_name_component_class(world_system_data._name, world_system_data._codename)
        
        return world_entity
###############################################################################################################################################
    def create_player_entities(self, actor_builder: ActorBuilder) -> List[Entity]:
        # 创建player 本质就是创建Actor
        create_result = self.create_actor_entities(actor_builder)
        for entity in create_result:
            actor_comp: ActorComponent = entity.get(ActorComponent)
            logger.info(f"创建Player Entity = {actor_comp.name}")
            assert not entity.has(PlayerComponent)
            entity.add(PlayerComponent, "")
        return create_result
###############################################################################################################################################
    def create_actor_entities(self, actor_builder: ActorBuilder) -> List[Entity]:
        res: List[Entity] = []

        if actor_builder._raw_data is None:
            logger.error("没有ActorBuilder数据，请检查World.json配置。")
            return res
        
        for actor_data in actor_builder._actors:
            _entity = self.create_actor_entity(actor_data, self.extended_context)  #context.create_entity()
            res.append(_entity)
        
        return res
###############################################################################################################################################
    def create_actor_entity(self, actor_data: ActorData, context: ExtendedContext) -> Entity:

        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system

        _entity = context.create_entity()

        # 必要组件
        _entity.add(GUIDComponent, _GUIDGenerator_.generate_string())
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

        return _entity
###############################################################################################################################################
    def create_stage_entities(self, stagebuilder: StageBuilder) -> List[Entity]:
        res: List[Entity] = []
        
        if stagebuilder._raw_data is None:
            logger.error("没有StageBuilder数据，请检查World.json配置。")
            return res
        
        for stage_data in stagebuilder._stages:
            stage_entity = self.create_stage_entity(stage_data, self.extended_context)
            res.append(stage_entity)
    
        return res
###############################################################################################################################################
    def create_stage_entity(self, stage_data: StageData, context: ExtendedContext) -> Entity:

        context = self.extended_context
        agent_connect_system = context.agent_connect_system
        memory_system = context.kick_off_memory_system
        file_system = context.file_system
        code_name_component_system = context.code_name_component_system
    
        #logger.debug(f"创建Stage：{builddata.name}")
        stage_entity = context.create_entity()

        #必要组件
        stage_entity.add(GUIDComponent, _GUIDGenerator_.generate_string())
        stage_entity.add(StageComponent, stage_data._name)
        stage_entity.add(StageDirectorComponent, stage_data._name) ###
        stage_entity.add(SimpleRPGAttrComponent, stage_data._name, 
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
        self.add_stage_conditions(stage_entity, stage_data)

        ## 创建连接的场景用于PortalStepActionSystem, 目前如果添加就只能添加一个
        assert len(stage_data._exit_of_portal) <= 1
        if  len(stage_data._exit_of_portal) > 0:
            exit_portal_and_goto_stage =  next(iter(stage_data._exit_of_portal))
            stage_entity.add(ExitOfPortalComponent, exit_portal_and_goto_stage._name)

        #重构
        agent_connect_system.register_agent(stage_data._name, stage_data._url)
        memory_system.add_kick_off_memory(stage_data._name, stage_data._kick_off_memory)
        code_name_component_system.register_code_name_component_class(stage_data._name, stage_data._codename)
        code_name_component_system.register_stage_tag_component_class(stage_data._name, stage_data._codename)
        
        return stage_entity
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
        context = self.extended_context
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
        context = self.extended_context
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