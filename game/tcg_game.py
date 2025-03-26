from enum import Enum, IntEnum, unique
import shutil
from entitas import Entity, Matcher  # type: ignore
from typing import Any, Final, Set, List, Optional, final
from overrides import override
from loguru import logger
from game.tcg_game_context import TCGGameContext
from game.base_game import BaseGame
from game.tcg_game_process_pipeline import TCGGameProcessPipeline
from models.v_0_0_1 import (
    Effect,
    World,
    WorldSystemInstance,
    DataBase,
    ActorInstance,
    StageInstance,
    AgentShortTermMemory,
    ActorType,
    StageType,
)
from components.components_v_0_0_1 import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    GUIDComponent,
    SystemMessageComponent,
    KickOffMessageComponent,
    AppearanceComponent,
    StageEnvironmentComponent,
    HomeComponent,
    DungeonComponent,
    HeroComponent,
    MonsterComponent,
    # EnterStageComponent,
    CombatAttributesComponent,
    CombatEffectsComponent,
)
from player.player_proxy import PlayerProxy
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from extended_systems.lang_serve_system import LangServeSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from pathlib import Path
from models.event_models import AgentEvent
from extended_systems.combat_system import CombatSystem, Combat
from extended_systems.dungeon_system import DungeonSystem


# ################################################################################################################################################
def _replace_with_you(input_text: str, your_name: str) -> str:

    if len(input_text) == 0 or your_name not in input_text:
        return input_text

    at_name = f"@{your_name}"
    if at_name in input_text:
        # 如果有@名字，就略过
        return input_text

    return input_text.replace(your_name, "你")


###############################################################################################################################################
@unique
@final
class TCGGameState(IntEnum):
    NONE = 0
    HOME = 1
    DUNGEON = 2


###############################################################################################################################################
@unique
@final
class ConversationError(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


###############################################################################################################################################
class TCGGame(BaseGame, TCGGameContext):

    def __init__(
        self,
        name: str,
        world: World,
        world_path: Path,
        langserve_system: LangServeSystem,
        dungeon_system: DungeonSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:

        # 必须按着此顺序实现父
        BaseGame.__init__(self, name)  # 需要传递 name
        TCGGameContext.__init__(self)  # 继承 Context, 需要调用其 __init__

        # 世界运行时
        self._world: Final[World] = world
        self._world_file_path: Final[Path] = world_path

        # 处理器 与 对其控制的 状态。
        self._home_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_home_state_pipline(self)
        )
        self._dungeon_combat_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_dungeon_combat_state_pipeline(self)
        )

        # 玩家
        self._player: PlayerProxy = PlayerProxy(name="")

        # agent 系统
        self._langserve_system: Final[LangServeSystem] = langserve_system

        # 混沌工程系统
        self._chaos_engineering_system: Final[IChaosEngineering] = (
            chaos_engineering_system
        )

        # 地牢管理系统
        self._dungeon_system: DungeonSystem = dungeon_system

        # 是否开启调试
        self._debug_flag_pipeline: bool = False

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

        if stage_entity.has(HomeComponent):
            return TCGGameState.HOME
        elif stage_entity.has(DungeonComponent):
            return TCGGameState.DUNGEON
        else:
            assert False, "stage type is not defined"

        return TCGGameState.NONE

    ###############################################################################################################################################
    @property
    def current_process_pipeline(self) -> TCGGameProcessPipeline:

        if self.current_game_state == TCGGameState.HOME:
            return self._home_pipeline
        elif self.current_game_state == TCGGameState.DUNGEON:
            return self._dungeon_combat_pipeline
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
    def combat_system(self) -> CombatSystem:
        return self._dungeon_system.combat_system

    ###############################################################################################################################################
    @property
    def world(self) -> World:
        return self._world

    ###############################################################################################################################################
    @property
    def dungeon_system(self) -> DungeonSystem:
        return self._dungeon_system

    ###############################################################################################################################################
    @dungeon_system.setter
    def dungeon_system(self, value: DungeonSystem) -> None:
        if self._dungeon_system.name != "":
            self._verbose_dungeon_system()

        self._dungeon_system = value
        self._dungeon_system.log_dungeon_details()

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
            self._home_pipeline,
            self._dungeon_combat_pipeline,
        ]
        for processor in all:
            processor.tear_down()
            processor.clear_reactive_processors()

        logger.error(f"{self.name}, game over!!!!!!!!!!!!!!!!!!!!")

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
    def save(self, verbose: bool = True) -> "TCGGame":

        # 生成快照
        self.world.entities_snapshot = self.make_entities_snapshot()

        # 保存快照
        self._world_file_path.write_text(self.world.model_dump_json(), encoding="utf-8")

        # 保存聊天记录和boot
        if verbose:
            # 保存实体快照
            self._verbose_entities_snapshot()
            # 保存聊天记录
            self._verbose_chat_history()
            # 保存boot
            self._verbose_boot()
            # 保存地下城记录。
            self._verbose_dungeon_system()

        return self

    ###############################################################################################################################################
    def _verbose_chat_history(self) -> None:

        chat_history_dir = self.world_file_dir / "chat_history"
        chat_history_dir.mkdir(parents=True, exist_ok=True)

        for agent_name, agent_memory in self.world.agents_short_term_memory.items():
            chat_history_path = chat_history_dir / f"{agent_name}.json"
            chat_history_path.write_text(
                agent_memory.model_dump_json(), encoding="utf-8"
            )

    ###############################################################################################################################################
    def _verbose_boot(self) -> None:
        boot_dir = self.world_file_dir / "boot"
        boot_dir.mkdir(parents=True, exist_ok=True)

        actors = self.world.boot.players + self.world.boot.actors
        for actor in actors:
            actor_path = boot_dir / f"{actor.name}.json"
            actor_path.write_text(actor.model_dump_json(), encoding="utf-8")

        for stage in self.world.boot.stages:
            stage_path = boot_dir / f"{stage.name}.json"
            stage_path.write_text(stage.model_dump_json(), encoding="utf-8")

    ###############################################################################################################################################
    def _verbose_entities_snapshot(self) -> None:
        entities_snapshot_dir = self.world_file_dir / "entities_snapshot"
        # 强制删除一次
        if entities_snapshot_dir.exists():
            shutil.rmtree(entities_snapshot_dir)
        # 创建目录
        entities_snapshot_dir.mkdir(parents=True, exist_ok=True)
        assert entities_snapshot_dir.exists()

        for entity_snapshot in self.world.entities_snapshot:
            entity_snapshot_path = (
                entities_snapshot_dir / f"{entity_snapshot.name}.json"
            )
            entity_snapshot_path.write_text(
                entity_snapshot.model_dump_json(), encoding="utf-8"
            )

    ###############################################################################################################################################
    def _verbose_dungeon_system(self) -> None:

        if self.dungeon_system.name == "":
            return

        dungeon_system_dir = self.world_file_dir / "dungeons"
        dungeon_system_dir.mkdir(parents=True, exist_ok=True)
        dungeon_system_path = dungeon_system_dir / f"{self.dungeon_system.name}.json"
        dungeon_system_path.write_text(
            self.dungeon_system.model_dump_json(), encoding="utf-8"
        )

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
                SystemMessageComponent, instance.name, instance.system_message
            )
            assert instance.name in instance.system_message
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
                SystemMessageComponent, instance.name, instance.system_message
            )
            assert instance.name in instance.system_message

            # 必要组件：启动消息
            actor_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

            # 必要组件：外观
            actor_entity.add(AppearanceComponent, instance.name, prototype.appearance)

            # 必要组件：类型标记
            match prototype.type:

                case ActorType.HERO:
                    actor_entity.add(HeroComponent, instance.name)
                case ActorType.MONSTER:
                    actor_entity.add(MonsterComponent, instance.name)

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
            assert not entity.has(PlayerComponent)
            entity.add(PlayerComponent, "")
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
                SystemMessageComponent, instance.name, instance.system_message
            )
            assert instance.name in instance.system_message

            stage_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )
            stage_entity.add(
                StageEnvironmentComponent, instance.name, instance.kick_off_message
            )

            if prototype.type == StageType.DUNGEON:
                stage_entity.add(DungeonComponent, instance.name)
            elif prototype.type == StageType.HOME:
                stage_entity.add(HomeComponent, instance.name)

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
        return self.get_entity_by_player_name(self.player.name)

    ###############################################################################################################################################
    def get_agent_short_term_memory(self, entity: Entity) -> AgentShortTermMemory:
        return self.world.agents_short_term_memory.setdefault(
            entity._name, AgentShortTermMemory(name=entity._name, chat_history=[])
        )

    ###############################################################################################################################################
    def _remove_agent_short_term_memory(self, entity: Entity) -> None:
        self.world.agents_short_term_memory.pop(entity._name, None)

    ###############################################################################################################################################
    def append_human_message(self, entity: Entity, chat: str, **kwargs: Any) -> None:

        # 如果 **kwargs 不是 空，就打印一下
        if len(kwargs) > 0:
            logger.info(f"kwargs: {kwargs}")

        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.extend(
            [HumanMessage(content=chat, kwargs=kwargs)]
        )

    ###############################################################################################################################################
    def append_ai_message(self, entity: Entity, chat: str) -> None:
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.extend([AIMessage(content=chat)])

    ###############################################################################################################################################
    def append_system_message(self, entity: Entity, chat: str, **kwargs: Any) -> None:
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        if len(agent_short_term_memory.chat_history) == 0:
            agent_short_term_memory.chat_history.extend([SystemMessage(content=chat)])

    ###############################################################################################################################################
    # TODO 目前是写死的
    def confirm_player_actor_control_readiness(
        self, actor_instance: ActorInstance
    ) -> bool:

        # 玩家的名字，此时必须有
        assert self.player.name != ""
        if self.player.name == "":
            return False

        assert (
            self.get_entity_by_player_name(self.player.name) is None
        ), "玩家已经存在，不需要再次确认"

        player_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[PlayerComponent, ActorComponent])
        ).entities
        assert len(player_entities) > 0, "玩家实体不存在"

        for player_entity in player_entities:

            actor_comp = player_entity.get(ActorComponent)
            assert actor_comp is not None
            if actor_comp.name != actor_instance.name:
                continue

            # 找到了可以控制的actor，标记控制，将player的名字赋值给actor
            player_comp = player_entity.get(PlayerComponent)
            assert player_comp is not None
            assert player_comp.player_name == ""
            player_entity.replace(PlayerComponent, self.player.name)
            logger.info(f"玩家: {self.player.name} 选择控制: {player_entity._name}")

            return True

        assert False, "玩家没有准备好，没有找到可以控制的actor"
        return False

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
            replace_message = _replace_with_you(agent_event.message, entity._name)
            self.append_human_message(entity, replace_message)
            logger.warning(f"事件通知 => {entity._name}:\n{replace_message}")

            # 如果是玩家，就要补充一个事件信息，用于客户端接收
            if entity.has(PlayerComponent):
                player_comp = entity.get(PlayerComponent)
                assert player_comp.player_name == self.player.name
                self.player.add_notification(event=agent_event)

    ###############################################################################################################################################
    # 传送角色set里的角色到指定场景，游戏层面的行为，会添加记忆但不会触发action
    def _stage_transition(self, actors: Set[Entity], stage_destination: Entity) -> None:

        assert self._debug_flag_pipeline is False, "传送前，不允许在pipeline中"

        for actor1 in actors:
            assert actor1.has(ActorComponent)

        # 传送前处理
        for actor_entity in actors:

            # 检查自身是否已经在目标场景
            current_stage = self.safe_get_stage_entity(actor_entity)
            assert current_stage is not None
            if current_stage is not None and current_stage == stage_destination:
                logger.warning(
                    f"{actor_entity._name} 已经存在于 {stage_destination._name}"
                )
                continue

            # 向所在场景及所在场景内除自身外的其他人宣布，这货要离开了
            self.broadcast_event(
                entity=current_stage,
                agent_event=AgentEvent(
                    message=f"# 发生事件！{actor_entity._name} 离开了场景: {current_stage._name}",
                ),
                exclude_entities={actor_entity},
            )

        # 传送中处理
        for actor_entity in actors:

            current_stage = self.safe_get_stage_entity(actor_entity)
            assert current_stage is not None

            # 更改所处场景的标识
            actor_entity.replace(
                ActorComponent, actor_entity._name, stage_destination._name
            )

            self.notify_event(
                entities={actor_entity},
                agent_event=AgentEvent(
                    message=f"# 发生事件！{actor_entity._name} 从 场景: {current_stage._name} 离开，然后进入了 场景: {stage_destination._name}",
                ),
            )

        # 传送后处理
        for actor_entity in actors:

            # 向所在场景及所在场景内除自身外的其他人宣布，这货到了
            self.broadcast_event(
                entity=stage_destination,
                agent_event=AgentEvent(
                    message=f"# 发生事件！{actor_entity._name} 进入了 场景: {stage_destination._name}",
                ),
                exclude_entities={actor_entity},
            )
            # 添加标记，有用。
            # actor_entity.replace(
            #     EnterStageComponent, actor_entity._name, stage_destination._name
            # )

    ###############################################################################################################################################
    def stage_transition(self, actors: Set[Entity], destination: str) -> None:
        destination_stage = self.get_stage_entity(destination)
        if destination_stage is None:
            logger.error(f"目标场景不存在: {destination}")
            return
        self._stage_transition(actors, destination_stage)

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
    def retrieve_actor_instance(self, actor_entity: Entity) -> Optional[ActorInstance]:

        if not actor_entity.has(ActorComponent):
            return None

        all_actors = self.world.boot.players + self.world.boot.actors
        for actor in all_actors:
            if actor.name == actor_entity._name:
                return actor
        return None

    ###############################################################################################################################################
    def setup_combat_attributes(self, actor_entity: Entity) -> None:
        assert actor_entity.has(ActorComponent)
        if not actor_entity.has(ActorComponent):
            return

        actor_instance = self.retrieve_actor_instance(actor_entity)
        if actor_instance is None:
            return

        hp: Final[float] = actor_instance.base_attributes.hp
        max_hp: Final[float] = actor_instance.base_attributes.max_hp
        physical_attack: Final[float] = actor_instance.base_attributes.physical_attack
        physical_defense: Final[float] = actor_instance.base_attributes.physical_defense
        magic_attack: Final[float] = actor_instance.base_attributes.magic_attack
        magic_defense: Final[float] = actor_instance.base_attributes.magic_defense

        logger.info(
            f"""{actor_entity._name}-准备战斗属性:
hp: {hp}
max_hp: {max_hp}
physical_attack: {physical_attack}
physical_defense: {physical_defense}
magic_attack: {magic_attack}
magic_defense: {magic_defense}"""
        )

        actor_entity.replace(
            CombatAttributesComponent,
            actor_entity._name,
            hp,
            max_hp,
            physical_attack,
            physical_defense,
            magic_attack,
            magic_defense,
        )

        actor_entity.replace(CombatEffectsComponent, actor_entity._name, [])

    ###############################################################################################################################################
    # 刷新effects
    def update_combat_effects(self, entity: Entity, effects: List[Effect]) -> None:

        # 效果更新
        assert entity.has(CombatEffectsComponent)
        combat_effects_comp = entity.get(CombatEffectsComponent)
        assert combat_effects_comp is not None

        current_effects = combat_effects_comp.effects
        for new_effect in effects:
            for i, e in enumerate(current_effects):
                if e.name == new_effect.name:
                    current_effects[i].name = new_effect.name
                    current_effects[i].description = new_effect.description
                    current_effects[i].rounds = new_effect.rounds
                    break
            else:
                current_effects.append(new_effect)

        entity.replace(
            CombatEffectsComponent, combat_effects_comp.name, current_effects
        )

    ###############################################################################################################################################
    # TODO!!! 临时测试准备传送！！！
    def launch_dungeon_adventure(self) -> None:

        assert len(self.dungeon_system.levels) > 0, "没有地下城！"
        if len(self.dungeon_system.levels) == 0:
            logger.error("没有地下城！")
            return

        initial_dungeon_level = self.dungeon_system.levels[0]
        stage_entity = self.get_stage_entity(initial_dungeon_level.name)
        assert stage_entity is not None
        assert stage_entity.has(DungeonComponent)
        if stage_entity is None:
            return

        # 集体准备传送
        heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
        assert len(heros_entities) > 0
        if len(heros_entities) == 0:
            logger.error("没有找到英雄!")
            return

        trans_message = (
            f"""# 提示！你将要开始一次冒险，准备进入地下城: {stage_entity._name}"""
        )
        for hero_entity in heros_entities:
            # 添加故事
            logger.info(f"添加故事: {hero_entity._name} => {trans_message}")
            self.append_human_message(hero_entity, trans_message)

        # 开始传送。
        self._stage_transition(heros_entities, stage_entity)

        ## 设置一个战斗。
        assert len(self.dungeon_system.levels) > 0, "没有地下城！"
        assert self.dungeon_system.position == 0, "当前地下城关卡已经完成！"
        self.combat_system.combat_engagement(Combat(name=stage_entity._name))

    #######################################################################################################################################
    # TODO, 临时测试，准备传送！！！
    def advance_to_next_dungeon(self) -> None:

        # 位置+1
        self.dungeon_system.position += 1

        # 下一个关卡?
        next_level = self.dungeon_system.current_level()
        assert next_level is not None
        if next_level is None:
            logger.error("没有下一个地下城！")
            return

        # 下一个关卡实体, 没有就是错误的。
        stage_entity = self.get_stage_entity(next_level.name)
        assert stage_entity is not None
        assert stage_entity.has(DungeonComponent)
        if stage_entity is None:
            return

        logger.info(f"下一关为：{stage_entity._name}，可以进入！！！！")

        # 集体准备传送
        heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
        assert len(heros_entities) > 0
        if len(heros_entities) == 0:
            logger.error("没有找到英雄!")
            return

        trans_message = f"""# 提示！你准备继续你的冒险，准备进入下一个地下城: {stage_entity._name}"""
        for hero_entity in heros_entities:
            # 添加故事
            logger.info(f"添加故事: {hero_entity._name} => {trans_message}")
            self.append_human_message(hero_entity, trans_message)

        # 开始传送。
        self._stage_transition(heros_entities, stage_entity)

        # 设置一个战斗。
        assert len(self.dungeon_system.levels) > 0, "没有地下城！"
        assert self.dungeon_system.position > 0, "当前地下城关卡已经完成！"
        self.combat_system.combat_engagement(
            Combat(name=stage_entity._name)
        )  # 再开一场战斗！

    ###############################################################################################################################################
    # TODO!!! 临时测试准备传送！！！
    def home_stage_transition(
        self, trans_message: str, home_stage: StageInstance
    ) -> None:

        stage_entity = self.get_stage_entity(home_stage.name)
        assert stage_entity is not None
        assert stage_entity.has(HomeComponent)
        if stage_entity is None:
            return

        heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
        assert len(heros_entities) > 0
        if len(heros_entities) == 0:
            logger.error("没有找到英雄!")
            return

        for hero_entity in heros_entities:
            # 添加故事
            logger.info(f"添加故事: {hero_entity._name} => {trans_message}")
            self.append_human_message(hero_entity, trans_message)

            if hero_entity.has(CombatAttributesComponent):
                logger.info(f"删除战斗属性: {hero_entity._name}")
                hero_entity.remove(CombatAttributesComponent)
            if hero_entity.has(CombatEffectsComponent):
                logger.info(f"删除战斗效果: {hero_entity._name}")
                hero_entity.remove(CombatEffectsComponent)

        # 开始传送。
        self._stage_transition(heros_entities, stage_entity)

    ###############################################################################################################################################
    def get_player_stage_entity(self) -> Optional[Entity]:

        player_entity = self.get_player_entity()
        assert player_entity is not None
        if player_entity is None:
            return None

        return self.safe_get_stage_entity(player_entity)

    ###############################################################################################################################################
