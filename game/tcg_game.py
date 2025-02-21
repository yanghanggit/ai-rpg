from entitas import Entity, Matcher  # type: ignore
from typing import Dict, Set, List, Optional
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
    StagePrototype,
    StageInstance,
    AgentShortTermMemory,
)
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerActorFlagComponent,
    GUIDComponent,
    SystemMessageComponent,
    KickOffMessageComponent,
    StageGraphComponent,
    FinalAppearanceComponent,
    StageEnvironmentComponent,
    HomeStageFlagComponent,
    DungeonStageFlagComponent,
)
from player.player_proxy import PlayerProxy
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from extended_systems.lang_serve_system import LangServeSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from pathlib import Path
import rpg_game_systems.prompt_utils
from models.event_models import AgentEvent


class TCGGame(BaseGame):

    def __init__(
        self,
        name: str,
        world_runtime: WorldRuntime,
        world_runtime_path: Path,
        context: TCGGameContext,
        langserve_system: LangServeSystem,
        # prop_file_system: PropFileManageSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:

        # 必须实现父
        super().__init__(name)

        # 上下文
        self._context: TCGGameContext = context
        self._context._game = self

        # 世界运行时
        self._world_runtime: WorldRuntime = world_runtime
        self._world_runtime_path: Path = world_runtime_path

        # 处理器
        self._processors: TCGGameProcessors = TCGGameProcessors.create(self, context)

        # 玩家
        self._players: List[PlayerProxy] = []

        # agent 系统
        self._langserve_system: LangServeSystem = langserve_system

        # 道具系统
        # self._prop_file_system: PropFileManageSystem = prop_file_system

        # 混沌工程系统
        self._chaos_engineering_system: IChaosEngineering = chaos_engineering_system

        # 初始化子系统。。。。
        # self._initialize_prop_file_system()

    ###############################################################################################################################################
    @property
    def langserve_system(self) -> LangServeSystem:
        return self._langserve_system

    ###############################################################################################################################################
    @property
    def chaos_engineering_system(self) -> IChaosEngineering:
        return self._chaos_engineering_system

    ###############################################################################################################################################
    @property
    def context(self) -> TCGGameContext:
        return self._context

    ###############################################################################################################################################
    @property
    def world_runtime(self) -> WorldRuntime:
        return self._world_runtime

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
        # TODO 加上所有processors pipeline
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
    def build_entities(self) -> "TCGGame":

        # 混沌系统
        self.chaos_engineering_system.initialize(self)
        self.chaos_engineering_system.on_pre_create_game()

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
        self.chaos_engineering_system.on_post_create_game()

        return self

    ###############################################################################################################################################
    # 测试！回复ecs
    def restore_entities(self) -> "TCGGame":
        self.context.restore_entities_from_snapshot(
            self.world_runtime.entities_snapshot
        )
        return self

    ###############################################################################################################################################
    def save(self) -> "TCGGame":

        self.world_runtime.entities_snapshot = self.context.make_entities_snapshot()

        assert self._world_runtime_path.exists()
        self._world_runtime_path.write_text(
            self.world_runtime.model_dump_json(), encoding="utf-8"
        )

        return self

    ###############################################################################################################################################
    def _create_world_system_entities(
        self,
        world_system_instances: List[WorldSystemInstance],
        data_base: WorldDataBase,
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in world_system_instances:

            prototype = data_base.world_systems.get(instance.name, None)
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

            prototype = data_base.actors.get(instance.name, None)
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
            actor_entity.add(
                FinalAppearanceComponent, instance.name, prototype.appearance
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
            assert not actor_entity.has(PlayerActorFlagComponent)
            actor_entity.add(PlayerActorFlagComponent, "")

        return actor_entities

    ###############################################################################################################################################
    def _create_stage_entities(
        self, stage_instances: List[StageInstance], data_base: WorldDataBase
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in stage_instances:

            prototype = data_base.stages.get(instance.name, None)
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
            stage_entity.add(
                StageEnvironmentComponent, instance.name, instance.kick_off_message
            )

            # 根据类型添加场景类型
            if prototype.type == StagePrototype.StageType.UNDIFINED:
                assert False, "stage type is not defined"
            elif prototype.type == StagePrototype.StageType.DUNGEON:
                stage_entity.add(DungeonStageFlagComponent, instance.name)
            elif prototype.type == StagePrototype.StageType.HOME:
                stage_entity.add(HomeStageFlagComponent, instance.name)

            # 添加场景可以连接的场景
            stage_entity.add(StageGraphComponent, instance.name, instance.next)

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
    # 临时的，考虑后面把player直接挂在context或者game里，因为player设计上唯一
    def get_player_entity(self) -> Optional[Entity]:
        player_entity = self._context.get_group(
            Matcher(
                all_of=[PlayerActorFlagComponent],
            )
        ).entities.copy()
        assert len(player_entity) == 1, "Player number is not 1"
        return next(iter(player_entity), None)

    ###############################################################################################################################################
    @property
    def players(self) -> List[PlayerProxy]:
        return self._players

    ###############################################################################################################################################
    def get_system_message(self, entity: Entity) -> str:

        data_base = self.world_runtime.root.data_base

        if entity.has(ActorComponent):
            actor_prototype = data_base.actors.get(entity._name, None)
            assert actor_prototype is not None
            if actor_prototype is not None:
                return actor_prototype.system_message

        elif entity.has(StageComponent):

            stage_prototype = data_base.stages.get(entity._name, None)
            assert stage_prototype is not None
            if stage_prototype is not None:
                return stage_prototype.system_message

        elif entity.has(WorldSystemComponent):

            world_system_prototype = data_base.world_systems.get(entity._name, None)
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
        if len(agent_short_term_memory.chat_history) == 0:
            agent_short_term_memory.chat_history.extend([SystemMessage(content=chat)])

    ###############################################################################################################################################
    def retrieve_actors_on_stage(self, entity: Entity) -> Set[Entity]:

        stage_entity = self.context.safe_get_stage_entity(entity)
        assert stage_entity is not None
        if stage_entity is None:
            return set()

        mapping = self.context.retrieve_stage_actor_mapping()
        if stage_entity not in mapping:
            return set()

        return mapping.get(stage_entity, set())

    ###############################################################################################################################################
    # def _initialize_prop_file_system(self) -> None:

    #     self._prop_file_system.clear()

    #     #
    #     world_root = self._world_runtime.root
    #     data_base = world_root.data_base

    #     # 所有的角色，包括玩家管理道具
    #     all_actors = world_root.actors + world_root.players
    #     for actor_instance in all_actors:
    #         for prop_instance in actor_instance.props:

    #             prop_prototype = self._get_prop_prototype(prop_instance, data_base)
    #             assert prop_prototype is not None
    #             if prop_prototype is None:
    #                 logger.error(f"db is None: {prop_instance.name}")
    #                 continue

    #             prop_file = PropFile(prop_instance, prop_prototype)
    #             self._prop_file_system.add_file(actor_instance.name, prop_file)

    #     # 所有的舞台，包括舞台管理道具
    #     for stage_instance in world_root.stages:
    #         for prop_instance in stage_instance.props:

    #             prop_prototype = self._get_prop_prototype(prop_instance, data_base)
    #             assert prop_prototype is not None
    #             if prop_prototype is None:
    #                 logger.error(f"db is None: {prop_instance.name}")
    #                 continue

    #             prop_file = PropFile(prop_instance, prop_prototype)
    #             self._prop_file_system.add_file(stage_instance.name, prop_file)

    ###############################################################################################################################################
    # def _get_prop_prototype(
    #     self, prop_instance: PropInstance, data_base: WorldDataBase
    # ) -> Optional[PropPrototype]:
    #     return data_base.props.get(prop_instance.name, None)

    ###############################################################################################################################################
    # TODO 目前是写死的
    def ready(self) -> bool:

        assert len(self._players) > 0
        if len(self._players) == 0:
            logger.error(f"no player proxy")
            return False

        player_entities: Set[Entity] = self.context.get_group(
            Matcher(all_of=[PlayerActorFlagComponent])
        ).entities

        assert len(player_entities) > 0
        if len(player_entities) == 0:
            logger.error(f"no player entity")
            return False

        only_one_player_entity = next(iter(player_entities))
        only_one_player_proxy = self._players[0]

        player_comp = only_one_player_entity.get(PlayerActorFlagComponent)
        assert player_comp is not None
        only_one_player_entity.replace(
            PlayerActorFlagComponent, only_one_player_proxy.player_name
        )

        logger.info(f"{self._name}, game ready!!!!!!!!!!!!!!!!!!!!")
        logger.info(f"player name = {only_one_player_proxy.player_name}")
        return True

    ###############################################################################################################################################
    def broadcast_event(
        self,
        entity: Entity,
        agent_event: AgentEvent,
        exclude_entities: Set[Entity] = set(),
    ) -> None:

        stage_entity = self.context.safe_get_stage_entity(entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        if stage_entity is None:
            return

        need_broadcast_entities = self.retrieve_actors_on_stage(stage_entity)
        need_broadcast_entities.add(stage_entity)

        if len(exclude_entities) > 0:
            need_broadcast_entities = need_broadcast_entities - exclude_entities

        self.notify_event(need_broadcast_entities, agent_event)

    ###############################################################################################################################################
    def notify_event(
        self,
        entities: Set[Entity],
        agent_event: AgentEvent,
    ) -> None:

        for entity in entities:

            # 针对agent的事件通知。
            replace_message = rpg_game_systems.prompt_utils.replace_with_you(
                agent_event.message, entity._name
            )
            self.append_human_message(entity, replace_message)
            logger.warning(f"事件通知 => {entity._name}:\n{replace_message}")

            # 如果是玩家，就要补充一个事件信息，用于客户端接收
            if entity.has(PlayerActorFlagComponent):
                player_comp = entity.get(PlayerActorFlagComponent)
                player_proxy = self.get_player(player_comp.name)
                assert player_proxy is not None
                if player_proxy is None:
                    continue

                player_proxy.append_event_to_notifications(
                    tag="", sendder="", event=agent_event
                )

    ###############################################################################################################################################
    def teleport_actors_to_stage(
        self, going_actors: Set[Entity], stage_name: str
    ) -> None:

        if len(going_actors) == 0:
            return

        # 找到目标stage
        target_stage = self.context.get_stage_entity(stage_name)
        if target_stage is None:
            logger.error(f"stage is None: {stage_name}")
            return

        # 得到stage和actor的对应关系
        stages_actor_map: Dict[Entity, Set[Entity]] = (
            self.context.retrieve_stage_actor_mapping()
        )
        # 得到传送者所在stage，和该stage内除传送者之外的其他actor的map
        # TODO 这个得改一下，应该是被传送的人和场景内其他人的对应关系，因为同行者也需要知道
        filtered_map: Dict[Entity, Set[Entity]] = {
            stage: actors - going_actors
            for stage, actors in stages_actor_map.items()
            if any(actor in going_actors for actor in actors)
        }

        for going_actor in going_actors:
            if going_actor is None or not going_actor.has(ActorComponent):
                assert False, "actor is None or have no actor component"
                return

            # 告知场景里的其他人，这个人被传送走了，不用boardcast，因为可能有人不会察觉到
            departure_stage = self._context.safe_get_stage_entity(going_actor)
            assert departure_stage is not None
            # 告知场景这个人被传送了
            for stay_actor in filtered_map[departure_stage]:
                # TODO 占位，判断这个人需不需要知道
                if False:
                    return
                # self.append_human_message(
                #     stay_actor, f"{going_actor._name}被传送到{stage_name}"
                # )
                self.append_human_message(
                    stay_actor,
                    f"{going_actor._name}被传送离开了当前场景:{departure_stage._name}",
                )
            # 告知被传送的人自己被传送了
            # 重新绑定actor和stage关系
