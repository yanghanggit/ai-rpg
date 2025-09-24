import copy
import random
import shutil
import uuid
from enum import Enum, IntEnum, unique
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Set, Tuple, final
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger
from overrides import override
from ai_rpg.models.actions import PlanAction
from ..game.game_config import LOGS_DIR
from ..mongodb import (
    DEFAULT_MONGODB_CONFIG,
    WorldDocument,
    mongodb_find_one,
    mongodb_upsert_one,
)
from ..entitas import Entity, Matcher
from ..game.base_game import BaseGame
from ..game.tcg_game_context import TCGGameContext
from ..game.tcg_game_process_pipeline import TCGGameProcessPipeline
from ..models import (
    Actor,
    ActorComponent,
    ActorType,
    AgentEvent,
    AgentChatHistory,
    AppearanceComponent,
    Combat,
    DeathComponent,
    DrawCardsAction,
    Dungeon,
    DungeonComponent,
    Engagement,
    EnvironmentComponent,
    HandComponent,
    HeroComponent,
    HomeComponent,
    KickOffMessageComponent,
    MonsterComponent,
    PlayerComponent,
    RPGCharacterProfile,
    RPGCharacterProfileComponent,
    RuntimeComponent,
    Skill,
    SpeakAction,
    Stage,
    StageComponent,
    StageType,
    PlayCardsAction,
    World,
    WorldSystem,
    WorldSystemComponent,
    TransStageAction,
)
from ..models.components import XCardPlayerComponent
from .player_client import PlayerClient


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
class ConversationValidationResult(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


###############################################################################################################################################
class TCGGame(BaseGame, TCGGameContext):

    def __init__(
        self,
        name: str,
        player_client: PlayerClient,
        world: World,
    ) -> None:

        # 必须按着此顺序实现父
        BaseGame.__init__(self, name)  # 需要传递 name
        TCGGameContext.__init__(self)  # 继承 Context, 需要调用其 __init__

        # 世界运行时
        self._world: Final[World] = world

        # 常规home 的流程
        self._npc_home_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_npc_home_pipline(self)
        )

        # 仅处理player的home流程
        self._player_home_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_player_home_pipline(self)
        )

        # 地下城战斗流程
        self._dungeon_combat_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_dungeon_combat_state_pipeline(self)
        )

        self._all_pipelines: List[TCGGameProcessPipeline] = [
            self._npc_home_pipeline,
            self._player_home_pipeline,
            self._dungeon_combat_pipeline,
        ]

        # 玩家
        self._player_client: Final[PlayerClient] = player_client
        logger.debug(
            f"TCGGame init player: {self._player_client.name}: {self._player_client.actor}"
        )
        assert self._player_client.name != ""
        assert self._player_client.actor != ""

    ###############################################################################################################################################
    @property
    def player_client(self) -> PlayerClient:
        return self._player_client

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        logger.debug(f"TCGGame destroy entity: {entity.name}")
        if entity.name in self.world.agents_chat_history:
            logger.debug(f"TCGGame destroy entity: {entity.name} in short term memory")
            self.world.agents_chat_history.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    @property
    def verbose_dir(self) -> Path:

        dir = LOGS_DIR / f"{self.player_client.name}" / f"{self.name}"
        if not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        assert dir.exists()
        assert dir.is_dir()
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
    @property
    def npc_home_pipeline(self) -> TCGGameProcessPipeline:
        return self._npc_home_pipeline

    ###############################################################################################################################################
    @property
    def player_home_pipeline(self) -> TCGGameProcessPipeline:
        return self._player_home_pipeline

    ###############################################################################################################################################
    @property
    def dungeon_combat_pipeline(self) -> TCGGameProcessPipeline:
        return self._dungeon_combat_pipeline

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        # 关闭所有管道
        for processor in self._all_pipelines:
            processor.shutdown()
            logger.debug(f"Shutdown pipeline: {processor._name}")

        # 清空
        self._all_pipelines.clear()
        logger.warning(f"{self.name}, exit!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        # 初始化所有管道
        for processor in self._all_pipelines:
            processor.activate_reactive_processors()
            await processor.initialize()
            logger.debug(f"Initialized pipeline: {processor._name}")

    ###############################################################################################################################################
    def new_game(self) -> "TCGGame":

        assert len(self.world.entities_snapshot) == 0, "游戏中有实体，不能创建新的游戏"

        ## 第1步，创建world_system
        self._create_world_system_entities(self.world.boot.world_systems)

        ## 第2步，创建actor
        self._create_actor_entities(self.world.boot.actors)

        ## 第3步，分配玩家控制的actor
        self._assign_player_to_actor()

        ## 第4步，创建stage
        self._create_stage_entities(self.world.boot.stages)

        return self

    ###############################################################################################################################################
    # 测试！回复ecs
    def load_game(self) -> "TCGGame":
        assert len(self.world.entities_snapshot) > 0, "游戏中没有实体，不能恢复游戏"
        self.restore_entities_from_snapshot(self.world.entities_snapshot)

        player_entity = self.get_player_entity()
        assert player_entity is not None
        assert player_entity.get(PlayerComponent).player_name == self.player_client.name

        return self

    ###############################################################################################################################################
    def save(self) -> "TCGGame":

        # 生成快照
        self.world.entities_snapshot = self.make_entities_snapshot()
        logger.debug(f"游戏将要保存，实体数量: {len(self.world.entities_snapshot)}")

        # 保存快照
        self._persist_world_to_mongodb()

        # debug
        self._debug_verbose()

        return self

    ###############################################################################################################################################
    def _debug_verbose(self) -> "TCGGame":
        """调试方法，保存游戏状态到文件"""
        self._verbose_boot_data()
        self._verbose_world_data()
        self._verbose_entities_snapshot()
        self._verbose_chat_history()
        self._verbose_dungeon_system()
        logger.debug(f"Verbose debug info saved to: {self.verbose_dir}")
        return self

    ###############################################################################################################################################
    def _persist_world_to_mongodb(self) -> None:
        """将游戏世界持久化到 MongoDB"""
        logger.debug("📝 创建演示游戏世界并存储到 MongoDB...")

        version = "0.0.1"
        collection_name = DEFAULT_MONGODB_CONFIG.worlds_collection

        try:
            # 创建并保存 WorldDocument
            world_document = WorldDocument.create_from_world(
                username=self.player_client.name, world=self.world, version=version
            )
            # self._create_world_document(version)
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
    def _save_world_document_to_mongodb(
        self, world_document: WorldDocument, collection_name: str
    ) -> Optional[str]:
        """保存 WorldDocument 到 MongoDB"""
        logger.debug(f"📝 存储演示游戏世界到 MongoDB 集合: {collection_name}")
        inserted_id = mongodb_upsert_one(collection_name, world_document.to_dict())

        if inserted_id:
            logger.debug("✅ 演示游戏世界已存储到 MongoDB!")

        return inserted_id

    ###############################################################################################################################################
    def _verify_saved_world_document(self, collection_name: str) -> None:
        """验证已保存的 WorldDocument"""
        logger.debug("📖 从 MongoDB 获取演示游戏世界进行验证...")

        saved_world_data = mongodb_find_one(
            collection_name,
            {"username": self.player_client.name, "game_name": self.world.boot.name},
        )

        if not saved_world_data:
            logger.error("❌ 从 MongoDB 获取演示游戏世界失败!")
            return

        try:
            # 使用便捷方法反序列化为 WorldDocument 对象
            # _world_document = WorldDocument.from_mongodb(retrieved_world_data)
            # logger.success(
            #     f"✅ 演示游戏世界已从 MongoDB 成功获取! = {_world_document.model_dump_json()}"
            # )
            pass

        except Exception as validation_error:
            logger.error(f"❌ WorldDocument 反序列化失败: {validation_error}")

    ###############################################################################################################################################
    def _verbose_chat_history(self) -> None:

        chat_history_dir = self.verbose_dir / "chat_history"
        chat_history_dir.mkdir(parents=True, exist_ok=True)

        for agent_name, agent_memory in self.world.agents_chat_history.items():
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
    def _verbose_world_data(self) -> None:
        world_data_dir = self.verbose_dir / "world_data"
        world_data_dir.mkdir(parents=True, exist_ok=True)
        world_file_path = world_data_dir / f"{self.world.boot.name}.json"
        world_file_path.write_text(
            self.world.model_dump_json(), encoding="utf-8"
        )  # 保存 World 数据到文件，覆盖

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
                stage_entity.add(HomeComponent, instance.name)

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
    def get_player_entity(self) -> Optional[Entity]:
        return self.get_entity_by_player_name(self.player_client.name)

    ###############################################################################################################################################
    def get_agent_chat_history(self, entity: Entity) -> AgentChatHistory:
        return self.world.agents_chat_history.setdefault(
            entity.name, AgentChatHistory(name=entity.name, chat_history=[])
        )

    ###############################################################################################################################################
    def append_system_message(self, entity: Entity, chat: str) -> None:
        logger.debug(f"append_system_message: {entity.name} => \n{chat}")
        agent_chat_history = self.get_agent_chat_history(entity)
        assert (
            len(agent_chat_history.chat_history) == 0
        ), "system message should be the first message"
        agent_chat_history.chat_history.append(SystemMessage(content=chat))

    ###############################################################################################################################################
    def append_human_message(self, entity: Entity, chat: str, **kwargs: Any) -> None:

        logger.debug(f"append_human_message: {entity.name} => \n{chat}")
        if len(kwargs) > 0:
            # 如果 **kwargs 不是 空，就打印一下，这种消息比较特殊。
            logger.debug(f"kwargs: {kwargs}")

        agent_short_term_memory = self.get_agent_chat_history(entity)
        agent_short_term_memory.chat_history.extend(
            [HumanMessage(content=chat, **kwargs)]
        )

    ###############################################################################################################################################
    def append_ai_message(self, entity: Entity, ai_messages: List[AIMessage]) -> None:

        assert len(ai_messages) > 0, "ai_messages should not be empty"
        for ai_message in ai_messages:
            assert isinstance(ai_message, AIMessage)
            assert ai_message.content != "", "ai_message content should not be empty"
            logger.debug(f"append_ai_message: {entity.name} => \n{ai_message.content}")

        # 添加多条 AIMessage
        agent_short_term_memory = self.get_agent_chat_history(entity)
        agent_short_term_memory.chat_history.extend(ai_messages)

    ###############################################################################################################################################
    def _assign_player_to_actor(self) -> bool:
        assert self.player_client.name != "", "玩家名字不能为空"
        assert self.player_client.actor != "", "玩家角色不能为空"

        actor_entity = self.get_actor_entity(self.player_client.actor)
        assert actor_entity is not None
        if actor_entity is None:
            return False

        assert not actor_entity.has(PlayerComponent)
        actor_entity.replace(PlayerComponent, self.player_client.name)
        logger.info(
            f"玩家: {self.player_client.name} 选择控制: {self.player_client.name}"
        )
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

        need_broadcast_entities = self.get_alive_actors_on_stage(stage_entity)
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
            replace_message = _replace_name_with_you(agent_event.message, entity.name)
            self.append_human_message(entity, replace_message)

        # 最后都要发给客户端。
        self.player_client.add_agent_event_message(agent_event=agent_event)

    ###############################################################################################################################################
    def _validate_stage_transition_prerequisites(
        self, actors: Set[Entity], stage_destination: Entity
    ) -> Set[Entity]:
        """
        验证场景传送的前置条件并过滤有效的角色

        Args:
            actors: 需要传送的角色集合
            stage_destination: 目标场景

        Returns:
            Set[Entity]: 需要实际传送的角色集合（排除已在目标场景的角色）
        """
        # 验证所有角色都有ActorComponent
        for actor in actors:
            assert actor.has(ActorComponent), f"角色 {actor.name} 缺少 ActorComponent"

        # 过滤掉已经在目标场景的角色
        actors_to_transfer = set()
        for actor_entity in actors:
            current_stage = self.safe_get_stage_entity(actor_entity)
            assert current_stage is not None, f"角色 {actor_entity.name} 没有当前场景"

            if current_stage == stage_destination:
                logger.warning(
                    f"{actor_entity.name} 已经存在于 {stage_destination.name}"
                )
                continue

            actors_to_transfer.add(actor_entity)

        return actors_to_transfer

    ###############################################################################################################################################
    def _handle_actors_leaving_stage(self, actors: Set[Entity]) -> None:
        """
        处理角色离开场景的通知

        Args:
            actors: 要离开的角色集合
        """
        for actor_entity in actors:
            current_stage = self.safe_get_stage_entity(actor_entity)
            assert current_stage is not None

            # 向所在场景及所在场景内除自身外的其他人宣布，这货要离开了
            self.broadcast_event(
                entity=current_stage,
                agent_event=AgentEvent(
                    message=f"# 发生事件！{actor_entity.name} 离开了场景: {current_stage.name}",
                ),
                exclude_entities={actor_entity},
            )

    ###############################################################################################################################################
    def _execute_actors_stage_transfer(
        self, actors: Set[Entity], stage_destination: Entity
    ) -> None:
        """
        执行角色的场景传送，包括更新场景归属和行动队列

        Args:
            actors: 要传送的角色集合
            stage_destination: 目标场景
        """
        for actor_entity in actors:
            current_stage = self.safe_get_stage_entity(actor_entity)
            assert current_stage is not None

            # 更改所处场景的标识
            actor_entity.replace(
                ActorComponent, actor_entity.name, stage_destination.name
            )

            # 通知角色自身的传送过程
            self.notify_event(
                entities={actor_entity},
                agent_event=AgentEvent(
                    message=f"# 发生事件！{actor_entity.name} 从 场景: {current_stage.name} 离开，然后进入了 场景: {stage_destination.name}",
                ),
            )

    ###############################################################################################################################################
    def _handle_actors_entering_stage(
        self, actors: Set[Entity], stage_destination: Entity
    ) -> None:
        """
        处理角色进入场景的通知

        Args:
            actors: 进入的角色集合
            stage_destination: 目标场景
        """
        for actor_entity in actors:
            # 向所在场景及所在场景内除自身外的其他人宣布，这货到了
            self.broadcast_event(
                entity=stage_destination,
                agent_event=AgentEvent(
                    message=f"# 发生事件！{actor_entity.name} 进入了 场景: {stage_destination.name}",
                ),
                exclude_entities={actor_entity},
            )

    ###############################################################################################################################################
    def stage_transition(self, actors: Set[Entity], stage_destination: Entity) -> None:
        """
        场景传送的主协调函数

        Args:
            actors: 需要传送的角色集合
            stage_destination: 目标场景
        """
        # 1. 验证前置条件并过滤有效角色
        actors_to_transfer = self._validate_stage_transition_prerequisites(
            actors, stage_destination
        )

        # 如果没有角色需要传送，直接返回
        if not actors_to_transfer:
            return

        # 2. 处理角色离开场景
        self._handle_actors_leaving_stage(actors_to_transfer)

        # 3. 执行场景传送
        self._execute_actors_stage_transfer(actors_to_transfer, stage_destination)

        # 4. 处理角色进入场景
        self._handle_actors_entering_stage(actors_to_transfer, stage_destination)

    ###############################################################################################################################################
    def validate_conversation(
        self, stage_or_actor: Entity, target_name: str
    ) -> ConversationValidationResult:

        actor_entity: Optional[Entity] = self.get_actor_entity(target_name)
        if actor_entity is None:
            return ConversationValidationResult.INVALID_TARGET

        current_stage_entity = self.safe_get_stage_entity(stage_or_actor)
        if current_stage_entity is None:
            return ConversationValidationResult.NO_STAGE

        target_stage_entity = self.safe_get_stage_entity(actor_entity)
        if target_stage_entity != current_stage_entity:
            return ConversationValidationResult.NOT_SAME_STAGE

        return ConversationValidationResult.VALID

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
            return self._dungeon_advance(self.current_dungeon, heros_entities)
        else:
            # 第一次，必须是<0, 证明一次没来过。
            logger.error(f"launch_dungeon position = {self.current_dungeon.position}")

        return False

    #######################################################################################################################################
    # TODO, 地下城下一关。
    def next_dungeon(self) -> None:
        # 位置+1
        if self.current_dungeon.advance_level():
            heros_entities = self.get_group(Matcher(all_of=[HeroComponent])).entities
            self._dungeon_advance(self.current_dungeon, heros_entities)

    #######################################################################################################################################
    def _validate_dungeon_advance_prerequisites(
        self, dungeon: Dungeon, heros_entities: Set[Entity]
    ) -> Tuple[bool, Optional[Entity]]:
        """
        验证地下城推进的前置条件

        Returns:
            Tuple[是否验证通过, 场景实体(如果验证通过)]
        """
        # 是否有可以进入的关卡？
        upcoming_dungeon = dungeon.current_level()
        if upcoming_dungeon is None:
            logger.error(
                f"{self.current_dungeon.name} 没有下一个地下城！position = {self.current_dungeon.position}"
            )
            return False, None

        # 下一个关卡实体, 没有就是错误的。
        stage_entity = self.get_stage_entity(upcoming_dungeon.name)
        if stage_entity is None or not stage_entity.has(DungeonComponent):
            logger.error(f"{upcoming_dungeon.name} 没有对应的stage实体！")
            return False, None

        # 集体准备传送
        if len(heros_entities) == 0:
            logger.error(f"没有英雄不能进入地下城!= {stage_entity.name}")
            return False, None

        logger.debug(
            f"{self.current_dungeon.name} = [{self.current_dungeon.position}]关为：{stage_entity.name}，可以进入！！！！"
        )

        return True, stage_entity

    #######################################################################################################################################
    def _generate_and_send_dungeon_transition_message(
        self, dungeon: Dungeon, stage_entity: Entity, heros_entities: Set[Entity]
    ) -> None:
        """
        生成并发送地下城传送提示消息
        """
        # 准备提示词
        if dungeon.position == 0:
            trans_message = (
                f"""# 提示！你将要开始一次冒险，准备进入地下城: {stage_entity.name}"""
            )
        else:
            trans_message = f"""# 提示！你准备继续你的冒险，准备进入下一个地下城: {stage_entity.name}"""

        for hero_entity in heros_entities:
            self.append_human_message(hero_entity, trans_message)  # 添加故事

    #######################################################################################################################################
    def _setup_dungeon_kickoff_messages(self, stage_entity: Entity) -> None:
        """
        设置地下城场景和怪物的KickOff消息
        """
        # 需要在这里补充设置地下城与怪物的kickoff信息。
        stage_kick_off_comp = stage_entity.get(KickOffMessageComponent)
        assert stage_kick_off_comp is not None
        logger.debug(
            f"当前 {stage_entity.name} 的kickoff信息: {stage_kick_off_comp.content}"
        )

        # 获取场景内角色的外貌信息
        actors_appearances_mapping: Dict[str, str] = self.get_stage_actor_appearances(
            stage_entity
        )

        # 重新组织一下
        actors_appearances_info = []
        for actor_name, appearance in actors_appearances_mapping.items():
            actors_appearances_info.append(f"{actor_name}: {appearance}")
        if len(actors_appearances_info) == 0:
            actors_appearances_info.append("无")

        # 生成追加的kickoff信息
        append_kickoff_message = f"""# 场景内角色
{"\n".join(actors_appearances_info)}"""

        # 设置组件
        stage_entity.replace(
            KickOffMessageComponent,
            stage_kick_off_comp.name,
            stage_kick_off_comp.content + "\n" + append_kickoff_message,
        )
        logger.debug(
            f"更新设置{stage_entity.name} 的kickoff信息: {stage_entity.get(KickOffMessageComponent).content}"
        )

        # 设置怪物的kickoff信息
        actors = self.get_alive_actors_on_stage(stage_entity)
        for actor in actors:
            if actor.has(MonsterComponent):
                monster_kick_off_comp = actor.get(KickOffMessageComponent)
                assert monster_kick_off_comp is not None
                logger.debug(
                    f"需要设置{actor.name} 的kickoff信息: {monster_kick_off_comp.content}"
                )

    #######################################################################################################################################
    # TODO, 进入地下城！
    def _dungeon_advance(self, dungeon: Dungeon, heros_entities: Set[Entity]) -> bool:
        """
        地下城关卡推进的主协调函数

        Args:
            dungeon: 地下城实例
            heros_entities: 英雄实体集合

        Returns:
            bool: 是否成功推进到下一关卡
        """
        # 1. 验证前置条件
        is_valid, stage_entity = self._validate_dungeon_advance_prerequisites(
            dungeon, heros_entities
        )
        if not is_valid or stage_entity is None:
            return False

        # 2. 生成并发送传送提示消息
        self._generate_and_send_dungeon_transition_message(
            dungeon, stage_entity, heros_entities
        )

        # 3. 执行场景传送
        self.stage_transition(heros_entities, stage_entity)

        # 4. 设置KickOff消息
        self._setup_dungeon_kickoff_messages(stage_entity)

        # 5. 初始化战斗状态
        dungeon.engagement.combat_kickoff(Combat(name=stage_entity.name))

        return True

    ###############################################################################################################################################
    # TODO!!! 临时测试准备传送！！！
    def return_home(self) -> None:

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
        prompt = f"""# 提示！冒险结束，你将要返回: {stage_entity.name}"""
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
                logger.debug(f"remove death component: {hero_entity.name}")
                hero_entity.remove(DeathComponent)

            # 不要的组件
            if hero_entity.has(XCardPlayerComponent):
                logger.debug(f"remove xcard player component: {hero_entity.name}")
                hero_entity.remove(XCardPlayerComponent)

            # 生命全部恢复。
            assert hero_entity.has(RPGCharacterProfileComponent)
            rpg_character_profile_comp = hero_entity.get(RPGCharacterProfileComponent)
            rpg_character_profile_comp.rpg_character_profile.hp = (
                rpg_character_profile_comp.rpg_character_profile.max_hp
            )

    ###############################################################################################################################################
    def get_stage_actor_distribution(
        self,
    ) -> Dict[Entity, List[Entity]]:

        ret: Dict[Entity, List[Entity]] = {}

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        # 以stage为key，actor为value
        for actor_entity in actor_entities:

            stage_entity = self.safe_get_stage_entity(actor_entity)
            assert stage_entity is not None, f"actor_entity = {actor_entity}"
            if stage_entity is None:
                continue

            ret.setdefault(stage_entity, []).append(actor_entity)

        # 补一下没有actor的stage
        stage_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[StageComponent])
        ).entities
        for stage_entity in stage_entities:
            if stage_entity not in ret:
                ret.setdefault(stage_entity, [])

        return ret

    ###############################################################################################################################################
    def get_stage_actor_distribution_mapping(
        self,
    ) -> Dict[str, List[str]]:

        ret: Dict[str, List[str]] = {}
        mapping = self.get_stage_actor_distribution()

        for stage_entity, actor_entities in mapping.items():
            ret[stage_entity.name] = [
                actor_entity.name for actor_entity in actor_entities
            ]

        return ret

    ###############################################################################################################################################
    # TODO, 临时添加行动, 逻辑。 activate_play_cards_action
    def play_cards_action(
        self, skill_execution_plan_options: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        激活打牌行动，为所有轮次中的角色选择技能并设置执行计划。

        Args:
            skill_execution_plan_options: 可选的技能执行计划选项
                格式: {技能名称: 目标名称}
                如果提供，会优先选择指定的技能并使用指定的目标

        Returns:
            bool: 是否成功激活打牌行动
        """

        # 1. 验证游戏状态
        if not self._validate_combat_state():
            return False

        if skill_execution_plan_options is not None:
            logger.debug(f"收到技能执行计划选项: {skill_execution_plan_options}")

        # 2. 验证所有角色的手牌状态
        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent, HandComponent], none_of=[DeathComponent])
        ).entities

        if len(actor_entities) == 0:
            logger.error("没有存活的并拥有手牌的角色，不能添加行动！")
            return False

        # 测试一下！
        for actor_entity in actor_entities:

            # 必须没有打牌行动
            assert (
                actor_entity.name in self.current_engagement.last_round.round_turns
            ), f"{actor_entity.name} 不在本回合行动队列里"

            # 必须没有打牌行动
            hand_comp = actor_entity.get(HandComponent)
            assert len(hand_comp.skills) > 0, f"{actor_entity.name} 没有技能可用"

            if not self._setup_actor_play_cards_action(
                actor_entity, skill_execution_plan_options
            ):
                assert False, f"为角色 {actor_entity.name} 设置打牌行动失败"

        return True

    ###############################################################################################################################################
    def _validate_combat_state(self) -> bool:
        """验证战斗状态是否允许添加行动"""
        if len(self.current_engagement.rounds) == 0:
            logger.error("没有回合，不能添加行动！")
            return False

        if not self.current_engagement.is_on_going_phase:
            logger.error("没有进行中的回合，不能添加行动！")
            return False

        if self.current_engagement.last_round.has_ended:
            logger.error("回合已经完成，不能添加行动！")
            return False

        return True

    ###############################################################################################################################################
    def _setup_actor_play_cards_action(
        self,
        actor_entity: Entity,
        skill_execution_plan_options: Optional[Dict[str, str]],
    ) -> bool:
        """为单个角色设置打牌行动"""

        assert not actor_entity.has(PlayCardsAction)
        hand_comp = actor_entity.get(HandComponent)

        # 选择技能和目标
        selected_skill, final_target = self._select_skill_and_target(
            actor_entity, hand_comp, skill_execution_plan_options
        )

        if selected_skill is None:
            logger.error(f"无法为角色 {actor_entity.name} 选择技能")
            return False

        # 创建打牌行动
        actor_entity.replace(
            PlayCardsAction,
            actor_entity.name,
            selected_skill,
            final_target,
        )

        return True

    ###############################################################################################################################################
    def _select_skill_and_target(
        self,
        actor_entity: Entity,
        hand_comp: HandComponent,
        skill_execution_plan_options: Optional[Dict[str, str]],
    ) -> Tuple[Optional[Skill], str]:
        """
        为角色选择技能和目标

        Returns:
            Tuple[技能对象, 最终目标]
        """

        selected_skill = None
        target_override = None

        # 优先从指定选项中选择技能
        if skill_execution_plan_options is not None:
            for skill in hand_comp.skills:
                if skill.name in skill_execution_plan_options:
                    selected_skill = skill
                    target_override = skill_execution_plan_options[skill.name]
                    logger.debug(
                        f"为角色 {actor_entity.name} 选择指定技能: {skill.name}, 目标: {target_override}"
                    )
                    break

        # 如果没有找到指定技能，随机选择
        if selected_skill is None:
            selected_skill = random.choice(hand_comp.skills)
            logger.debug(
                f"为角色 {actor_entity.name} 随机选择技能: {selected_skill.name}"
            )

        # 确定最终目标
        if target_override is not None:
            final_target = target_override
        else:
            final_target = selected_skill.target

        return selected_skill, final_target

    #######################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def speak_action(self, target: str, content: str) -> bool:

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
        player_entity.replace(SpeakAction, player_entity.name, data)

        return True

    #######################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def draw_cards_action(self) -> None:

        player_entity = self.get_player_entity()
        assert player_entity is not None

        actor_entities = self.get_alive_actors_on_stage(player_entity)
        for entity in actor_entities:
            entity.replace(
                DrawCardsAction,
                entity.name,
            )

    #######################################################################################################################################
    def new_round(self) -> bool:

        if not self.current_engagement.is_on_going_phase:
            logger.warning("当前没有进行中的战斗，不能设置回合。")
            return False

        if (
            len(self.current_engagement.rounds) > 0
            and not self.current_engagement.last_round.has_ended
        ):
            # 有回合正在进行中，所以不能添加新的回合。
            logger.warning("有回合正在进行中，所以不能添加新的回合。")
            return False

        # 排序角色
        player_entity = self.get_player_entity()
        assert player_entity is not None
        actors_on_stage = self.get_alive_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0
        shuffled_reactive_entities = self._shuffle_action_order(list(actors_on_stage))

        # 场景描写加上。
        first_entity = next(iter(shuffled_reactive_entities))
        stage_entity = self.safe_get_stage_entity(first_entity)
        assert stage_entity is not None
        stage_environment_comp = stage_entity.get(EnvironmentComponent)

        round = self.current_engagement.new_round(
            round_turns=[entity.name for entity in shuffled_reactive_entities]
        )

        round.environment = stage_environment_comp.description
        logger.info(f"new_round:\n{round.model_dump_json()}")
        return True

    #######################################################################################################################################
    # 随机排序
    def _shuffle_action_order(self, actor_entities: List[Entity]) -> List[Entity]:
        shuffled_reactive_entities = actor_entities.copy()
        random.shuffle(shuffled_reactive_entities)
        return shuffled_reactive_entities

    #######################################################################################################################################
    # 正式的排序方式，按着敏捷度排序
    def _sort_action_order_by_dex(self, actor_entities: List[Entity]) -> List[Entity]:

        actor_dexterity_pairs: List[Tuple[Entity, int]] = []
        for entity in actor_entities:

            assert entity.has(RPGCharacterProfileComponent)
            rpg_character_profile_component = entity.get(RPGCharacterProfileComponent)
            actor_dexterity_pairs.append(
                (
                    entity,
                    rpg_character_profile_component.rpg_character_profile.dexterity,
                )
            )

        return [
            entity
            for entity, _ in sorted(
                actor_dexterity_pairs, key=lambda x: x[1], reverse=True
            )
        ]

    #######################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def plan_action(self, actors: List[str]) -> None:

        for actor_name in actors:

            actor_entity = self.get_actor_entity(actor_name)
            assert actor_entity is not None
            if actor_entity is None:
                logger.error(f"角色: {actor_name} 不存在！")
                continue

            if not actor_entity.has(HeroComponent):
                logger.error(f"角色: {actor_name} 不是英雄，不能有行动计划！")
                continue

            if actor_entity.has(PlayerComponent):
                logger.error(f"角色: {actor_name} 是玩家控制的，不能有行动计划！")
                continue

            logger.debug(f"为角色: {actor_name} 激活行动计划！")
            actor_entity.replace(PlanAction, actor_entity.name)

    #######################################################################################################################################
    # TODO, 临时添加行动, 逻辑。
    def trans_stage_action(self, stage_name: str) -> bool:
        target_stage_entity = self.get_stage_entity(stage_name)
        assert target_stage_entity is not None, f"目标场景: {stage_name} 不存在！"
        if target_stage_entity is None:
            logger.error(f"目标场景: {stage_name} 不存在！")
            return

        assert target_stage_entity.has(
            HomeComponent
        ), f"目标场景: {stage_name} 不是家园！"
        player_entity = self.get_player_entity()
        assert player_entity is not None, "玩家实体不存在！"
        player_entity.replace(TransStageAction, player_entity.name, stage_name)
        return True

    #######################################################################################################################################
    def find_recent_human_message_by_attribute(
        self,
        actor_entity: Entity,
        attribute_key: str,
        attribute_value: str,
    ) -> Optional[HumanMessage]:

        chat_history = self.get_agent_chat_history(actor_entity).chat_history

        # 注意，这里是倒序遍历！
        for chat_message in reversed(chat_history):

            if not isinstance(chat_message, HumanMessage):
                continue

            try:
                # 直接从 HumanMessage 对象获取属性，而不是从嵌套的 kwargs 中获取
                if hasattr(chat_message, attribute_key):
                    if getattr(chat_message, attribute_key) == attribute_value:
                        return chat_message

            except Exception as e:
                logger.error(f"find_recent_human_message_by_attribute error: {e}")
                continue

        return None

    #######################################################################################################################################
