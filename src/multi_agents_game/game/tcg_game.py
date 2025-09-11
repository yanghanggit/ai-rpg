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
from ..chat_services.manager import ChatClientManager
from ..game.game_config import LOGS_DIR
from ..mongodb import (
    DEFAULT_MONGODB_CONFIG,
    WorldDocument,
    mongodb_find_one,
    mongodb_upsert_one,
)
from ..entitas import Entity, Matcher
from ..game.base_game import BaseGame
from ..game.tcg_game_context import RetrieveMappingOptions, TCGGameContext
from ..game.tcg_game_process_pipeline import TCGGameProcessPipeline
from ..models import (
    Actor,
    ActorComponent,
    ActorType,
    AgentEvent,
    AgentShortTermMemory,
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
    PlayerActiveComponent,
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
        player: PlayerClient,
        world: World,
        chat_system: ChatClientManager,
    ) -> None:

        # 必须按着此顺序实现父
        BaseGame.__init__(self, name)  # 需要传递 name
        TCGGameContext.__init__(self)  # 继承 Context, 需要调用其 __init__

        # 世界运行时
        self._world: Final[World] = world

        # 处理器 与 对其控制的 状态。
        self._home_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_home_state_pipline(self)
        )
        self._dungeon_combat_pipeline: Final[TCGGameProcessPipeline] = (
            TCGGameProcessPipeline.create_dungeon_combat_state_pipeline(self)
        )

        self._all_pipelines: List[TCGGameProcessPipeline] = [
            self._home_pipeline,
            self._dungeon_combat_pipeline,
        ]

        # 玩家
        self._player: PlayerClient = player
        assert self._player.name != ""
        assert self._player.actor != ""

        # agent 系统
        self._chat_system: Final[ChatClientManager] = chat_system

    ###############################################################################################################################################
    @property
    def player(self) -> PlayerClient:
        return self._player

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
    def chat_system(self) -> ChatClientManager:
        return self._chat_system

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
    def home_state_pipeline(self) -> TCGGameProcessPipeline:
        return self._home_pipeline

    ###############################################################################################################################################
    @property
    def dungeon_combat_pipeline(self) -> TCGGameProcessPipeline:
        return self._dungeon_combat_pipeline

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        self._shutsdown_all_pipelines()
        logger.warning(f"{self.name}, game over!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    def _shutsdown_all_pipelines(self) -> None:
        for processor in self._all_pipelines:
            processor.shutdown()
        self._all_pipelines.clear()
        # logger.warning(f"{self.name}, game over!!!!!!!!!!!!!!!!!!!!")

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
        self._verbose_world_data()
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
    def append_ai_message(self, entity: Entity, ai_messages: List[AIMessage]) -> None:

        assert len(ai_messages) > 0, "ai_messages should not be empty"
        for ai_message in ai_messages:
            assert isinstance(ai_message, AIMessage)
            assert ai_message.content != "", "ai_message content should not be empty"
            logger.debug(f"append_ai_message: {entity._name} => \n{ai_message.content}")

        # 添加多条 AIMessage
        agent_short_term_memory = self.get_agent_short_term_memory(entity)
        agent_short_term_memory.chat_history.extend(ai_messages)

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

        # assert self._debug_flag_pipeline is False, "传送前，不允许在pipeline中"

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
    # TODO, 进入地下城！
    def _dungeon_advance(self, dungeon: Dungeon, heros_entities: Set[Entity]) -> bool:

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

        # 需要在这里补充设置地下城与怪物的kickoff信息。
        stage_kick_off_comp = stage_entity.get(KickOffMessageComponent)
        assert stage_kick_off_comp is not None
        logger.debug(
            f"当前 {stage_entity._name} 的kickoff信息: {stage_kick_off_comp.content}"
        )

        # 获取场景内角色的外貌信息
        actors_appearances_mapping: Dict[str, str] = (
            self.retrieve_actor_appearance_on_stage_mapping(stage_entity)
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
            f"更新设置{stage_entity._name} 的kickoff信息: {stage_entity.get(KickOffMessageComponent).content}"
        )

        actors = self.retrieve_actors_on_stage(stage_entity)
        for actor in actors:
            if actor.has(MonsterComponent):
                monster_kick_off_comp = actor.get(KickOffMessageComponent)
                assert monster_kick_off_comp is not None
                logger.debug(
                    f"需要设置{actor._name} 的kickoff信息: {monster_kick_off_comp.content}"
                )

        # 设置一个战斗为kickoff状态。
        dungeon.engagement.combat_kickoff(Combat(name=stage_entity._name))

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
    # TODO, 临时添加行动, 逻辑。 activate_play_cards_action
    def activate_play_cards_action(
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

        # 2. 验证所有角色的手牌状态
        if not self._validate_actors_hand_cards():
            return False

        # 3. 记录传入的技能选项
        if skill_execution_plan_options is not None:
            logger.debug(f"收到技能执行计划选项: {skill_execution_plan_options}")

        # 4. 为每个角色设置打牌行动
        last_round = self.current_engagement.last_round
        for turn_actor_name in last_round.round_turns:
            if not self._setup_actor_play_cards_action(
                turn_actor_name, skill_execution_plan_options
            ):
                return False

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

        last_round = self.current_engagement.last_round
        if last_round.has_ended:
            logger.error("回合已经完成，不能添加行动！")
            return False

        return True

    ###############################################################################################################################################
    def _validate_actors_hand_cards(self) -> bool:
        """验证所有角色的手牌状态"""
        last_round = self.current_engagement.last_round

        for turn_actor_name in last_round.round_turns:
            actor_entity = self.get_actor_entity(turn_actor_name)
            if actor_entity is None:
                logger.error(f"没有找到角色: {turn_actor_name}，不能添加行动！")
                return False

            if not actor_entity.has(HandComponent):
                logger.error(f"角色: {actor_entity._name} 没有手牌，不能添加行动！")
                return False

            hand_comp = actor_entity.get(HandComponent)
            if len(hand_comp.skills) == 0:
                logger.error(f"角色: {actor_entity._name} 没有技能可用，不能添加行动！")
                return False

        return True

    ###############################################################################################################################################
    def _setup_actor_play_cards_action(
        self,
        turn_actor_name: str,
        skill_execution_plan_options: Optional[Dict[str, str]],
    ) -> bool:
        """为单个角色设置打牌行动"""

        actor_entity = self.get_actor_entity(turn_actor_name)
        assert actor_entity is not None
        assert not actor_entity.has(PlayCardsAction)

        hand_comp = actor_entity.get(HandComponent)

        # 选择技能和目标
        selected_skill, final_target = self._select_skill_and_target(
            actor_entity, hand_comp, skill_execution_plan_options
        )

        if selected_skill is None:
            logger.error(f"无法为角色 {actor_entity._name} 选择技能")
            return False

        # 获取技能执行计划
        skill_execution_plan = hand_comp.get_execution_plan(selected_skill.name)
        assert skill_execution_plan is not None
        assert skill_execution_plan.skill == selected_skill.name

        # 创建打牌行动
        actor_entity.replace(
            PlayCardsAction,
            actor_entity._name,
            selected_skill,
            final_target,
            # skill_execution_plan.dialogue,
            # skill_execution_plan.reason,
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
                        f"为角色 {actor_entity._name} 选择指定技能: {skill.name}, 目标: {target_override}"
                    )
                    break

        # 如果没有找到指定技能，随机选择
        if selected_skill is None:
            selected_skill = random.choice(hand_comp.skills)
            logger.debug(
                f"为角色 {actor_entity._name} 随机选择技能: {selected_skill.name}"
            )

        # 确定最终目标
        if target_override is not None:
            final_target = target_override
        else:
            skill_execution_plan = hand_comp.get_execution_plan(selected_skill.name)
            final_target = skill_execution_plan.target if skill_execution_plan else ""

        return selected_skill, final_target

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
        actors_on_stage = self.retrieve_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0
        shuffled_reactive_entities = self._shuffle_action_order(list(actors_on_stage))

        # 场景描写加上。
        first_entity = next(iter(shuffled_reactive_entities))
        stage_entity = self.safe_get_stage_entity(first_entity)
        assert stage_entity is not None
        stage_environment_comp = stage_entity.get(EnvironmentComponent)

        round = self.current_engagement.new_round(
            round_turns=[entity._name for entity in shuffled_reactive_entities]
        )

        round.environment = stage_environment_comp.narrate
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
