"""
TCG 游戏核心实现

融合交易卡牌战斗机制的 RPG 游戏，包含地下城探险、战斗系统和流程管道管理。
"""

from typing import Final
from loguru import logger
from overrides import override
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from ..game.tcg_game_process_pipeline import (
    create_home_pipeline,
    create_combat_pipeline,
    create_dungeon_generate_pipeline,
)
from ..models import (
    Dungeon,
    World,
    ActorComponent,
    HandComponent,
    DrawDeckComponent,
    DiscardDeckComponent,
    BlockComponent,
    StageType,
    ActorType,
    StatusEffectsComponent,
    ArchetypeComponent,
    CharacterStats,
    CharacterStatsComponent,
    EquipmentComponent,
    InventoryComponent,
)
from ..models.utils import compute_stats_with_equipment
from .player_session import PlayerSession
from ..entitas import Matcher, Entity


#################################################################################################################################################


#################################################################################################################################################
class TCGGame(RPGGame):
    """
    交易卡牌游戏，融合卡牌战斗机制的RPG游戏实现

    Attributes:
        _home_pipeline: 家园场景流程管道（NPC 与玩家共用）
        _combat_execution_pipeline: 地下城战斗执行流程管道
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
        if player_entity is None:
            return False

        return self.is_actor_in_home_stage(player_entity)

    ###############################################################################################################################################
    @property
    def is_player_in_dungeon_stage(self) -> bool:
        """检查玩家是否在地下城场景中"""
        player_entity = self.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        if player_entity is None:
            return False

        return self.is_actor_in_dungeon_stage(player_entity)

    ###############################################################################################################################################
    @override
    def build_from_blueprint(self) -> "TCGGame":
        """创建并初始化新游戏世界

        Returns:
            返回自身实例，支持链式调用
        """
        super().build_from_blueprint()
        self._mount_actor_deck_components()
        self._mount_actor_archetype_components()
        return self

    #######################################################################################################################################
    def setup_dungeon_entities(self, dungeon_model: Dungeon) -> None:
        """根据地下城模型初始化并创建相关游戏实体（敌人和场景）

        Args:
            dungeon_model: 地下城数据模型
        """

        if dungeon_model.setup_entities:
            logger.warning(f"地下城实体已设置，跳过创建: {dungeon_model.name}")
            return

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for actor in dungeon_model.actors:
            actor_entity = self.get_actor_entity(actor.name)
            assert actor_entity is None, "actor_entity is not None"
            assert (
                actor.character_sheet.type == ActorType.ENEMY
            ), "actor_entity is not enemy type"

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for room in dungeon_model.rooms:
            stage_entity = self.get_stage_entity(room.stage.name)
            assert stage_entity is None, "stage_entity is not None"
            assert (
                room.stage.stage_profile.type == StageType.DUNGEON
            ), "stage_entity is not dungeon type"

        logger.debug(f"正在根据地下城模型创建实体: {dungeon_model.name}")

        # 创建地下城的怪物。
        self._create_actor_entities(dungeon_model.actors)

        # 为新创建的怪物实体补充 DrawDeckComponent / DiscardDeckComponent
        self._mount_actor_deck_components()
        self._mount_actor_archetype_components()

        # 创建地下城的场景
        self._create_stage_entities([room.stage for room in dungeon_model.rooms])

        # 设置标记，避免重复创建。
        dungeon_model.setup_entities = True

    #######################################################################################################################################
    def teardown_dungeon_entities(self, dungeon_model: Dungeon) -> None:
        """根据地下城模型清理并销毁相关游戏实体（敌人和场景）

        Args:
            dungeon_model: 地下城数据模型
        """
        # 清空地下城的怪物。
        for actor in dungeon_model.actors:
            destroy_actor_entity = self.get_actor_entity(actor.name)
            if destroy_actor_entity is not None:
                self.destroy_entity(destroy_actor_entity)

        # 清空地下城的场景
        for room in dungeon_model.rooms:
            destroy_stage_entity = self.get_stage_entity(room.stage.name)
            if destroy_stage_entity is not None:
                self.destroy_entity(destroy_stage_entity)

    ################################################################################################################
    def clear_round_state(self) -> None:
        """清除所有角色实体的每回合可变状态（手牌与格挡）"""

        # 清除所有角色实体的手牌组件，并将剩余手牌归还牌组
        for entity in self.get_group(Matcher(HandComponent)).entities.copy():
            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None
            # 将剩余手牌全部归还牌组，再移除手牌组件
            if hand_comp.cards:
                draw_deck_comp = entity.get(DrawDeckComponent)
                assert (
                    draw_deck_comp is not None
                ), f"{entity.name} 缺少 DrawDeckComponent"
                # 仅归还来源为本角色的卡牌；外来塞入牌（source != actor_name）直接丢弃
                own_cards = [c for c in hand_comp.cards if c.source == entity.name]
                foreign_cards = [c for c in hand_comp.cards if c.source != entity.name]
                draw_deck_comp.cards.extend(own_cards)
                logger.debug(
                    f"clear hands: {entity.name} 归还 {len(own_cards)} 张自有手牌到 DrawDeck，DrawDeck 累计 {len(draw_deck_comp.cards)} 张"
                )
                for fc in foreign_cards:
                    logger.debug(
                        f"clear hands: [{entity.name}] 外来牌 [{fc.name}](source={fc.source!r}) 回合结束，source 不匹配，丢弃不归还"
                    )
            else:
                logger.debug(f"clear hands: {entity.name}")

            # 移除 HandComponent
            entity.remove(HandComponent)

        # 清除所有角色实体的格挡组件
        for entity in self.get_group(Matcher(BlockComponent)).entities.copy():
            logger.debug(f"clear blocks: {entity.name}")
            entity.remove(BlockComponent)

    ################################################################################################################
    def clear_status_effects(self) -> None:
        """清除所有角色实体的状态效果组件"""

        actor_entities = self.get_group(Matcher(StatusEffectsComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear status effects: {entity.name}")
            entity.remove(StatusEffectsComponent)

    #######################################################################################################################################
    def _mount_actor_deck_components(self) -> None:
        """为所有缺少 DrawDeckComponent / DiscardDeckComponent 的 Actor 实体挂载空牌组"""

        for entity in self.get_group(Matcher(ActorComponent)).entities:
            if not entity.has(DrawDeckComponent):
                entity.replace(DrawDeckComponent, entity.name, [])
                logger.debug(f"为 Actor 实体 {entity.name} 添加空 DrawDeckComponent")
            if not entity.has(DiscardDeckComponent):
                entity.replace(DiscardDeckComponent, entity.name, [])
                logger.debug(f"为 Actor 实体 {entity.name} 添加空 DiscardDeckComponent")

    #######################################################################################################################################
    def _mount_actor_archetype_components(self) -> None:
        """为所有缺少 ArchetypeComponent 的 Actor 实体挂载原型约束"""

        all_actor_models = {
            a.name: a for a in self._world.blueprint.actors + self._world.dungeon.actors
        }

        # 为每个 Actor 实体挂载 ArchetypeComponent，内容来自 Actor 模型的 archetypes 字段
        for entity in self.get_group(Matcher(ActorComponent)).entities:
            if entity.has(ArchetypeComponent):
                continue

            # 从蓝图中找到对应的 Actor 模型，获取其 archetypes 数据
            actor_model = all_actor_models.get(entity.name)
            assert actor_model is not None, f"找不到 Actor model: {entity.name}"

            # 添加 ArchetypeComponent，内容来自 Actor 模型的 archetypes 字段
            entity.replace(ArchetypeComponent, entity.name, actor_model.archetypes)
            logger.debug(
                f"为 Actor 实体 {entity.name} 挂载 ArchetypeComponent ({len(actor_model.archetypes)} 条原型)"
            )

    ###############################################################################################################################################
    def compute_character_stats(self, entity: Entity) -> CharacterStats:
        """计算角色的最终有效属性，聚合基础属性与已装备物品的属性加成。

        Args:
            entity: 角色实体，必须拥有 CharacterStatsComponent

        Returns:
            包含基础属性与所有已装备物品加成之和的新 CharacterStats 实例
        """

        assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
        assert entity.has(
            CharacterStatsComponent
        ), f"{entity.name} 缺少 CharacterStatsComponent"

        stats_comp = entity.get(CharacterStatsComponent)
        return compute_stats_with_equipment(
            stats_comp,
            entity.get(EquipmentComponent) if entity.has(EquipmentComponent) else None,
            entity.get(InventoryComponent) if entity.has(InventoryComponent) else None,
        )

    ###############################################################################################################################################
    def set_character_hp(self, entity: Entity, hp: int) -> CharacterStats:
        """设置角色的当前 HP，自动 clamp 至 [0, max_hp]。

        Args:
            entity: 角色实体，必须拥有 CharacterStatsComponent
            hp: 目标 HP 值，将被 clamp 至 0 ~ compute_character_stats(entity).max_hp
        """

        assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
        assert entity.has(
            CharacterStatsComponent
        ), f"{entity.name} 缺少 CharacterStatsComponent"

        stats_comp = entity.get(CharacterStatsComponent)
        max_hp = self.compute_character_stats(entity).max_hp
        clamped = max(0, min(hp, max_hp))
        stats_comp.stats.hp = clamped

        return self.compute_character_stats(entity)

    ################################################################################################################
