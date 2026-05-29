"""
TCG 游戏核心实现

融合交易卡牌战斗机制的 RPG 游戏，包含地下城探险、战斗系统和流程管道管理。
"""

import copy
import uuid
from typing import Final, List, Optional
from loguru import logger
from .rpg_game_pipeline_manager import RPGGameProcessPipeline
from .rpg_game import RPGGame
from ..game.tcg_game_process_pipeline import (
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
    CharacterStats,
    CharacterStatsComponent,
    COMPONENT_TYPES,
    DeckComponent,
    Dungeon,
    DungeonComponent,
    MonsterComponent,
    PartyRosterComponent,
    HandComponent,
    HomeComponent,
    IdentityComponent,
    InventoryComponent,
    KeywordComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
    StorageComponent,
    DiscardPileComponent,
    Round,
    RoundStatsComponent,
    Stage,
    StageComponent,
    StageType,
    DeathComponent,
    StatusEffect,
    EffectPhase,
    StatusEffectsComponent,
    World,
    WorldComponent,
    WorldSystem,
)
from ..models.utils import compute_effective_stats
from .player_session import PlayerSession
from ..entitas import Matcher, Entity


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
    def build_from_blueprint(self) -> "TCGGame":
        """创建并初始化新游戏世界，包括世界系统、角色和场景

        Returns:
            返回自身实例，支持链式调用
        """
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

        ## 第2步，创建actor（含牌组与关键词组件挂载）
        self._create_actor_entities(self._world.blueprint.actors)

        ## 第3步，创建stage
        self._create_stage_entities(self._world.blueprint.stages)

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

        ## 第5步，标记仅玩家可见的场景
        assert (
            self._world.blueprint.player_only_stage != ""
        ), "player_only_stage 不能为空"
        player_only_stage_entity = self.get_stage_entity(
            self._world.blueprint.player_only_stage
        )
        assert player_only_stage_entity is not None, "player_only_stage_entity is None"
        assert not player_only_stage_entity.has(PlayerOnlyStageComponent)

        # 添加 PlayerOnlyStageComponent 组件，并设置 name 属性为场景实体的名字，方便后续识别和访问控制
        player_only_stage_entity.replace(
            PlayerOnlyStageComponent, player_only_stage_entity.name
        )
        logger.debug(f"场景: {player_only_stage_entity.name} 已标记为仅玩家可见")

        ## 第6步，添加 PartyRosterComponent 到玩家角色实体
        assert not player_actor_entity.has(
            PartyRosterComponent
        ), "玩家角色实体不应该已经有 PartyRosterComponent"

        # 添加 PartyRosterComponent 组件，并设置 name 属性为角色实体的名字，方便后续识别和管理玩家的远征队伍
        player_actor_entity.replace(PartyRosterComponent, player_actor_entity.name, [])
        logger.debug(
            f"为玩家角色实体 {player_actor_entity.name} 添加 PartyRosterComponent"
        )

        ## 第7步，添加 InventoryComponent 与 StorageComponent 到玩家角色实体
        assert not player_actor_entity.has(
            InventoryComponent
        ), "玩家角色实体不应该已经有 InventoryComponent"
        player_actor_entity.replace(InventoryComponent, player_actor_entity.name, [])
        logger.debug(
            f"为玩家角色实体 {player_actor_entity.name} 添加 InventoryComponent"
        )

        assert not player_actor_entity.has(
            StorageComponent
        ), "玩家角色实体不应该已经有 StorageComponent"
        initial_items = copy.deepcopy(self._world.blueprint.items)
        player_actor_entity.replace(
            StorageComponent, player_actor_entity.name, initial_items
        )
        logger.debug(
            f"为玩家角色实体 {player_actor_entity.name} 添加 StorageComponent（{len(initial_items)} 件初始道具）"
        )

        return self

    ###############################################################################################################################################
    def _create_world_entities(
        self,
        world_system_models: List[WorldSystem],
    ) -> List[Entity]:
        """创建世界系统实体（全局规则管理器、叙事者）

        Args:
            world_system_models: 世界系统模型列表

        Returns:
            创建完成的世界系统实体列表
        """
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
                world_system_entity, world_system_model.system_message
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
    def _create_actor_entities(self, actor_models: List[Actor]) -> List[Entity]:
        """创建角色实体（玩家、NPC、敌人），初始化所有组件，并挂载 TCG 所需的牌组与关键词组件

        Args:
            actor_models: 角色模型列表

        Returns:
            创建完成的角色实体列表
        """
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
            self.add_system_message(actor_entity, actor_model.system_message)

            # 必要组件：外观
            assert (
                actor_model.character_sheet.base_body != ""
            ), f"actor_model.character_sheet.base_body 不能为空: {actor_model.name}"
            actor_entity.add(
                AppearanceComponent,
                actor_model.name,
                actor_model.character_sheet.base_body,
                "",  # appearance 初始为空，由 ActorAppearanceUpdateSystem 填充
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

            # TCG 组件：牌组
            actor_entity.replace(DeckComponent, actor_entity.name, [])
            logger.debug(
                f"为 Actor 实体 {actor_entity.name} 挂载空牌组（DeckComponent）"
            )

            # TCG 组件：关键词
            actor_entity.replace(
                KeywordComponent, actor_entity.name, actor_model.keywords.copy()
            )
            logger.debug(
                f"为 Actor 实体 {actor_entity.name} 挂载 KeywordComponent ({len(actor_model.keywords)} 条关键词)"
            )

            # 添加到返回值
            actor_entities.append(actor_entity)

        return actor_entities

    ###############################################################################################################################################
    def _create_stage_entities(self, stage_models: List[Stage]) -> List[Entity]:
        """创建场景实体，并建立角色与场景的关联关系

        Args:
            stage_models: 场景模型列表

        Returns:
            创建完成的场景实体列表
        """
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
            self.add_system_message(stage_entity, stage_model.system_message)

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
                actor.character_sheet.type == ActorType.MONSTER
            ), "actor_entity is not enemy type"

        # 加一步测试: 不可以存在！如果存在说明没有清空。
        for room in dungeon_model.rooms:
            stage_entity = self.get_stage_entity(room.stage.name)
            assert stage_entity is None, "stage_entity is not None"
            assert (
                room.stage.stage_profile.type == StageType.DUNGEON
            ), "stage_entity is not dungeon type"

        logger.debug(f"正在根据地下城模型创建实体: {dungeon_model.name}")

        # 创建地下城的怪物（含牌组与关键词组件挂载）
        self._create_actor_entities(dungeon_model.actors)

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
        """清除所有角色实体的每回合可变状态（手牌）"""

        # 清除所有角色实体的手牌组件，将剩余手牌归入 DiscardPile（STS 标准：回合末未出牌进弃牌堆）
        for entity in self.get_group(Matcher(HandComponent)).entities.copy():
            hand_comp = entity.get(HandComponent)

            if hand_comp.cards:
                discard_pile_comp = entity.get(DiscardPileComponent)
                assert (
                    discard_pile_comp is not None
                ), f"{entity.name} 缺少 DiscardPileComponent"
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
    def clear_status_effects(self) -> None:
        """清除所有角色实体的状态效果组件"""

        actor_entities = self.get_group(Matcher(StatusEffectsComponent)).entities.copy()
        for entity in actor_entities:
            logger.debug(f"clear status effects: {entity.name}")
            entity.remove(StatusEffectsComponent)

    ###############################################################################################################################################
    def get_status_effects_by_phase(
        self, entity: Entity, phase: EffectPhase
    ) -> List[StatusEffect]:
        """返回实体在指定战斗阶段生效的状态效果列表。

        Args:
            entity: 目标实体
            phase: 要筛选的生效阶段（EffectPhase）

        Returns:
            匹配阶段的 StatusEffect 列表；实体无 StatusEffectsComponent 时返回空列表
        """
        status_comp = entity.get(StatusEffectsComponent)
        if status_comp is None:
            return []
        return [e for e in status_comp.status_effects if e.phase == phase]

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
        return compute_effective_stats(
            stats_comp,
            (
                entity.get(StatusEffectsComponent).status_effects
                if entity.has(StatusEffectsComponent)
                else None
            ),
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

    ###############################################################################################################################################
    def apply_status_effect_patch(
        self, entity: Entity, status_effect_name: str, counter: int
    ) -> None:
        """更新实体上指定状态效果的 counter，并记录更新日志。

        匹配方式为按名称精确匹配。名称不存在时记录 warning 并跳过，不抛异常。

        Args:
            entity: 目标实体，必须拥有 StatusEffectsComponent
            status_effect_name: 要更新的状态效果名称
            counter: 更新后的特殊计数器值
        """
        assert entity.has(
            StatusEffectsComponent
        ), f"{entity.name} 缺少 StatusEffectsComponent，无法回写状态效果计数器"
        status_comp = entity.get(StatusEffectsComponent)
        effect_map = {e.name: e for e in status_comp.status_effects}
        if status_effect_name in effect_map:
            old_counter = effect_map[status_effect_name].counter
            effect_map[status_effect_name].counter = counter
            logger.info(
                f"更新 {entity.name} 状态效果「{status_effect_name}」 counter: "
                f"{old_counter} → {counter}"
            )
        else:
            logger.warning(
                f"status_effect_patches 中的效果「{status_effect_name}」"
                f"在 {entity.name} 的 StatusEffectsComponent 中不存在，跳过"
            )

    ###############################################################################################################################################
    def get_current_turn_actor(self, round: Round) -> Optional[str]:
        """从最新回合快照中找出第一个仍有行动力（energy > 0）的角色名。

        Args:
            round: 当前战斗回合

        Returns:
            当前应行动的角色名；若所有角色能量耗尽则返回 None
        """
        if not round.actor_order_snapshots:
            return None

        snapshot = round.actor_order_snapshots[-1]
        for actor_name in snapshot:
            actor_entity = self.get_actor_entity(actor_name)
            assert actor_entity is not None, f"无法找到角色实体: {actor_name}"
            if actor_entity is None:
                continue
            assert actor_entity.has(
                RoundStatsComponent
            ), f"{actor_name} 缺少 RoundStatsComponent"
            if not actor_entity.has(RoundStatsComponent):
                continue
            if actor_entity.get(RoundStatsComponent).energy > 0:
                return actor_name
        return None

    ###############################################################################################################################################
    def advance_turn(self, round: Round) -> None:
        """消耗 energy 后重新计算当前 turn 行动者，并写回 round.current_turn_actor_name。

        在每次出牌或过牌消耗 energy 之后调用，保持 Round 模型中 current_turn_actor_name 的最新状态。

        Args:
            round: 当前战斗回合
        """
        round.current_turn_actor_name = self.get_current_turn_actor(round)
        logger.debug(
            f"advance_turn: current_turn_actor_name updated to {round.current_turn_actor_name}"
        )

    ###############################################################################################################################################
    def consume_energy(self, entity: Entity, amount: int = 1) -> None:
        """消耗角色实体指定点数的 energy。

        Args:
            entity: 角色实体，必须拥有 RoundStatsComponent 且 energy > 0
            amount: 消耗的 energy 数量，默认为 1
        """
        assert entity.has(
            RoundStatsComponent
        ), f"{entity.name} 缺少 RoundStatsComponent"
        round_stats = entity.get(RoundStatsComponent)
        assert (
            round_stats.energy > 0
        ), f"{entity.name} 能量不足！当前 energy={round_stats.energy}"
        entity.replace(
            RoundStatsComponent,
            entity.name,
            max(0, round_stats.energy - amount),
        )

    ###############################################################################################################################################
    def process_zero_health_entities(self) -> None:
        """为 HP 归零且尚未标记死亡的实体添加 DeathComponent。"""
        defeated_entities = self.get_group(
            Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            entity_hp = self.compute_character_stats(entity).hp
            if entity_hp <= 0:
                logger.info(f"{entity.name} 已被击败，HP={entity_hp}")
                self.add_human_message(entity, "# 你的HP已归零，失去战斗能力！")
                entity.replace(DeathComponent, entity.name)

    ################################################################################################################
