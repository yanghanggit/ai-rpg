from enum import Enum, IntEnum, unique
from entitas import Entity, Matcher  # type: ignore
from typing import Set, List, Optional, Union, final
from overrides import override
from loguru import logger
from game.tcg_game_context import TCGGameContext
from game.base_game import BaseGame
from game.tcg_game_process_pipeline import TCGGameProcessPipeline
from rpg_models.event_models import BaseEvent
from tcg_models.v_0_0_1 import (
    World,
    WorldSystemInstance,
    DataBase,
    ActorInstance,
    StageInstance,
    AgentShortTermMemory,
    ActorType,
    StageType,
)
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerActorFlagComponent,
    GUIDComponent,
    SystemMessageComponent,
    KickOffMessageComponent,
    FinalAppearanceComponent,
    StageEnvironmentComponent,
    HomeStageFlagComponent,
    DungeonStageFlagComponent,
    HeroActorFlagComponent,
    MonsterActorFlagComponent,
    # AttributeCompoment,
    EnterStageFlagComponent,
)
from player.player_proxy import PlayerProxy
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from extended_systems.lang_serve_system import LangServeSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from pathlib import Path
import rpg_game_systems.prompt_utils
from rpg_models.event_models import AgentEvent

# from extended_systems.tcg_game_battle_manager import BattleManager


@unique
@final
class TCGGameState(IntEnum):
    NONE = 0
    HOME = 1
    DUNGEON = 2


@unique
@final
class ConversationError(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


class TCGGame(BaseGame, TCGGameContext):

    def __init__(
        self,
        name: str,
        world: World,
        world_path: Path,
        langserve_system: LangServeSystem,
        # battle_manager: BattleManager,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:

        # 必须按着此顺序实现父
        BaseGame.__init__(self, name)  # 需要传递 name
        TCGGameContext.__init__(self)  # 继承 Context, 需要调用其 __init__

        # 世界运行时
        self._world: World = world
        self._world_file_path: Path = world_path

        # 处理器 与 对其控制的 状态。
        # self._game_state: TCGGameState = TCGGameState.NONE
        self._home_state_process_pipeline: TCGGameProcessPipeline = (
            TCGGameProcessPipeline.create_home_state_pipline(self)
        )
        self._dungeon_state_processing_pipeline: TCGGameProcessPipeline = (
            TCGGameProcessPipeline.create_dungeon_state_pipeline(self)
        )

        # 玩家
        self._player: PlayerProxy = PlayerProxy()

        # agent 系统
        self._langserve_system: LangServeSystem = langserve_system

        # 临时战斗系统
        # self._battle_manager = battle_manager

        # 混沌工程系统
        self._chaos_engineering_system: IChaosEngineering = chaos_engineering_system

    ###############################################################################################################################################
    @property
    def world_file_dir(self) -> Path:
        return self._world_file_path.parent

    ###############################################################################################################################################
    @property
    def current_game_state(self) -> TCGGameState:

        player_entity = self.get_player_entity()
        if player_entity is None:
            return TCGGameState.NONE

        stage_entity = self.safe_get_stage_entity(player_entity)
        assert stage_entity is not None
        if stage_entity is None:
            return TCGGameState.NONE

        if stage_entity.has(HomeStageFlagComponent):
            return TCGGameState.HOME
        elif stage_entity.has(DungeonStageFlagComponent):
            return TCGGameState.DUNGEON
        else:
            assert False, "stage type is not defined"

        return TCGGameState.NONE

    ###############################################################################################################################################
    @property
    def current_process_pipeline(self) -> TCGGameProcessPipeline:

        if self.current_game_state == TCGGameState.HOME:
            return self._home_state_process_pipeline
        elif self.current_game_state == TCGGameState.DUNGEON:
            return self._dungeon_state_processing_pipeline
        else:
            assert False, "game state is not defined"

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
    def world(self) -> World:
        return self._world

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        # 顺序不要动
        active_processing_pipeline = self.current_process_pipeline
        if not active_processing_pipeline._initialized:
            active_processing_pipeline._initialized = True
            active_processing_pipeline.activate_reactive_processors()
            active_processing_pipeline.initialize()

        active_processing_pipeline.execute()
        active_processing_pipeline.cleanup()

    ###############################################################################################################################################
    @override
    async def a_execute(self) -> None:
        # 顺序不要动
        active_process_pipeline = self.current_process_pipeline
        if not active_process_pipeline._initialized:
            active_process_pipeline._initialized = True
            active_process_pipeline.activate_reactive_processors()
            active_process_pipeline.initialize()

        await active_process_pipeline.a_execute()
        active_process_pipeline.cleanup()

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        # TODO 加上所有processors pipeline
        all = [
            self._home_state_process_pipeline,
            self._dungeon_state_processing_pipeline,
        ]
        for processor in all:
            processor.tear_down()
            processor.clear_reactive_processors()

        logger.info(f"{self._name}, game over!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    @override
    def send_message(self, player_proxy_names: Set[str], send_event: BaseEvent) -> None:
        pass

    ###############################################################################################################################################
    def build_entities(self) -> "TCGGame":

        # 混沌系统
        self.chaos_engineering_system.initialize(self)
        self.chaos_engineering_system.on_pre_create_game()

        #
        world_boot = self._world.boot

        ## 第1步，创建world_system
        self._create_world_system_entities(
            world_boot.world_systems, world_boot.data_base
        )

        ## 第2步，创建actor
        self._create_player_entities(world_boot.players, world_boot.data_base)
        self._create_actor_entities(world_boot.actors, world_boot.data_base)

        ## 第3步，创建stage
        self._create_stage_entities(world_boot.stages, world_boot.data_base)

        ## 最后！混沌系统，准备测试
        self.chaos_engineering_system.on_post_create_game()

        return self

    ###############################################################################################################################################
    # 测试！回复ecs
    def restore_entities(self) -> "TCGGame":
        self.restore_entities_from_snapshot(self.world.entities_snapshot)
        return self

    ###############################################################################################################################################
    def save(self) -> "TCGGame":

        self.world.entities_snapshot = self.make_entities_snapshot()

        assert self._world_file_path.exists()
        self._world_file_path.write_text(self.world.model_dump_json(), encoding="utf-8")

        return self

    ###############################################################################################################################################
    def _create_world_system_entities(
        self,
        world_system_instances: List[WorldSystemInstance],
        data_base: DataBase,
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in world_system_instances:

            prototype = data_base.world_systems.get(instance.prototype, None)
            assert prototype is not None
            if prototype is None:
                logger.error(f"db is None! {instance.name}: {instance.prototype}")
                continue

            # 创建实体
            world_system_entity = self.__create_entity__(instance.name)
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
        self, actor_instances: List[ActorInstance], data_base: DataBase
    ) -> List[Entity]:

        ret: List[Entity] = []
        for instance in actor_instances:

            prototype = data_base.actors.get(instance.prototype, None)
            assert prototype is not None
            if prototype is None:
                logger.error(f"db is None! {instance.name} : {instance.prototype}")
                continue

            # 创建实体
            actor_entity = self.__create_entity__(instance.name)
            assert actor_entity is not None

            # 必要组件：guid
            actor_entity.add(GUIDComponent, instance.name, instance.guid)

            # 必要组件：身份类型标记-角色Actor
            actor_entity.add(ActorComponent, instance.name, "")

            # 必要组件：系统消息
            actor_entity.add(
                SystemMessageComponent, instance.name, prototype.system_message
            )

            # 必要组件：启动消息
            actor_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

            # 必要组件：外观
            actor_entity.add(
                FinalAppearanceComponent, instance.name, prototype.appearance
            )

            # 必要组件：属性
            # actor_entity.add(
            #     AttributeCompoment,
            #     instance.name,
            #     instance.attributes[0],
            #     instance.attributes[1],
            #     instance.attributes[2],
            #     instance.attributes[3],
            #     instance.attributes[4],
            #     instance.attributes[5],
            #     instance.attributes[6],
            #     # instance.buffs,
            #     # instance.active_skills,
            #     # instance.trigger_skills,
            # )

            match prototype.type:

                case ActorType.HERO:
                    actor_entity.add(HeroActorFlagComponent, instance.name)
                case ActorType.MONSTER:
                    actor_entity.add(MonsterActorFlagComponent, instance.name)

            # 添加到返回值
            ret.append(actor_entity)

        return ret

    ###############################################################################################################################################
    def _create_player_entities(
        self, actor_instances: List[ActorInstance], data_base: DataBase
    ) -> List[Entity]:

        ret: List[Entity] = []
        ret = self._create_actor_entities(actor_instances, data_base)
        for entity in ret:
            assert not entity.has(PlayerActorFlagComponent)
            entity.add(PlayerActorFlagComponent, "")
        return ret

    ###############################################################################################################################################
    def _create_stage_entities(
        self, stage_instances: List[StageInstance], data_base: DataBase
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in stage_instances:

            prototype = data_base.stages.get(instance.prototype, None)
            assert prototype is not None
            if prototype is None:
                logger.error(f"db is None! {instance.name} : {instance.prototype}")
                continue

            # 创建实体
            stage_entity = self.__create_entity__(instance.name)

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

            if prototype.type == StageType.DUNGEON:
                stage_entity.add(DungeonStageFlagComponent, instance.name)
            elif prototype.type == StageType.HOME:
                stage_entity.add(HomeStageFlagComponent, instance.name)

            ## 重新设置Actor和stage的关系
            for actor_name in instance.actors:
                actor_entity: Optional[Entity] = self.get_actor_entity(actor_name)
                assert actor_entity is not None
                actor_entity.replace(ActorComponent, actor_name, instance.name)

            ret.append(stage_entity)

        return []

    ###############################################################################################################################################
    @property
    def player(self) -> PlayerProxy:
        return self._player

    ###############################################################################################################################################
    @player.setter
    def player(self, player_proxy: PlayerProxy) -> None:
        self._player = player_proxy

    ###############################################################################################################################################
    # 临时的，考虑后面把player直接挂在context或者game里，因为player设计上唯一
    def get_player_entity(self) -> Optional[Entity]:
        # player_entity = self.get_group(
        #     Matcher(
        #         all_of=[PlayerActorFlagComponent],
        #     )
        # ).entities.copy()
        # assert len(player_entity) == 1, "Player number is not 1"
        # return next(iter(player_entity), None)
        return self.get_entity_by_player_name(self.player.name)

    ###############################################################################################################################################
    def get_current_stage_entity(self) -> Optional[Entity]:
        player_entity = self.get_player_entity()
        assert player_entity is not None
        return self.safe_get_stage_entity(player_entity)

    ###############################################################################################################################################
    def get_system_message(self, entity: Entity) -> str:

        data_base = self.world.boot.data_base

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
        return self.world.agents_short_term_memory.setdefault(
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
    # TODO 目前是写死的
    def ready(self) -> bool:

        player_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[PlayerActorFlagComponent])
        ).entities

        assert len(player_entities) > 0
        if len(player_entities) == 0:
            logger.error(f"no player entity")
            return False

        player_actor_entity = next(iter(player_entities))
        player_comp = player_actor_entity.get(PlayerActorFlagComponent)
        assert player_comp is not None
        player_actor_entity.replace(PlayerActorFlagComponent, self.player.name)
        logger.info(f"{self._name}, game ready!!!!!!!!!!!!!!!!!!!!")
        logger.info(f"{self.player.name} => {player_actor_entity._name}")
        return True

    ###############################################################################################################################################
    def broadcast_event(
        self,
        entity: Entity,
        agent_event: AgentEvent,
        exclude_entities: Set[Entity] = set(),
    ) -> None:

        stage_entity = self.safe_get_stage_entity(entity)
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
                assert player_comp.name == self.player.name
                self.player.add_notification(event=agent_event)

    ###############################################################################################################################################
    # 传送角色set里的角色到指定场景，游戏层面的行为，会添加记忆但不会触发action
    def teleport_actors_to_stage(
        self, going_actors: Set[Entity], destination: Union[str, Entity]
    ) -> None:

        if len(going_actors) == 0:
            return

        for going_actor in going_actors:
            if going_actor is None or not going_actor.has(ActorComponent):
                assert False, "actor is None or have no actor component"
                return

        # 找到目标stage，否则报错
        target_stage = (
            self.get_stage_entity(destination)
            if isinstance(destination, str)
            else self.safe_get_stage_entity(destination)
        )
        if target_stage is None:
            destination = (
                destination._name if isinstance(destination, Entity) else destination
            )
            logger.error(
                f"该场景不存在: {destination}，请确认场景是否存在，是否有格式错误"
            )
            return

        # 传送前处理
        for going_actor in going_actors:

            # 检查自身是否已经在目标场景
            current_stage = self.safe_get_stage_entity(going_actor)
            assert current_stage is not None
            if current_stage is not None and current_stage == target_stage:
                logger.warning(f"{going_actor._name} 已经存在于 {target_stage._name}")
                continue

            # 向所在场景及所在场景内除自身外的其他人宣布，这货要离开了
            self.broadcast_event(
                current_stage,
                AgentEvent(
                    message=f"{going_actor._name} 传送离开了 {current_stage._name}",
                ),
                {going_actor},
            )
            # 再对他自己说你离开了
            self.notify_event(
                {going_actor},
                AgentEvent(
                    message=f"一束从天而降的奇异光束包裹了你，等你醒来后，发现你被传送离开了 {current_stage._name}",
                ),
            )

        # 传送中处理
        for going_actor in going_actors:

            # 更改所处场景的标识
            going_actor.replace(ActorComponent, going_actor._name, target_stage._name)

        # 传送后处理
        for going_actor in going_actors:

            # 向所在场景及所在场景内除自身外的其他人宣布，这货到了
            self.broadcast_event(
                target_stage,
                AgentEvent(
                    message=f"{going_actor._name} 传送到了 {target_stage._name}",
                ),
                {going_actor},
            )
            # 再对他自己说你到了
            self.notify_event(
                {going_actor},
                AgentEvent(
                    message=f"一束从天而降的奇异光束包裹了你，等你醒来后，发现你被传送到了 {target_stage._name}",
                ),
            )
            # 添加标记，有用。
            going_actor.replace(
                EnterStageFlagComponent, going_actor._name, target_stage._name
            )

        # if self.current_game_state == TCGGameState.DUNGEON:
        #     self._battle_manager._new_battle_refresh()

    ###############################################################################################################################################
    # 检查是否可以对话
    def validate_conversation(
        self, stage_or_actor: Entity, target_name: str
    ) -> ConversationError:

        actor_entity: Optional[Entity] = self.get_actor_entity(target_name)
        if actor_entity is None:
            return ConversationError.INVALID_TARGET

        current_stage_entity = self.safe_get_stage_entity(stage_or_actor)
        if current_stage_entity is None:
            return ConversationError.NO_STAGE

        target_stage_entity = self.safe_get_stage_entity(actor_entity)
        if target_stage_entity != current_stage_entity:
            return ConversationError.NOT_SAME_STAGE

        return ConversationError.VALID

    ###############################################################################################################################################
