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
    AgentShortTermMemory,
)
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    GUIDComponent,
    SystemMessageComponent,
    KickOffMessageComponent,
)
from player.player_proxy import PlayerProxy
from format_string.tcg_complex_name import ComplexName
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


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
    @property
    def world_runtime(self) -> WorldRuntime:
        return self._world_runtime

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
        self._create_player_entities(world_root.players, world_root.data_base)
        self._create_actor_entities(world_root.actors, world_root.data_base)

        ## 第3步，创建stage
        self._create_stage_entities(world_root.stages, world_root.data_base)

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
            world_system_entity = self.context.__create_entity__(instance.name)
            assert world_system_entity is not None

            # 必要组件
            world_system_entity.add(GUIDComponent, instance.name, instance.guid)
            world_system_entity.add(WorldSystemComponent, instance.name)
            world_system_entity.add(
                SystemMessageComponent, instance.name, prototype.system_message
            )
            world_system_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

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
            actor_entity = self.context.__create_entity__(instance.name)
            assert actor_entity is not None

            # 必要组件
            actor_entity.add(GUIDComponent, instance.name, instance.guid)
            actor_entity.add(ActorComponent, instance.name, "")
            actor_entity.add(
                SystemMessageComponent, instance.name, prototype.system_message
            )
            actor_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

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
            stage_entity = self.context.__create_entity__(instance.name)

            # 必要组件
            stage_entity.add(GUIDComponent, instance.name, instance.guid)
            stage_entity.add(StageComponent, instance.name)
            stage_entity.add(
                SystemMessageComponent, instance.name, prototype.system_message
            )
            stage_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

            ## 重新设置Actor和stage的关系
            for actor_name in instance.actors:
                actor_entity: Optional[Entity] = self.context.get_actor_entity(
                    actor_name
                )
                assert actor_entity is not None
                actor_entity.replace(ActorComponent, actor_name, instance.name)

            ret.append(stage_entity)

        return []

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
    def get_system_message(self, entity: Entity) -> str:

        data_base = self.world_runtime.root.data_base
        complex_name = ComplexName(entity._name)

        if entity.has(ActorComponent):
            actor_prototype = data_base.actors.get(complex_name.parse_name, None)
            assert actor_prototype is not None
            if actor_prototype is not None:
                return actor_prototype.system_message

        elif entity.has(StageComponent):

            stage_prototype = data_base.stages.get(complex_name.parse_name, None)
            assert stage_prototype is not None
            if stage_prototype is not None:
                return stage_prototype.system_message

        elif entity.has(WorldSystemComponent):

            world_system_prototype = data_base.world_systems.get(
                complex_name.parse_name, None
            )
            assert world_system_prototype is not None
            if world_system_prototype is not None:
                return world_system_prototype.system_message

        return ""

    ###############################################################################################################################################
    def get_agent_short_term_memory(self, entity: Entity) -> AgentShortTermMemory:
        return self.world_runtime.agents_short_term_memory.setdefault(
            entity._name, AgentShortTermMemory(name=entity._name, chat_history=[])
        )

    ###############################################################################################################################################
    def append_human_message(self, entity: Entity, chat: str) -> None:
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.extend([HumanMessage(content=chat)])

    ###############################################################################################################################################
    def append_ai_message(self, entity: Entity, chat: str) -> None:
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.extend([AIMessage(content=chat)])

    ###############################################################################################################################################
    def append_system_message(self, entity: Entity, chat: str) -> None:
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        assert len(agent_short_term_memory.chat_history) == 0
        agent_short_term_memory.chat_history.extend([SystemMessage(content=chat)])

    ###############################################################################################################################################
