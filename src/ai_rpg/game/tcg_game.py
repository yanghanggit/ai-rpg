"""
TCG 游戏核心实现

融合交易卡牌战斗机制的 RPG 游戏，包含地下城探险、战斗系统和流程管道管理。
"""

from typing import Final, List
from loguru import logger
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
    HandComponent,
    BlockComponent,
    StageType,
    ActorType,
    ActorComponent,
    StatusEffect,
    StatusEffectsComponent,
)
from .player_session import PlayerSession
from ..entitas import Matcher


#################################################################################################################################################
def _make_status_effects_tick_message(
    ticked: List[StatusEffect],
    expired: List[StatusEffect],
) -> str:
    """生成回合结束时状态效果更新的 LLM 通知文本。

    Args:
        ticked: 持续时间已递减但尚未过期的效果列表
        expired: 本回合耗尽（已移除）的效果列表

    Returns:
        写入 agent 上下文的 human message 文本
    """
    lines = ["# 回合结束 — 状态效果更新"]
    for e in ticked:
        lines.append(f"- {e.name}（剩余{e.duration}回合）")
    for e in expired:
        lines.append(f"- {e.name} → 已过期，已从状态列表移除")
    return "\n".join(lines)


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
        for entity in self.get_group(Matcher(HandComponent)).entities.copy():
            logger.debug(f"clear hands: {entity.name}")
            entity.remove(HandComponent)
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

    ################################################################################################################
    def tick_status_effects_duration(self) -> None:
        """回合结束时递减所有角色的状态效果持续时间，移除已过期的效果。

        - duration == -1：永久效果，跳过递减
        - duration > 0：-=1；降至 0 时从列表中移除

        对每个有变化的 actor 实体写入 human message，保持 agent 对话上下文连续性。
        """
        for entity in self.get_group(Matcher(StatusEffectsComponent)).entities.copy():
            assert entity.has(
                ActorComponent
            ), f"Entity {entity.name} has StatusEffectsComponent but is not an Actor"
            comp = entity.get(StatusEffectsComponent)

            # 递减持续时间并移除过期效果
            updated = []
            ticked = []
            expired = []
            for effect in comp.status_effects:
                if effect.duration == -1:
                    updated.append(effect)
                    continue
                effect.duration -= 1
                if effect.duration > 0:
                    updated.append(effect)
                    ticked.append(effect)
                else:
                    expired.append(effect)
                    logger.debug(
                        f"[{entity.name}] 状态效果「{effect.name}」持续时间耗尽，已移除"
                    )

            # 更新组件状态效果列表
            comp.status_effects = updated

            # 没有任何变化则跳过写入上下文
            if not ticked and not expired:
                continue

            # 将更新结果写入角色上下文，保持对话连续性
            self.add_human_message(
                entity, _make_status_effects_tick_message(ticked, expired)
            )

    ################################################################################################################
