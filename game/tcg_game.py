from entitas import Entity  # type: ignore
from typing import Set, List, Optional
from overrides import override
from loguru import logger
from game.tcg_game_context import TCGGameContext
from game.base_game import BaseGame
from game.tcg_game_processors import TCGGameProcessors
from models.event_models import BaseEvent
from models.tcg_models import (
    WorldRuntime,
    WorldSystemInstance,
    WorldDataBase,
    ActorInstance,
    StageInstance,
)
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    GUIDComponent,
)
from player.player_proxy import PlayerProxy
from format_string.tcg_complex_name import ComplexName


class TCGGame(BaseGame):

    def __init__(
        self, name: str, world_runtime: WorldRuntime, context: TCGGameContext
    ) -> None:

        # 必须实现父
        super().__init__(name)

        self._context: TCGGameContext = context
        self._context._game = self
        self._world_runtime: WorldRuntime = world_runtime
        self._processors: TCGGameProcessors = TCGGameProcessors.create(self, context)
        self._players: List[PlayerProxy] = []

    ###############################################################################################################################################
    @property
    def context(self) -> TCGGameContext:
        return self._context

    ###############################################################################################################################################
    def build(self) -> None:

        # 混沌系统
        self.context.chaos_engineering_system.initialize(self)
        self.context.chaos_engineering_system.on_pre_create_game()

        #
        world_root = self._world_runtime.root

        ## 第1步，创建world_system
        self._create_world_system_entities(
            world_root.world_systems, world_root.data_base
        )

        ## 第2步，创建actor
        player_entities = self._create_player_entities(
            world_root.players, world_root.data_base
        )
        actor_entities = self._create_actor_entities(
            world_root.actors, world_root.data_base
        )

        ## 第4步，创建stage
        self._create_stage_entities(world_root.stages, world_root.data_base)

        ## 第5步，最后处理因为需要上一阶段的注册流程
        self._initialize_actor_stage_links(set(actor_entities + player_entities))

        ## 最后！混沌系统，准备测试
        self.context.chaos_engineering_system.on_post_create_game()

    ###############################################################################################################################################
    def _create_world_system_entities(
        self,
        world_system_instances: List[WorldSystemInstance],
        data_base: WorldDataBase,
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in world_system_instances:

            complex_name = ComplexName(instance.name)
            prototype = data_base.world_systems.get(complex_name.parse_name, None)
            assert prototype is not None
            if prototype is None:
                logger.error(f"db is None: {instance.name}")
                continue

            # 创建实体
            world_system_entity = self.context.create_entity()
            assert world_system_entity is not None

            # 必要组件
            world_system_entity.add(GUIDComponent, instance.name, instance.guid)
            world_system_entity.add(WorldSystemComponent, instance.name)

            # 添加扩展子系统的功能: CodeName
            code_name_component_class = (
                self.context.query_component_system.register_query_component_class(
                    instance_name=instance.name,
                    data_base_code_name=prototype.code_name,
                    guid=instance.guid,
                )
            )
            assert code_name_component_class is not None
            world_system_entity.add(code_name_component_class, instance.name)

            # 添加到返回值
            ret.append(world_system_entity)

        return ret

    ###############################################################################################################################################
    def _create_actor_entities(
        self, actor_instances: List[ActorInstance], data_base: WorldDataBase
    ) -> List[Entity]:

        ret: List[Entity] = []
        for instance in actor_instances:

            complex_name = ComplexName(instance.name)
            prototype = data_base.actors.get(complex_name.parse_name, None)
            assert prototype is not None
            if prototype is None:
                logger.error(f"db is None: {instance.name}")
                continue

            # 创建实体
            actor_entity = self.context.create_entity()
            assert actor_entity is not None

            # 必要组件
            actor_entity.add(GUIDComponent, instance.name, instance.guid)
            actor_entity.add(ActorComponent, instance.name, "")

            # 添加扩展子系统: CodeName
            code_name_component_class = (
                self.context.query_component_system.register_query_component_class(
                    instance_name=instance.name,
                    data_base_code_name=prototype.code_name,
                    guid=instance.guid,
                )
            )
            assert code_name_component_class is not None
            actor_entity.add(code_name_component_class, instance.name)

            # 添加到返回值
            ret.append(actor_entity)

        return ret

    ###############################################################################################################################################
    def _create_player_entities(
        self, players: List[ActorInstance], data_base: WorldDataBase
    ) -> List[Entity]:

        actor_entities = self._create_actor_entities(players, data_base)
        for actor_entity in actor_entities:
            assert actor_entity is not None
            assert actor_entity.has(ActorComponent)
            assert not actor_entity.has(PlayerComponent)
            actor_entity.add(PlayerComponent, "")

        return actor_entities

    ###############################################################################################################################################
    def _create_stage_entities(
        self, stage_instances: List[StageInstance], data_base: WorldDataBase
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in stage_instances:

            complex_name = ComplexName(instance.name)
            prototype = data_base.stages.get(complex_name.parse_name, None)
            assert prototype is not None
            if prototype is None:
                logger.error(f"db is None: {instance.name}")
                continue

            # 创建实体
            stage_entity = self.context.create_entity()

            # 必要组件
            stage_entity.add(GUIDComponent, instance.name, instance.guid)
            stage_entity.add(StageComponent, instance.name)

            ## 重新设置Actor和stage的关系
            for actor_name in instance.actors:
                actor_entity: Optional[Entity] = self.context.get_actor_entity(
                    actor_name
                )
                assert actor_entity is not None
                actor_entity.replace(ActorComponent, actor_name, instance.name)

            # 添加子系统：CodeName
            code_name_component_class = (
                self.context.query_component_system.register_query_component_class(
                    instance_name=instance.name,
                    data_base_code_name=prototype.code_name,
                    guid=instance.guid,
                )
            )
            assert code_name_component_class is not None
            stage_entity.add(code_name_component_class, instance.name)

            # 添加子系统：StageTag
            self.context.query_component_system.register_stage_tag_component_class(
                instance.name, f"""{prototype.code_name}{instance.guid}"""
            )

            ret.append(stage_entity)

        return []

    ###############################################################################################################################################
    def _initialize_actor_stage_links(self, actor_entities: Set[Entity]) -> None:
        # 只有初始化级别的调用，才能使用这个函数
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            assert actor_comp.current_stage != ""
            self.context.update_stage_tag_component(
                actor_entity, "", actor_comp.current_stage
            )

    ###############################################################################################################################################
    def restore(self) -> None:
        self.context.restore_from_snapshot(self._world_runtime.entities_snapshot)

    ###############################################################################################################################################
    def add_player(self, player_proxy: PlayerProxy) -> None:
        assert player_proxy not in self._players
        if player_proxy not in self._players:
            self._players.append(player_proxy)

    ###############################################################################################################################################
    def get_player(self, player_name: str) -> Optional[PlayerProxy]:
        for player in self._players:
            if player.player_name == player_name:
                return player
        return None

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        # 顺序不要动
        current_processors = self._processors
        if not current_processors._initialized:
            current_processors._initialized = True
            current_processors.activate_reactive_processors()
            current_processors.initialize()

        current_processors.execute()
        current_processors.cleanup()

    ###############################################################################################################################################
    @override
    async def a_execute(self) -> None:
        # 顺序不要动
        current_processors = self._processors
        if not current_processors._initialized:
            current_processors._initialized = True
            current_processors.activate_reactive_processors()
            current_processors.initialize()

        await current_processors.a_execute()
        current_processors.cleanup()

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        all = [self._processors]
        for processor in all:
            processor.tear_down()
            processor.clear_reactive_processors()

        logger.info(f"{self._name}, game over!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    @override
    def send_event(self, player_proxy_names: Set[str], send_event: BaseEvent) -> None:
        pass

    ###############################################################################################################################################
