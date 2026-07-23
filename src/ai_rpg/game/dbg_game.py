"""
DBG 游戏核心实现
"""

import copy
import uuid
from typing import Final, List, Optional
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from .dbg_game_process_pipeline import (
    create_home_pipeline,
    create_combat_pipeline,
    create_dungeon_generate_pipeline,
)
from ..models import (
    Actor,
    ActorComponent,
    ActorType,
    NPCComponent,
    AppearanceComponent,
    CharacterStatsComponent,
    COMPONENT_TYPES,
    DeckComponent,
    Dungeon,
    DungeonComponent,
    MonsterComponent,
    HandComponent,
    HomeComponent,
    IdentityComponent,
    InventoryComponent,
    PlayerComponent,
    StorageComponent,
    DiscardPileComponent,
    RoundStatsComponent,
    Stage,
    StageComponent,
    StageType,
    World,
    WorldComponent,
    WorldSystem,
    WornCostumeComponent,
    SystemMessage,
    AnyItem,
    PlayerSession,
    CombatRoom,
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
        world: World,
    ) -> None:

        # 必须按着此顺序实现父类
        RPGGame.__init__(self, name, player_session, world)

        # 家园流程（NPC 与玩家共用）
        self._home_pipeline: Final[RPGGameProcessPipeline] = create_home_pipeline(self)

        # 地下城战斗流程
        self._combat_pipeline: Final[RPGGameProcessPipeline] = create_combat_pipeline(
            self
        )

        # 地下城生成流程（LLM 文本生成 + 图片生成）
        self._dungeon_generate_pipeline: Final[RPGGameProcessPipeline] = (
            create_dungeon_generate_pipeline(self)
        )

        # 注册所有管道到管道管理器
        self.register_pipeline(self._home_pipeline)
        self.register_pipeline(self._combat_pipeline)
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
        """检查玩家是否在地下城场景中"""
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        return self.is_actor_in_dungeon_stage(player_entity)

    ###############################################################################################################################################
    @property
    def current_combat_room(self) -> CombatRoom:
        """断言当前处于战斗房间中，返回战斗房间"""
        assert self._world.dungeon is not None, "当前地下城不存在"
        assert self._world.dungeon.current_room is not None, "当前地下城房间不存在"
        assert isinstance(
            self._world.dungeon.current_room, CombatRoom
        ), "当前地下城房间不是战斗房间"
        return self._world.dungeon.current_room

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
        """创建并初始化新游戏世界，包括世界系统、角色和场景"""
        assert (
            len(self._world.entities_serialization) == 0
        ), "游戏中有实体，不能创建新的游戏"
        if len(self._world.entities_serialization) > 0:
            logger.warning(
                f"游戏中有实体，不能创建新的游戏，entities_serialization = {self._world.entities_serialization}"
            )
            return self

        ## 第1步，创建world_system
        self._create_world_entities(self._world.blueprint.world_systems)

        ## 第1.5步，创建全局储物箱实体（挂载在 WorldComponent）
        initial_items = copy.deepcopy(self._world.blueprint.storage)
        self._create_storage_entity(initial_items)

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

        ## 第5步，添加 InventoryComponent 到玩家角色实体
        assert not player_actor_entity.has(
            InventoryComponent
        ), "玩家角色实体不应该已经有 InventoryComponent"
        initial_inventory = copy.deepcopy(self._world.blueprint.inventory)
        player_actor_entity.replace(
            InventoryComponent, player_actor_entity.name, initial_inventory
        )
        logger.debug(
            f"为玩家角色实体 {player_actor_entity.name} 添加 InventoryComponent，初始道具 {len(initial_inventory)} 件"
        )

        return self

    ###############################################################################################################################################
    def _create_storage_entity(self, items: List[AnyItem]) -> Entity:
        """创建全局唯一储物箱实体（WorldComponent + StorageComponent）。"""

        storage_entity = self._world.blueprint.storage_entity
        assert storage_entity != "", "storage_entity 不能为空"

        storage_entity_entity = self._create_entity(storage_entity)
        assert (
            storage_entity_entity is not None
        ), f"创建storage_entity失败: {storage_entity}"

        self._world.entity_counter += 1
        storage_entity_entity.add(
            IdentityComponent,
            storage_entity,
            self._world.entity_counter,
            str(uuid.uuid4()),
        )
        storage_entity_entity.add(WorldComponent, storage_entity)
        storage_entity_entity.add(StorageComponent, storage_entity, items)

        logger.debug(f"创建全局储物箱实体 {storage_entity}，初始道具 {len(items)} 件")
        return storage_entity_entity

    ###############################################################################################################################################
    def _create_world_entities(
        self,
        world_system_models: List[WorldSystem],
    ) -> List[Entity]:
        """创建世界系统实体（全局规则管理器、叙事者）"""
        world_entities: List[Entity] = []

        for world_system_model in world_system_models:

            # 创建实体
            world_system_entity = self._create_entity(world_system_model.name)
            assert (
                world_system_entity is not None
            ), f"创建world_system_entity失败: {world_system_model.name}"

            # 必要组件：identifier
            self._world.entity_counter += 1
            world_system_entity.add(
                IdentityComponent,
                world_system_model.name,
                self._world.entity_counter,
                str(uuid.uuid4()),
            )

            # 必要组件：身份类型标记-世界系统
            world_system_entity.add(WorldComponent, world_system_model.name)

            # 添加系统消息
            assert (
                world_system_model.name in world_system_model.system_message
            ), f"world_system_model.system_message 缺少 {world_system_model.name} 的系统消息"
            self.add_system_message(
                world_system_entity,
                SystemMessage(content=world_system_model.system_message),
            )

            # 特殊组件，根据 world_system_model.components 数据驱动动态添加
            for comp_serialization in world_system_model.components:
                comp_class = COMPONENT_TYPES.get(comp_serialization.name)
                assert (
                    comp_class is not None
                ), f"未知组件类型: {comp_serialization.name}"
                restore_comp = comp_class(**comp_serialization.data)
                logger.debug(
                    f"为 WorldSystem 实体 {world_system_entity.name} 添加 {comp_serialization.name}"
                )
                world_system_entity.set(comp_class, restore_comp)

            # 添加到返回值
            world_entities.append(world_system_entity)

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
            actor_entity.add(
                ActorComponent, actor_model.name, actor_model.character_sheet.name, ""
            )

            # 必要组件：系统消息
            assert (
                actor_model.name in actor_model.system_message
            ), f"actor_model.system_message 缺少 {actor_model.name} 的系统消息"
            self.add_system_message(
                actor_entity, SystemMessage(content=actor_model.system_message)
            )

            # 必要组件：外观
            assert (
                actor_model.character_sheet.base_body != ""
            ), f"actor_model.character_sheet.base_body 不能为空: {actor_model.name}"
            actor_entity.add(
                AppearanceComponent,
                actor_model.name,
                actor_model.character_sheet.base_body,
                actor_model.character_sheet.base_body,  # 初始外观与基础身体相同，后续可通过装备 CostumeItem 挂载 CostumeComponent 来改变外观，但不影响基础身体（base_body）
            )

            # 必要组件：基础属性，这里用浅拷贝，不能动原有的。
            actor_entity.add(
                CharacterStatsComponent,
                actor_model.name,
                copy.copy(actor_model.character_stats),
            )

            # 必要组件：类型标记
            match actor_model.character_sheet.type:
                case ActorType.NPC:
                    actor_entity.add(NPCComponent, actor_model.name)
                case ActorType.MONSTER:
                    actor_entity.add(MonsterComponent, actor_model.name)
                case _:
                    assert (
                        False
                    ), f"未知的 ActorType: {actor_model.character_sheet.type}"

            # DBG 组件：牌组 + 关键词约束
            assert (
                len(actor_model.keywords) > 0
            ), f"DBG 游戏要求每个角色至少有一个关键词约束: {actor_model.name}"
            actor_entity.replace(
                DeckComponent, actor_entity.name, [], actor_model.keywords.copy()
            )
            logger.debug(
                f"为 Actor 实体 {actor_entity.name} 挂载空牌组（DeckComponent，{len(actor_model.keywords)} 条关键词）"
            )

            # DBG 组件：初始时装（CostumeComponent），如果 actor_model.custom_item 不为 None，则挂载 CostumeComponent，初始时装来源于 actor_model.custom_item
            if actor_model.custom_item is not None:
                actor_entity.replace(
                    WornCostumeComponent,
                    actor_entity.name,
                    copy.deepcopy(actor_model.custom_item),
                )
                logger.debug(
                    f"为 Actor 实体 {actor_entity.name} 添加初始时装 {actor_model.custom_item.name}"
                )

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

            # 必要组件: StageComponent，包含场景名称和场景配置文件名称（stage_profile.name），方便后续访问和识别
            stage_entity.add(
                StageComponent, stage_model.name, stage_model.stage_profile.name
            )

            # 必要组件：系统消息
            assert stage_model.name in stage_model.system_message
            self.add_system_message(
                stage_entity, SystemMessage(content=stage_model.system_message)
            )

            # 必要组件：类型
            match stage_model.stage_profile.type:
                case StageType.DUNGEON:
                    stage_entity.add(DungeonComponent, stage_model.name)
                case StageType.HOME:
                    stage_entity.add(HomeComponent, stage_model.name)
                case _:
                    assert False, f"未知的 StageType: {stage_model.stage_profile.type}"

            ## 重新设置Actor和stage的关系
            for actor_model in stage_model.actors:
                actor_entity = self.get_actor_entity(actor_model.name)
                assert (
                    actor_entity is not None
                ), f"找不到actor_entity: {actor_model.name}"
                actor_entity.replace(
                    ActorComponent,
                    actor_model.name,
                    actor_model.character_sheet.name,
                    stage_model.name,
                )

            stage_entities.append(stage_entity)

        return stage_entities

    ################################################################################################################
    def clear_round_state(self) -> None:
        """清除所有角色实体的每回合可变状态（手牌归入弃牌堆 + 回合动态属性）"""

        # 清除所有角色实体的手牌组件，将剩余手牌归入 DiscardPile（STS 标准：回合末未出牌进弃牌堆）
        for entity in self.get_group(
            Matcher(all_of=[HandComponent, DiscardPileComponent])
        ).entities.copy():
            hand_comp = entity.get(HandComponent)
            discard_pile_comp = entity.get(DiscardPileComponent)

            if hand_comp.cards:
                # 仅归入来源为本角色的卡牌；外来塞入牌（source != actor_name）直接丢弃
                own_cards = [c for c in hand_comp.cards if c.source == entity.name]
                foreign_cards = [c for c in hand_comp.cards if c.source != entity.name]
                discard_pile_comp.cards.extend(own_cards)
                logger.debug(
                    f"clear hands: {entity.name} 将 {len(own_cards)} 张剩余手牌归入 DiscardPile，DiscardPile 累计 {len(discard_pile_comp.cards)} 张"
                )
                for fc in foreign_cards:
                    logger.debug(
                        f"clear hands: [{entity.name}] 外来牌 [{fc.name}](source={fc.source!r}) 回合结束，source 不匹配，丢弃"
                    )
            else:
                logger.debug(f"clear hands: {entity.name}")

            # 移除 HandComponent
            entity.remove(HandComponent)

        # 清除所有角色实体的回合动态属性组件
        for entity in self.get_group(Matcher(RoundStatsComponent)).entities.copy():
            logger.debug(f"clear round stats: {entity.name}")
            entity.remove(RoundStatsComponent)

    ################################################################################################################
