from typing import List, Optional
from overrides import override
from entitas import Matcher #type: ignore
from loguru import logger
from ecs_systems.components import ( WorldComponent, StageComponent, ExitOfPortalComponent, ActorComponent,  PlayerComponent, 
    SimpleRPGAttrComponent, AppearanceComponent, StageExitCondStatusComponent, StageExitCondCheckActorStatusComponent,
    StageExitCondCheckActorPropsComponent, StageEntryCondStatusComponent, StageEntryCondCheckActorStatusComponent,
    StageEntryCondCheckActorPropsComponent, BodyComponent, GUIDComponent)
from my_entitas.extended_context import ExtendedContext
from build_game.game_builder import GameBuilder
from build_game.stage_builder import StageBuilder
from build_game.actor_builder import ActorBuilder
from build_game.world_system_builder import WorldSystemBuilder
from entitas.entity import Entity
from ecs_systems.stage_director_component import StageDirectorComponent
from file_system.files_def import PropFile
import shutil
from rpg_game.base_game import BaseGame
from file_system.helper import add_actor_archive_files
from my_entitas.extended_processors import ExtendedProcessors
from prototype_data.data_def import StageData, ActorData, WorldSystemData
from extended_systems.guid_generator import _GUIDGenerator_
from rpg_game.rpg_game_processors import create_rpg_processors

class RPGGame(BaseGame):

    """
    RPG 的测试类游戏
    """

    def __init__(self, name: str, context: ExtendedContext) -> None:
        super().__init__(name)
        
        ## 尽量不要再加东西了，Game就只管上下文，创建世界的数据，和Processors。其中上下文可以做运行中的全局数据管理者
        self._extended_context: ExtendedContext = context
        self._game_builder: Optional[GameBuilder] = None
        self._processors: ExtendedProcessors = create_rpg_processors(self, context)
        self._player_names: List[str] = []
###############################################################################################################################################
    def create_game(self, game_builder: GameBuilder) -> 'RPGGame':

        context = self._extended_context
        
        # 第0步，yh 目前用于测试!!!!!!!，直接删worlddata.name的文件夹，保证每次都是新的 删除runtime_dir_for_world的文件夹
        if game_builder._runtime_dir.exists():
            #todo
            logger.warning(f"删除文件夹：{game_builder._runtime_dir}, 这是为了测试，后续得改！！！")
            shutil.rmtree(game_builder._runtime_dir)

        # 混沌系统，准备测试
        context._chaos_engineering_system.on_pre_create_game(context, game_builder)

        ## 第1步，设置根路径
        self._game_builder = game_builder
        context._langserve_agent_system.set_runtime_dir(game_builder._runtime_dir)
        context._kick_off_memory_system.set_runtime_dir(game_builder._runtime_dir)
        context._file_system.set_runtime_dir(game_builder._runtime_dir)

        ## 第2步 创建管理员类型的角色，全局的AI
        self.create_world_system_entities(game_builder._world_system_builder)

        ## 第3步，创建actor，player是特殊的actor
        self.create_player_entities(game_builder._player_builder)
        self.create_actor_entities(game_builder._actor_buidler)
        self.add_code_name_component_to_world_and_actors()

        ## 第4步，创建stage
        self.create_stage_entities(game_builder._stage_builder)
        
        ## 第5步，最后处理因为需要上一阶段的注册流程
        self.add_code_name_component_stages()

        ## 最后！混沌系统，准备测试
        context._chaos_engineering_system.on_post_create_game(context, game_builder)

        return self
###############################################################################################################################################
    @override
    def execute(self) -> None:

        self.started = True

        #顺序不要动
        if not self.inited:
            self.inited = True
            self._processors.activate_reactive_processors()
            self._processors.initialize()
        
        self._processors.execute()
        self._processors.cleanup()
###############################################################################################################################################
    @override
    async def async_execute(self) -> None:
        self.started = True

        #顺序不要动
        if not self.inited:
            self.inited = True
            self._processors.activate_reactive_processors()
            self._processors.initialize()
        
        await self._processors.async_execute()
        self._processors.cleanup()
###############################################################################################################################################
    @override
    def exit(self) -> None:
        self._processors.clear_reactive_processors()
        self._processors.tear_down()
        logger.info(f"{self.name}, game over")
###############################################################################################################################################
    def create_world_system_entities(self, actor_builder: WorldSystemBuilder) -> List[Entity]:
        res: List[Entity] = []
       
        if actor_builder._raw_data is None:
            logger.error("没有WorldSystemBuilder数据，请检查World.json配置。")
            return res
        
        for builddata in actor_builder._world_systems:
            world_entity = self.create_world_system_entity(builddata, self._extended_context) #
            res.append(world_entity)
        
        return res
###############################################################################################################################################
    def create_world_system_entity(self, world_system_data: WorldSystemData, context: ExtendedContext) -> Entity:
        context = self._extended_context
        # 创建实体
        world_entity = context.create_entity()
        #必要组件
        world_entity.add(GUIDComponent, _GUIDGenerator_.generate())
        world_entity.add(WorldComponent, world_system_data._name)
        #重构
        context._langserve_agent_system.register_agent(world_system_data._name, world_system_data._url)
        context._codename_component_system.register_code_name_component_class(world_system_data._name, world_system_data._codename)
        
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
            _entity = self.create_actor_entity(actor_data, self._extended_context)  #context.create_entity()
            res.append(_entity)
        
        return res
###############################################################################################################################################
    def create_actor_entity(self, actor_data: ActorData, context: ExtendedContext) -> Entity:

        # 创建实体
        _entity = context.create_entity()

        # 必要组件
        _entity.add(GUIDComponent, _GUIDGenerator_.generate())
        _entity.add(ActorComponent, actor_data._name, "")
        _entity.add(SimpleRPGAttrComponent, actor_data._name, 
                    actor_data.max_hp, 
                    actor_data.hp, 
                    actor_data.attack, 
                    actor_data.defense)
        hash_code = hash(actor_data._appearance)
        _entity.add(AppearanceComponent, actor_data._appearance, hash_code)
        _entity.add(BodyComponent, actor_data._body)

        #重构
        context._langserve_agent_system.register_agent(actor_data._name, actor_data._url)
        context._kick_off_memory_system.add_kick_off_memory(actor_data._name, actor_data._kick_off_memory)
        context._codename_component_system.register_code_name_component_class(actor_data._name, actor_data._codename)
        
        # 添加道具
        for tp in actor_data._props:
            # 数组组织
            prop_proxy = tp[0]
            count = tp[1]
            ## 重构
            _pd = context._data_base_system.get_prop(prop_proxy._name)
            if _pd is None:
                logger.error(f"没有从数据库找到道具：{prop_proxy._name}")
                continue
        
            prop_file = PropFile(prop_proxy._name, actor_data._name, _pd, count)
            context._file_system.add_prop_file(prop_file)
            context._codename_component_system.register_code_name_component_class(_pd._name, _pd._codename)

        # 初步建立关系网（在编辑文本中提到的Actor名字）
        add_actor_archive_files(context._file_system, actor_data._name, actor_data._actor_archives)

        return _entity
###############################################################################################################################################
    def create_stage_entities(self, stage_builder: StageBuilder) -> List[Entity]:
        res: List[Entity] = []
        
        if stage_builder._raw_data is None:
            logger.error("没有StageBuilder数据,请检查World.json配置。")
            return res
        
        for stage_data in stage_builder._stages:
            stage_entity = self.create_stage_entity(stage_data, self._extended_context)
            res.append(stage_entity)
    
        return res
###############################################################################################################################################
    def create_stage_entity(self, stage_data: StageData, context: ExtendedContext) -> Entity:

        context = self._extended_context

        # 创建实体
        stage_entity = context.create_entity()

        #必要组件
        stage_entity.add(GUIDComponent, _GUIDGenerator_.generate())
        stage_entity.add(StageComponent, stage_data._name)
        stage_entity.add(StageDirectorComponent, stage_data._name) ###
        stage_entity.add(SimpleRPGAttrComponent, stage_data._name, 
                        stage_data.max_hp, 
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
            _pd = context._data_base_system.get_prop(prop_proxy._name)
            if _pd is None:
                logger.error(f"没有从数据库找到道具：{prop_proxy._name}")
                continue
            prop_file = PropFile(prop_proxy._name, stage_data._name, _pd, count)
            context._file_system.add_prop_file(prop_file)
            context._codename_component_system.register_code_name_component_class(_pd._name, _pd._codename)

        # 添加场景的条件：包括进入和离开的条件，自身变化条件等等
        self.add_stage_conditions(stage_entity, stage_data)

        ## 创建连接的场景用于PortalStepActionSystem, 目前如果添加就只能添加一个
        assert len(stage_data._exit_of_portal) <= 1
        if  len(stage_data._exit_of_portal) > 0:
            exit_portal_and_goto_stage =  next(iter(stage_data._exit_of_portal))
            stage_entity.add(ExitOfPortalComponent, exit_portal_and_goto_stage._name)

        #重构
        context._langserve_agent_system.register_agent(stage_data._name, stage_data._url)
        context._kick_off_memory_system.add_kick_off_memory(stage_data._name, stage_data._kick_off_memory)
        context._codename_component_system.register_code_name_component_class(stage_data._name, stage_data._codename)
        context._codename_component_system.register_stage_tag_component_class(stage_data._name, stage_data._codename)
        
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
        context = self._extended_context

        #
        world_entities = context.get_group(Matcher(WorldComponent)).entities
        for entity in world_entities:
            world_comp: WorldComponent = entity.get(WorldComponent)
            codecompclass = context._codename_component_system.get_component_class_by_name(world_comp.name)
            if codecompclass is not None:
                entity.add(codecompclass, world_comp.name)

        #
        actor_entities = context.get_group(Matcher(ActorComponent)).entities
        for entity in actor_entities:
            actor_comp: ActorComponent = entity.get(ActorComponent)
            codecompclass = context._codename_component_system.get_component_class_by_name(actor_comp.name)
            if codecompclass is not None:
                entity.add(codecompclass, actor_comp.name)
###############################################################################################################################################
    def add_code_name_component_stages(self) -> None:
        context = self._extended_context

        ## 重新设置actor和stage的关系
        actor_entities = context.get_group(Matcher(ActorComponent)).entities
        for entity in actor_entities:
            actor_comp: ActorComponent = entity.get(ActorComponent)
            context.change_stage_tag_component(entity, "", actor_comp.current_stage)

        ## 重新设置stage和stage的关系
        stage_entities = context.get_group(Matcher(StageComponent)).entities
        for entity in stage_entities:
            stagecomp: StageComponent = entity.get(StageComponent)
            codecompclass = context._codename_component_system.get_component_class_by_name(stagecomp.name)
            if codecompclass is not None:
                entity.add(codecompclass, stagecomp.name)
###############################################################################################################################################
    @override
    def on_exit(self) -> None:
        logger.debug(f"{self.name} on_exit")
###############################################################################################################################################
    @property
    def about_game(self) -> str:
        if self._game_builder is None:
            return ""
        return self._game_builder.about_game
###############################################################################################################################################
    def add_player(self, name: str) -> None:
        assert name not in self._player_names
        if name not in self._player_names:
            self._player_names.append(name)
###############################################################################################################################################
    def single_terminal_player(self) -> str:
        assert len(self._player_names) == 1
        if len(self._player_names) == 0:
            return ""
        return self._player_names[0]
###############################################################################################################################################
    @property
    def player_names(self) -> List[str]:
        return self._player_names
###############################################################################################################################################
    @property
    def game_rounds(self) -> int:
        return self._extended_context._execute_count
###############################################################################################################################################