from enum import Enum, IntEnum, unique
import uuid
import shutil
from ..entitas import Entity, Matcher
from typing import Any, Dict, Final, Set, List, Optional, cast, final
from overrides import override
from loguru import logger
from ..game.tcg_game_context import TCGGameContext, RetrieveMappingOptions
from ..game.base_game import BaseGame
from ..game.tcg_game_process_pipeline import TCGGameProcessPipeline
from ..models import (
    World,
    AgentShortTermMemory,
    StatusEffect,
    Combat,
    Dungeon,
    Engagement,
    WorldSystem,
    RPGCharacterProfile,
    Actor,
    Stage,
    ActorType,
    StageType,
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    RuntimeComponent,
    KickOffMessageComponent,
    AppearanceComponent,
    EnvironmentComponent,
    HomeComponent,
    DungeonComponent,
    HeroComponent,
    MonsterComponent,
    RPGCharacterProfileComponent,
    AgentEvent,
    TurnAction,
    HandComponent,
    SpeakAction,
    PlayerActiveComponent,
    DrawCardsAction,
    DeathComponent,
)
from ..models.components import XCardPlayerComponent
from ..player.player_proxy import PlayerProxy
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..chat_services.chat_system import ChatSystem
from ..chaos_engineering.chaos_engineering_system import IChaosEngineering
from pathlib import Path
import copy
import random
from ..config import DEFAULT_MONGODB_CONFIG, LOGS_DIR
from ..db.mongodb_world_document import WorldDocument
from ..db.mongodb_client import (
    mongodb_upsert_one,
    mongodb_find_one,
)


# ################################################################################################################################################
def _replace_name_with_you(input_text: str, your_name: str) -> str:

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
        player: PlayerProxy,
        world: World,
        # world_path: Path,
        chat_system: ChatSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:

        # 必须按着此顺序实现父
        BaseGame.__init__(self, name)  # 需要传递 name
        TCGGameContext.__init__(self)  # 继承 Context, 需要调用其 __init__

        # 世界运行时
        self._world: Final[World] = world
        # self._world_file_path: Final[Path] = world_path

        # 处理器 与 对其控制的 状态。
        self._home_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_home_state_pipline(self)
        )
        self._dungeon_combat_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_dungeon_combat_state_pipeline(self)
        )

        # 玩家
        self._player: PlayerProxy = player
        assert self._player.name != ""
        assert self._player.actor != ""

        # agent 系统
        self._chat_system: Final[ChatSystem] = chat_system

        # 混沌工程系统
        self._chaos_engineering_system: Final[IChaosEngineering] = (
            chaos_engineering_system
        )
        self.chaos_engineering_system.initialize(self)

        # 是否开启调试
        self._debug_flag_pipeline: bool = False

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        logger.debug(f"TCGGame destroy entity: {entity._name}")
        if entity._name in self.world.agents_short_term_memory:
            logger.debug(f"TCGGame destroy entity: {entity._name} in short term memory")
            self.world.agents_short_term_memory.pop(entity._name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    @property
    def verbose_dir(self) -> Path:

        dir = LOGS_DIR / f"{self.player.name}" / f"{self.name}"
        if not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        assert dir.exists()
        assert dir.is_dir()
        # logger.info(f"Verbose debug dir: {dir}")
        return dir

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
    def chat_system(self) -> ChatSystem:
        return self._chat_system

    ###############################################################################################################################################
    @property
    def chaos_engineering_system(self) -> IChaosEngineering:
        return self._chaos_engineering_system

    ###############################################################################################################################################
    @property
    def world(self) -> World:
        return self._world

    ###############################################################################################################################################
    @property
    def current_dungeon(self) -> Dungeon:
        assert isinstance(self._world.dungeon, Dungeon)
        return self._world.dungeon

    ###############################################################################################################################################
    @property
    def current_engagement(self) -> Engagement:
        return self.current_dungeon.engagement

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

        logger.warning(f"{self.name}, game over!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    def new_game(self) -> "TCGGame":

        assert len(self.world.entities_snapshot) == 0, "游戏中有实体，不能创建新的游戏"

        # 混沌系统
        self.chaos_engineering_system.on_pre_new_game()

        ## 第1步，创建world_system
        self._create_world_system_entities(self.world.boot.world_systems)

        ## 第2步，创建actor
        self._create_actor_entities(self.world.boot.actors)
        self._assign_player_to_actor()

        ## 第3步，创建stage
        self._create_stage_entities(self.world.boot.stages)

        ## 最后！混沌系统，准备测试
        self.chaos_engineering_system.on_post_new_game()

        return self

    ###############################################################################################################################################
    # 测试！回复ecs
    def load_game(self) -> "TCGGame":
        assert len(self.world.entities_snapshot) > 0, "游戏中没有实体，不能恢复游戏"
        self.restore_entities_from_snapshot(self.world.entities_snapshot)

        player_entity = self.get_player_entity()
        assert player_entity is not None
        assert player_entity.get(PlayerComponent).player_name == self.player.name

        return self

    ###############################################################################################################################################
    def save(self) -> "TCGGame":

        # 生成快照
        self.world.entities_snapshot = self.make_entities_snapshot()

        # 保存快照
        self._persist_world_to_mongodb()

        # debug
        self._verbose()
        return self

    ###############################################################################################################################################
    def _verbose(self) -> None:
        """调试方法，保存游戏状态到文件"""
        self._verbose_boot_data()
        self._verbose_entities_snapshot()
        self._verbose_chat_history()
        self._verbose_dungeon_system()

        logger.info(f"Verbose debug info saved to: {self.verbose_dir}")

    ###############################################################################################################################################
    def _persist_world_to_mongodb(self) -> None:
        """将游戏世界持久化到 MongoDB"""
        logger.info("📝 创建演示游戏世界并存储到 MongoDB...")

        version = "0.0.1"
        collection_name = DEFAULT_MONGODB_CONFIG.worlds_collection

        try:
            # 创建并保存 WorldDocument
            world_document = self._create_world_document(version)
            inserted_id = self._save_world_document_to_mongodb(
                world_document, collection_name
            )

            # 验证保存结果
            if inserted_id:
                self._verify_saved_world_document(collection_name)
            else:
                logger.error("❌ 演示游戏世界存储到 MongoDB 失败!")

        except Exception as e:
            logger.error(f"❌ 演示游戏世界 MongoDB 操作失败: {e}")
            raise

    ###############################################################################################################################################
    def _create_world_document(self, version: str) -> WorldDocument:
        """创建 WorldDocument 实例"""
        return WorldDocument.create_from_world(
            username=self.player.name, world=self.world, version=version
        )

    ###############################################################################################################################################
    def _save_world_document_to_mongodb(
        self, world_document: WorldDocument, collection_name: str
    ) -> Optional[str]:
        """保存 WorldDocument 到 MongoDB"""
        logger.info(f"📝 存储演示游戏世界到 MongoDB 集合: {collection_name}")
        inserted_id = mongodb_upsert_one(collection_name, world_document.to_dict())

        if inserted_id:
            logger.success("✅ 演示游戏世界已存储到 MongoDB!")

        return inserted_id

    ###############################################################################################################################################
    def _verify_saved_world_document(self, collection_name: str) -> None:
        """验证已保存的 WorldDocument"""
        logger.info("📖 从 MongoDB 获取演示游戏世界进行验证...")

        retrieved_world_data = mongodb_find_one(
            collection_name,
            {"username": self.player.name, "game_name": self.world.boot.name},
        )

        if not retrieved_world_data:
            logger.error("❌ 从 MongoDB 获取演示游戏世界失败!")
            return

        try:
            # 使用便捷方法反序列化为 WorldDocument 对象
            retrieved_world_document = WorldDocument.from_mongodb(retrieved_world_data)
            # logger.success(
            #     f"✅ 演示游戏世界已从 MongoDB 成功获取! = {retrieved_world_document.model_dump_json()}"
            # )

        except Exception as validation_error:
            logger.error(f"❌ WorldDocument 反序列化失败: {validation_error}")

    ###############################################################################################################################################
    def _verbose_chat_history(self) -> None:

        chat_history_dir = self.verbose_dir / "chat_history"
        chat_history_dir.mkdir(parents=True, exist_ok=True)

        for agent_name, agent_memory in self.world.agents_short_term_memory.items():
            chat_history_path = chat_history_dir / f"{agent_name}.json"
            chat_history_path.write_text(
                agent_memory.model_dump_json(), encoding="utf-8"
            )

    ###############################################################################################################################################
    def _verbose_boot_data(self) -> None:
        boot_data_dir = self.verbose_dir / "boot_data"
        boot_data_dir.mkdir(parents=True, exist_ok=True)

        boot_file_path = boot_data_dir / f"{self.world.boot.name}.json"
        if boot_file_path.exists():
            return  # 如果文件已存在，则不覆盖

        # 保存 Boot 数据到文件
        boot_file_path.write_text(self.world.boot.model_dump_json(), encoding="utf-8")

    ###############################################################################################################################################
    def _verbose_entities_snapshot(self) -> None:
        entities_snapshot_dir = self.verbose_dir / "entities_snapshot"
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

        if self.current_dungeon.name == "":
            return

        dungeon_system_dir = self.verbose_dir / "dungeons"
        dungeon_system_dir.mkdir(parents=True, exist_ok=True)
        dungeon_system_path = dungeon_system_dir / f"{self.current_dungeon.name}.json"
        dungeon_system_path.write_text(
            self.current_dungeon.model_dump_json(), encoding="utf-8"
        )

    ###############################################################################################################################################
    def _create_world_system_entities(
        self,
        world_system_instances: List[WorldSystem],
    ) -> List[Entity]:

        ret: List[Entity] = []

        for instance in world_system_instances:

            # break  # TODO, 先注释掉

            # 创建实体
            world_system_entity = self.__create_entity__(instance.name)
            assert world_system_entity is not None

            # 必要组件
            world_system_entity.add(
                RuntimeComponent,
                instance.name,
                self.world.next_runtime_index(),
                str(uuid.uuid4()),
            )
            world_system_entity.add(WorldSystemComponent, instance.name)

            # system prompt
            assert instance.name in instance.system_message
            self.append_system_message(world_system_entity, instance.system_message)

            # kickoff prompt
            world_system_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

            # 添加到返回值
            ret.append(world_system_entity)

        return ret

    ###############################################################################################################################################
    def _create_actor_entities(self, actor_instances: List[Actor]) -> List[Entity]:

        ret: List[Entity] = []
        for instance in actor_instances:

            # 创建实体
            actor_entity = self.__create_entity__(instance.name)
            assert actor_entity is not None

            # 必要组件：guid
            actor_entity.add(
                RuntimeComponent,
                instance.name,
                self.world.next_runtime_index(),
                str(uuid.uuid4()),
            )

            # 必要组件：身份类型标记-角色Actor
            actor_entity.add(ActorComponent, instance.name, "")

            # 必要组件：系统消息
            assert instance.name in instance.system_message
            self.append_system_message(actor_entity, instance.system_message)

            # 必要组件：启动消息
            actor_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

            # 必要组件：外观
            actor_entity.add(
                AppearanceComponent, instance.name, instance.character_sheet.appearance
            )

            # 必要组件：基础属性，这里用浅拷贝，不能动原有的。
            actor_entity.add(
                RPGCharacterProfileComponent,
                instance.name,
                copy.copy(instance.rpg_character_profile),
                [],
            )

            # 测试类型。
            character_profile_component = actor_entity.get(RPGCharacterProfileComponent)
            assert isinstance(
                character_profile_component.rpg_character_profile, RPGCharacterProfile
            )

            # 必要组件：类型标记
            match instance.character_sheet.type:
                case ActorType.HERO:
                    actor_entity.add(HeroComponent, instance.name)
                case ActorType.MONSTER:
                    actor_entity.add(MonsterComponent, instance.name)

            # 添加到返回值
            ret.append(actor_entity)

        return ret

    ###############################################################################################################################################
    def _create_stage_entities(self, stage_instances: List[Stage]) -> List[Entity]:

        ret: List[Entity] = []

        for instance in stage_instances:

            # 创建实体
            stage_entity = self.__create_entity__(instance.name)

            # 必要组件
            stage_entity.add(
                RuntimeComponent,
                instance.name,
                self.world.next_runtime_index(),
                str(uuid.uuid4()),
            )
            stage_entity.add(StageComponent, instance.name)

            # system prompt
            assert instance.name in instance.system_message
            self.append_system_message(stage_entity, instance.system_message)

            # kickoff prompt
            stage_entity.add(
                KickOffMessageComponent, instance.name, instance.kick_off_message
            )

            # 必要组件：环境描述
            stage_entity.add(
                EnvironmentComponent,
                instance.name,
                "",
            )

            # 必要组件：类型
            if instance.character_sheet.type == StageType.DUNGEON:
                stage_entity.add(DungeonComponent, instance.name)
            elif instance.character_sheet.type == StageType.HOME:
                stage_entity.add(HomeComponent, instance.name, [])

            ## 重新设置Actor和stage的关系
            for actor_instance in instance.actors:
                actor_entity: Optional[Entity] = self.get_actor_entity(
                    actor_instance.name
                )
                assert actor_entity is not None
                actor_entity.replace(ActorComponent, actor_instance.name, instance.name)

            ret.append(stage_entity)

        return []

    ###############################################################################################################################################
    @property
    def player(self) -> PlayerProxy:
        return self._player

    ###############################################################################################################################################
    def get_player_entity(self) -> Optional[Entity]:
        return self.get_entity_by_player_name(self.player.name)

    ###############################################################################################################################################
    def get_agent_short_term_memory(self, entity: Entity) -> AgentShortTermMemory:
        return self.world.agents_short_term_memory.setdefault(
            entity._name, AgentShortTermMemory(name=entity._name, chat_history=[])
        )

    ###############################################################################################################################################
    def append_system_message(self, entity: Entity, chat: str) -> None:
        logger.debug(f"append_system_message: {entity._name} => \n{chat}")
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        if len(agent_short_term_memory.chat_history) == 0:
            agent_short_term_memory.chat_history.extend([SystemMessage(content=chat)])

    ###############################################################################################################################################
    def append_human_message(self, entity: Entity, chat: str, **kwargs: Any) -> None:

        logger.debug(f"append_human_message: {entity._name} => \n{chat}")
        if len(kwargs) > 0:
            # 如果 **kwargs 不是 空，就打印一下，这种消息比较特殊。
            logger.debug(f"kwargs: {kwargs}")

        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.extend(
            [HumanMessage(content=chat, kwargs=kwargs)]
        )

    ###############################################################################################################################################
    def append_ai_message(self, entity: Entity, ai_message: AIMessage) -> None:
        logger.debug(f"append_ai_message: {entity._name} => \n{ai_message.content}")
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.append(ai_message)

    ###############################################################################################################################################
    def _assign_player_to_actor(self) -> bool:
        assert self.player.name != "", "玩家名字不能为空"
        assert self.player.actor != "", "玩家角色不能为空"

        actor_entity = self.get_actor_entity(self.player.actor)
        assert actor_entity is not None
        if actor_entity is None:
            return False

        assert not actor_entity.has(PlayerComponent)
        actor_entity.replace(PlayerComponent, self.player.name)
        logger.info(f"玩家: {self.player.name} 选择控制: {self.player.name}")
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

        # 正常的添加记忆。
        for entity in entities:
            replace_message = _replace_name_with_you(agent_event.message, entity._name)
            self.append_human_message(entity, replace_message)

            if entity.has(PlayerComponent):
                # 客户端拿到这个事件，用于处理业务。
                self.player.add_agent_event(agent_event=agent_event)

    ###############################################################################################################################################
    def stage_transition(self, actors: Set[Entity], stage_destination: Entity) -> None:

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

            # 从当前的行动队列里移除
            if current_stage.has(HomeComponent):
                home_comp = current_stage.get(HomeComponent)
                if actor_entity._name in home_comp.action_order:
                    home_comp.action_order.remove(actor_entity._name)
                    current_stage.replace(
                        HomeComponent,
                        home_comp.name,
                        home_comp.action_order,
                    )

            # 加入到目标场景的行动队列里
            if stage_destination.has(HomeComponent):
                home_comp = stage_destination.get(HomeComponent)
                if actor_entity._name not in home_comp.action_order:
                    home_comp.action_order.append(actor_entity._name)
                    stage_destination.replace(
                        HomeComponent,
                        home_comp.name,
                        home_comp.action_order,
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

    ###############################################################################################################################################
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
    def initialize_combat_components(self, actor_entity: Entity) -> None:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(RPGCharacterProfileComponent)

        rpg_character_profile_comp = actor_entity.get(RPGCharacterProfileComponent)
        assert isinstance(
            rpg_character_profile_comp.rpg_character_profile, RPGCharacterProfile
        )

        # 重置了。
        actor_entity.replace(
            RPGCharacterProfileComponent,
            actor_entity._name,
            copy.copy(rpg_character_profile_comp.rpg_character_profile),
            [],
        )

    ###############################################################################################################################################
    def update_combat_status_effects(
        self, entity: Entity, status_effects: List[StatusEffect]
    ) -> None:

        # 效果更新
        assert entity.has(RPGCharacterProfileComponent)
        character_profile_component = entity.get(RPGCharacterProfileComponent)

        current_effects = character_profile_component.status_effects
        for new_effect in status_effects:
            for i, e in enumerate(current_effects):
                if e.name == new_effect.name:
                    current_effects[i].name = new_effect.name
                    current_effects[i].description = new_effect.description
                    current_effects[i].rounds = new_effect.rounds
                    break
            else:
                current_effects.append(new_effect)

        entity.replace(
            RPGCharacterProfileComponent,
            character_profile_component.name,
            character_profile_component.rpg_character_profile,
            current_effects,
        )

    #######################################################################################################################################
    def _create_dungeon_entities(self, dungeon: Dungeon) -> None:

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for actor in dungeon.actors:
            actor_entity = self.get_actor_entity(actor.name)
            assert actor_entity is None, "actor_entity is not None"

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for stage in dungeon.levels:
            stage_entity = self.get_stage_entity(stage.name)
            assert stage_entity is None, "stage_entity is not None"

        # 正式创建。。。。。。。。。。
        # 创建地下城的怪物。
        self._create_actor_entities(dungeon.actors)
        ## 创建地下城的场景
        self._create_stage_entities(dungeon.levels)

    #######################################################################################################################################
    def _destroy_dungeon_entities(self, dungeon: Dungeon) -> None:

        # 清空地下城的怪物。
        for actor in dungeon.actors:
            actor_entity = self.get_actor_entity(actor.name)
            if actor_entity is not None:
                self.destroy_entity(actor_entity)

        # 清空地下城的场景
        for stage in dungeon.levels:
            stage_entity = self.get_stage_entity(stage.name)
            if stage_entity is not None:
                self.destroy_entity(stage_entity)

    #######################################################################################################################################
    def _clear_dungeon(self) -> None:
        self._destroy_dungeon_entities(self._world.dungeon)
        self._world.dungeon = Dungeon(name="")

    #######################################################################################################################################
    # TODO!!! 进入地下城。
    def launch_dungeon(self) -> bool:
        if self.current_dungeon.position < 0:
            self.current_dungeon.position = 0  # 第一次设置，第一个关卡。
            self._create_dungeon_entities(self.current_dungeon)
            heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
            return self._process_dungeon_advance(self.current_dungeon, heros_entities)
        else:
            # 第一次，必须是<0, 证明一次没来过。
            logger.error(f"launch_dungeon position = {self.current_dungeon.position}")

        return False

    #######################################################################################################################################
    # TODO, 地下城下一关。
    def advance_next_dungeon(self) -> None:
        # 位置+1
        if self.current_dungeon.advance_level():
            heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
            self._process_dungeon_advance(self.current_dungeon, heros_entities)

    #######################################################################################################################################
    # TODO, 进入地下城！
    def _process_dungeon_advance(
        self, dungeon: Dungeon, heros_entities: Set[Entity]
    ) -> bool:

        # 是否有可以进入的关卡？
        upcoming_dungeon = dungeon.current_level()
        assert upcoming_dungeon is not None
        if upcoming_dungeon is None:
            logger.error(
                f"{self.current_dungeon.name} 没有下一个地下城！position = {self.current_dungeon.position}"
            )
            return False

        # 下一个关卡实体, 没有就是错误的。
        stage_entity = self.get_stage_entity(upcoming_dungeon.name)
        assert stage_entity is not None
        assert stage_entity.has(DungeonComponent)
        if stage_entity is None:
            logger.error(f"{upcoming_dungeon.name} 没有对应的stage实体！")
            return False

        # 集体准备传送
        assert len(heros_entities) > 0
        if len(heros_entities) == 0:
            logger.error(f"没有英雄不能进入地下城!= {stage_entity._name}")
            return False

        logger.debug(
            f"{self.current_dungeon.name} = [{self.current_dungeon.position}]关为：{stage_entity._name}，可以进入！！！！"
        )

        # TODO, 准备提示词。
        trans_message = ""
        if dungeon.position == 0:
            trans_message = (
                f"""# 提示！你将要开始一次冒险，准备进入地下城: {stage_entity._name}"""
            )
        else:
            trans_message = f"""# 提示！你准备继续你的冒险，准备进入下一个地下城: {stage_entity._name}"""

        for hero_entity in heros_entities:
            self.append_human_message(hero_entity, trans_message)  # 添加故事

        # 开始传送。
        self.stage_transition(heros_entities, stage_entity)

        # 设置一个战斗为kickoff状态。
        dungeon.engagement.combat_kickoff(Combat(name=stage_entity._name))

        return True

    ###############################################################################################################################################
    # TODO!!! 临时测试准备传送！！！
    def return_to_home(self) -> None:

        heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
        assert len(heros_entities) > 0
        if len(heros_entities) == 0:
            logger.error("没有找到英雄!")
            return

        home_stage_entities = self.get_group(Matcher(all_of=[HomeComponent])).entities
        assert len(home_stage_entities) > 0
        if len(home_stage_entities) == 0:
            logger.error("没有找到家园!")
            return

        stage_entity = next(iter(home_stage_entities))
        prompt = f"""# 提示！冒险结束，你将要返回: {stage_entity._name}"""
        for hero_entity in heros_entities:

            # 添加故事。
            self.append_human_message(hero_entity, prompt)

        # 开始传送。
        self.stage_transition(heros_entities, stage_entity)

        # 设置空的地下城的数据。
        self._clear_dungeon()

        # 清除掉所有的战斗状态
        for hero_entity in heros_entities:

            # 不要的组件。
            if hero_entity.has(DeathComponent):
                logger.debug(f"remove death component: {hero_entity._name}")
                hero_entity.remove(DeathComponent)

            # 不要的组件
            if hero_entity.has(XCardPlayerComponent):
                logger.debug(f"remove xcard player component: {hero_entity._name}")
                hero_entity.remove(XCardPlayerComponent)

            # 生命全部恢复。
            assert hero_entity.has(RPGCharacterProfileComponent)
            rpg_character_profile_comp = hero_entity.get(RPGCharacterProfileComponent)
            rpg_character_profile_comp.rpg_character_profile.hp = (
                rpg_character_profile_comp.rpg_character_profile.max_hp
            )

    ###############################################################################################################################################
    def gen_map(
        self, options: RetrieveMappingOptions = RetrieveMappingOptions()
    ) -> Dict[str, List[str]]:

        entities_mapping = self._retrieve_stage_actor_mapping(options)
        if len(entities_mapping) == 0:
            return {}

        names_mapping: Dict[str, List[str]] = {}
        for stage_entity, actor_entities in entities_mapping.items():
            actor_names = {actor_entity._name for actor_entity in actor_entities}
            stage_name = stage_entity._name
            names_mapping[stage_name] = list(actor_names)

        return names_mapping

    ###############################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def execute_play_card(self) -> bool:

        if len(self.current_engagement.rounds) == 0:
            logger.error("没有回合，不能添加行动！")
            return False

        if not self.current_engagement.is_on_going_phase:
            logger.error("没有进行中的回合，不能添加行动！")
            return False

        last_round = self.current_engagement.last_round
        if last_round.is_round_complete:
            logger.error("回合已经完成，不能添加行动！")
            return False

        # 检查一遍，如果条件不满足也要出去。
        for turn_actor_name in last_round.round_turns:
            actor_entity = self.get_actor_entity(turn_actor_name)
            assert actor_entity is not None
            if actor_entity is None:
                logger.error(f"没有找到角色: {turn_actor_name}，不能添加行动！")
                return False

            if not actor_entity.has(HandComponent):
                logger.error(f"角色: {actor_entity._name} 没有手牌，不能添加行动！")
                return False

            hand_comp = actor_entity.get(HandComponent)
            assert len(hand_comp.skills) > 0
            if len(hand_comp.skills) == 0:
                logger.error(f"角色: {actor_entity._name} 没有技能可用，不能添加行动！")
                return False

        # 添加，到了这里就不能停了。
        for turn_actor_name in last_round.round_turns:

            actor_entity = self.get_actor_entity(turn_actor_name)
            assert actor_entity is not None
            assert not actor_entity.has(TurnAction)

            # TODO, 目前先随机选择一个技能。
            hand_comp = actor_entity.get(HandComponent)
            assert len(hand_comp.skills) > 0
            selected_skill = random.choice(hand_comp.skills)

            # 添加这个动作。
            actor_entity.replace(
                TurnAction,
                actor_entity._name,
                len(self.current_engagement.rounds),
                last_round.round_turns,
                selected_skill.name,
            )

        return True

    #######################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def activate_speak_action(self, target: str, content: str) -> bool:

        assert target != "", "target is empty"
        assert content != "", "content is empty"
        logger.debug(f"activate_speak_action: {target} => \n{content}")

        if content == "":
            logger.error("内容不能为空！")
            return False

        target_entity = self.get_actor_entity(target)
        if target_entity is None:
            logger.error(f"目标角色: {target} 不存在！")
            return False

        player_entity = self.get_player_entity()
        assert player_entity is not None
        data: Dict[str, str] = {target: content}
        player_entity.replace(SpeakAction, player_entity._name, data)
        player_entity.replace(PlayerActiveComponent, player_entity._name)  # 添加标记。

        return True

    #######################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def activate_draw_cards_action(self) -> None:

        player_entity = self.get_player_entity()
        assert player_entity is not None

        actor_entities = self.retrieve_actors_on_stage(player_entity)
        for entity in actor_entities:
            entity.replace(
                DrawCardsAction,
                entity._name,
            )

    #######################################################################################################################################
    def retrieve_recent_human_message_by_kargs(
        self, actor_entity: Entity, kwargs_key: str, kwargs_value: str
    ) -> Optional[HumanMessage]:

        chat_history = self.get_agent_short_term_memory(actor_entity).chat_history
        for chat_message in reversed(chat_history):

            if not isinstance(chat_message, HumanMessage):
                continue

            try:

                kwargs = chat_message.model_dump()["kwargs"]
                if kwargs == None:
                    continue

                cast_dict = cast(Dict[str, Any], kwargs)
                if not kwargs_key in cast_dict:
                    continue

                if cast_dict.get(kwargs_key) == kwargs_value:
                    return chat_message

            except Exception as e:
                logger.error(f"retrieve_recent_human_message_by_kargs error: {e}")
                continue

        return None

    ###############################################################################################################################################
    def clear_hands(self) -> None:
        actor_entities = self.get_group(Matcher(HandComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear hands: {entity._name}")
            entity.remove(HandComponent)

    #######################################################################################################################################
