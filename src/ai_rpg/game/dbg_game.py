"""
DBG 游戏核心实现
"""

import copy
import uuid
from typing import Final, List, Optional
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from .dbg_home_pipeline import create_home_pipeline
from .dbg_home_craft_pipeline import create_home_craft_pipeline
from .dbg_dungeon_opening_room_pipeline import create_dungeon_opening_room_pipeline
from .dbg_dungeon_combat_room_pipeline import create_dungeon_combat_room_pipeline
from .dbg_dungeon_generate_pipeline import create_dungeon_generate_pipeline
from ..models import (
    Actor,
    ActorComponent,
    ActorType,
    NPCComponent,
    AppearanceComponent,
    CharacterStatsComponent,
    COMPONENT_TYPES,
    Dungeon,
    DungeonComponent,
    MonsterComponent,
    HomeComponent,
    IdentityComponent,
    PlayerComponent,
    resolve_component_type,
    StorageComponent,
    Stage,
    StageComponent,
    StageType,
    WorldState,
    WorldComponent,
    World,
    SystemMessage,
    PlayerSession,
    CombatRoom,
    OpeningRoom,
)
from ..entitas import Matcher, Entity


#################################################################################################################################################
class DBGGame(RPGGame):
    """
    DBG，Deck Building Game
    """

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: WorldState,
    ) -> None:

        # 必须按着此顺序实现父类
        RPGGame.__init__(self, name, player_session, world)

        # 家园流程（NPC 与玩家共用）
        self._home_pipeline: Final[RPGGameProcessPipeline] = create_home_pipeline(self)

        # 家园制作流程（仅处理 craft 动作）
        self._home_craft_pipeline: Final[RPGGameProcessPipeline] = (
            create_home_craft_pipeline(self)
        )

        # 副本开场流程（叙事 + 牌库初始化，无战斗；卡池生成由外部显式触发）
        self._dungeon_opening_room_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_opening_room_pipeline(self)
        )

        # 副本战斗流程
        self._dungeon_combat_room_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_combat_room_pipeline(self)
        )

        # 副本生成流程（LLM 文本生成 + 图片生成）
        self._dungeon_generate_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_generate_pipeline(self)
        )

        # 注册所有管道到管道管理器
        self.register_pipeline(self._home_pipeline)
        self.register_pipeline(self._home_craft_pipeline)
        self.register_pipeline(self._dungeon_opening_room_pipeline)
        self.register_pipeline(self._dungeon_combat_room_pipeline)
        self.register_pipeline(self._dungeon_generate_pipeline)

    ###############################################################################################################################################
    @property
    def current_dungeon(self) -> Dungeon:
        return self._world.dungeon

    ###############################################################################################################################################
    @property
    def is_player_in_home_stage(self) -> bool:
        """检查玩家是否在家园场景中"""
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        return self.is_actor_in_home_stage(player_entity)

    ###############################################################################################################################################
    @property
    def is_player_in_dungeon_stage(self) -> bool:
        """检查玩家是否在副本场景中"""
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        return self.is_actor_in_dungeon_stage(player_entity)

    ###############################################################################################################################################
    @property
    def current_dungeon_combat_room(self) -> CombatRoom:
        """断言当前处于战斗房间中，返回战斗房间"""
        assert self._world.dungeon is not None, "当前副本不存在"
        assert self._world.dungeon.current_room is not None, "当前副本房间不存在"
        assert isinstance(
            self._world.dungeon.current_room, CombatRoom
        ), "当前副本房间不是战斗房间"
        return self._world.dungeon.current_room

    ###############################################################################################################################################
    @property
    def is_current_room_dungeon_combat(self) -> bool:
        """检查当前副本房间是否为战斗房间"""
        if self._world.dungeon is None:
            return False
        if self._world.dungeon.current_room is None:
            return False
        return isinstance(self._world.dungeon.current_room, CombatRoom)

    ###############################################################################################################################################
    @property
    def current_dungeon_opening_room(self) -> OpeningRoom:
        """断言当前处于开场房间中，返回开场房间"""
        assert self._world.dungeon is not None, "当前副本不存在"
        assert self._world.dungeon.current_room is not None, "当前副本房间不存在"
        assert isinstance(
            self._world.dungeon.current_room, OpeningRoom
        ), "当前副本房间不是开场房间"
        return self._world.dungeon.current_room

    ###############################################################################################################################################
    @property
    def is_current_room_dungeon_opening(self) -> bool:
        """检查当前副本房间是否为开场房间"""
        if self._world.dungeon is None:
            return False
        if self._world.dungeon.current_room is None:
            return False
        return isinstance(self._world.dungeon.current_room, OpeningRoom)

    ###############################################################################################################################################
    def get_storage_entity(self) -> Optional[Entity]:
        """获取全局储物箱实体。"""
        storage_entities = self.get_group(
            Matcher(
                all_of=[WorldComponent, StorageComponent],
            )
        ).entities

        assert len(storage_entities) == 1, "There should be exactly one storage entity."
        return next(iter(storage_entities), None)

    ###############################################################################################################################################
    def build_from_blueprint(self) -> "DBGGame":
        """创建并初始化新游戏世界，包括世界、角色和场景"""
        assert len(self._world.entities) == 0, "游戏中有实体，不能创建新的游戏"
        if len(self._world.entities) > 0:
            logger.warning(
                f"游戏中有实体，不能创建新的游戏，entities = {self._world.entities}"
            )
            return self

        ## 第1步，创建world（含全局储物箱世界实体，其 StorageComponent 由 world_entities 数据驱动挂载）
        self._create_world_entities(self._world.blueprint.world_entities)

        ## 第2步，创建actor（含牌组与关键词组件挂载）
        self.create_actor_entities(
            [actor for stage in self._world.blueprint.stages for actor in stage.actors]
        )

        ## 第3步，创建stage
        self.create_stage_entities(self._world.blueprint.stages)

        ## 第4步，分配玩家控制的actor
        assert self._player_session.name != "", "玩家名字不能为空"
        assert self._player_session.actor != "", "玩家角色不能为空"
        player_actor_entity = self.get_actor_entity(self._player_session.actor)
        assert (
            player_actor_entity is not None
        ), f"找不到玩家角色实体: {self._player_session.actor}"

        # 玩家角色实体必须没有 PlayerComponent，确保之前没有被分配过玩家控制
        assert not player_actor_entity.has(PlayerComponent)
        player_actor_entity.replace(PlayerComponent, self._player_session.name)
        logger.info(
            f"玩家: {self._player_session.name} 选择控制: {self._player_session.actor}"
        )

        return self

    ###############################################################################################################################################
    def _create_world_entities(
        self,
        world_models: List[World],
    ) -> List[Entity]:
        """创建世界实体（全局规则管理器、叙事者）"""
        world_entities: List[Entity] = []

        for world_model in world_models:

            # 创建实体
            world_entity = self._create_entity(world_model.name)
            assert world_entity is not None, f"创建world_entity失败: {world_model.name}"

            # 必要组件：identifier
            self._world.entity_counter += 1
            world_entity.add(
                IdentityComponent,
                world_model.name,
                self._world.entity_counter,
                str(uuid.uuid4()),
            )

            # 必要组件：身份类型标记-世界
            world_entity.add(WorldComponent, world_model.name)

            # 添加系统消息
            assert (
                world_model.name in world_model.system_message
            ), f"world_model.system_message 缺少 {world_model.name} 的系统消息"
            self.add_system_message(
                world_entity,
                SystemMessage(content=world_model.system_message),
            )

            # 特殊组件，根据 world_model.components 数据驱动动态添加
            for comp_serialization in world_model.components:
                comp_class = COMPONENT_TYPES.get(comp_serialization.name)
                assert (
                    comp_class is not None
                ), f"未知组件类型: {comp_serialization.name}"
                restore_comp = comp_class(**comp_serialization.data)
                logger.debug(
                    f"为 World 实体 {world_entity.name} 添加 {comp_serialization.name}"
                )
                world_entity.set(comp_class, restore_comp)

            # 添加到返回值
            world_entities.append(world_entity)

        return world_entities

    ###############################################################################################################################################
    def create_actor_entities(self, actor_models: List[Actor]) -> List[Entity]:
        """创建角色实体（玩家、NPC、敌人），初始化所有组件，并挂载 DBG 所需的牌组与关键词组件"""
        actor_entities: List[Entity] = []

        for actor_model in actor_models:

            # 创建实体
            actor_entity = self._create_entity(actor_model.name)
            assert actor_entity is not None, f"创建actor_entity失败: {actor_model.name}"

            # 必要组件：identifier
            self._world.entity_counter += 1
            actor_entity.add(
                IdentityComponent,
                actor_model.name,
                self._world.entity_counter,
                str(uuid.uuid4()),
            )

            # 必要组件：身份类型标记-角色Actor
            actor_entity.add(ActorComponent, actor_model.name, "")

            # 必要组件：系统消息
            assert (
                actor_model.name in actor_model.system_message
            ), f"actor_model.system_message 缺少 {actor_model.name} 的系统消息"
            self.add_system_message(
                actor_entity, SystemMessage(content=actor_model.system_message)
            )

            # 必要组件：外观
            assert (
                actor_model.base_body != ""
            ), f"actor_model.base_body 不能为空: {actor_model.name}"
            actor_entity.add(
                AppearanceComponent,
                actor_model.name,
                actor_model.base_body,
                actor_model.base_body,  # 初始外观与基础身体相同，后续可通过装备 CostumeItem 挂载 CostumeComponent 来改变外观，但不影响基础身体（base_body）
            )

            # 必要组件：基础属性，这里用浅拷贝，不能动原有的。
            actor_entity.add(
                CharacterStatsComponent,
                actor_model.name,
                copy.copy(actor_model.character_stats),
            )

            # 必要组件：类型标记
            match actor_model.type:
                case ActorType.NPC:
                    actor_entity.add(NPCComponent, actor_model.name)
                case ActorType.MONSTER:
                    actor_entity.add(MonsterComponent, actor_model.name)
                case _:
                    assert False, f"未知的 ActorType: {actor_model.type}"

            # 特殊组件，根据 actor_model.components 数据驱动动态添加
            for comp_serialization in actor_model.components:
                comp_class = COMPONENT_TYPES.get(comp_serialization.name)
                assert (
                    comp_class is not None
                ), f"未知组件类型: {comp_serialization.name}"
                restore_comp = comp_class(**comp_serialization.data)
                logger.debug(
                    f"为 Actor 实体 {actor_entity.name} 添加 {comp_serialization.name}"
                )
                actor_entity.set(comp_class, restore_comp)

            # 添加到返回值
            actor_entities.append(actor_entity)

        return actor_entities

    ###############################################################################################################################################
    def create_stage_entities(self, stage_models: List[Stage]) -> List[Entity]:
        """创建场景实体，并建立角色与场景的关联关系"""
        stage_entities: List[Entity] = []

        for stage_model in stage_models:

            # 创建实体
            stage_entity = self._create_entity(stage_model.name)
            assert stage_entity is not None, f"创建stage_entity失败: {stage_model.name}"

            # 必要组件: identifier
            self._world.entity_counter += 1
            stage_entity.add(
                IdentityComponent,
                stage_model.name,
                self._world.entity_counter,
                str(uuid.uuid4()),
            )

            # 必要组件: StageComponent，包含场景名称，方便后续访问和识别
            stage_entity.add(StageComponent, stage_model.name)

            # 必要组件：系统消息
            assert stage_model.name in stage_model.system_message
            self.add_system_message(
                stage_entity, SystemMessage(content=stage_model.system_message)
            )

            # 必要组件：类型
            match stage_model.type:
                case StageType.DUNGEON:
                    stage_entity.add(DungeonComponent, stage_model.name)
                case StageType.HOME:
                    stage_entity.add(HomeComponent, stage_model.name)
                case _:
                    assert False, f"未知的 StageType: {stage_model.type}"

            # 特殊组件，根据 stage_model.components 数据驱动动态添加
            # （含每个 Stage 的唯一标记组件，跨进程反序列化时惰性重建）
            for comp_serialization in stage_model.components:
                comp_class = resolve_component_type(
                    comp_serialization.name, comp_serialization.data
                )
                restore_comp = comp_class(**comp_serialization.data)
                logger.debug(
                    f"为 Stage 实体 {stage_entity.name} 添加 {comp_serialization.name}"
                )
                stage_entity.set(comp_class, restore_comp)

            ## 重新设置Actor和stage的关系
            for actor_model in stage_model.actors:
                actor_entity = self.get_actor_entity(actor_model.name)
                assert (
                    actor_entity is not None
                ), f"找不到actor_entity: {actor_model.name}"
                actor_entity.replace(
                    ActorComponent,
                    actor_model.name,
                    stage_model.name,
                )

            stage_entities.append(stage_entity)

        return stage_entities

    ################################################################################################################
