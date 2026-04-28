"""
战斗回合过渡系统

职责：创建新回合、重置参战角色的回合属性，并生成本回合的行动顺序快照。
第一回合由 CombatInitializationSystem 创建；本系统负责后续每一回合的衔接。
旧回合清理由 CombatRoundCleanupSystem 负责（位于本系统之前）。
"""

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final, override
from loguru import logger
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    DungeonComponent,
    IdentityComponent,
    Round,
    RoundStatsComponent,
)


###############################################################################################################################################
# 行动顺序策略枚举
@final
@unique
class ActionOrderStrategy(StrEnum):
    """战斗回合中角色行动顺序的排序策略"""

    RANDOM = "random"  # 随机打乱（默认）
    CREATION_ORDER = "creation_order"  # 按实体创建顺序（creation_order 小的靠前）
    SPEED_ORDER = "speed_order"  # 按速度降序（speed 大的靠前），体现角色敏捷/迟缓个性


@final
class CombatRoundTransitionSystem(ExecuteProcessor):
    """
    战斗回合过渡系统。

    每次 pipeline 执行时，若上一回合已完成（is_completed）则自动创建下一回合：
    调用 start_new_round 重置所有参战角色的 RoundStatsComponent，
    再按指定策略（RANDOM / SPEED_ORDER / CREATION_ORDER）生成行动顺序快照，
    写入 Round.actor_order_snapshots 供 EnemyPlayDecisionSystem 等后续系统使用。
    """

    ############################################################################################################
    def __init__(
        self,
        game: TCGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.RANDOM,
    ) -> None:
        self._game: Final[TCGGame] = game
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
    def start_new_round(self, actors: set[Entity]) -> Round:
        """创建并追加新回合，同时重置所有参战角色的 RoundStatsComponent。"""
        assert (
            self._game.current_dungeon.current_combat is not None
        ), "current_combat is None"
        assert self._game.current_dungeon.is_ongoing, "当前战斗未进行中，无法开始新回合"
        current_rounds = self._game.current_dungeon.current_rounds or []
        if len(current_rounds) > 0:
            last_round = self._game.current_dungeon.latest_round
            assert last_round is not None, "latest_round is None"
            assert last_round.is_completed, "上一回合尚未完成，无法创建新回合"
        new_round = Round()
        self._game.current_dungeon.current_combat.rounds.append(new_round)
        for actor in actors:
            assert not actor.has(
                RoundStatsComponent
            ), f"{actor.name} 已存在 RoundStatsComponent"
            assert not actor.has(DeathComponent), f"{actor.name} 已死亡，不应参与新回合"
            computed = self._game.compute_character_stats(actor)
            actor.replace(RoundStatsComponent, actor.name, computed.energy, 0)
        return new_round

    ############################################################################################################
    def sorted_actors_by_round_speed(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并按速度降序排列。"""
        eligible: List[Entity] = [
            entity
            for entity in actors
            if entity.has(RoundStatsComponent)
            and entity.get(RoundStatsComponent).energy > 0
        ]
        eligible.sort(
            key=lambda entity: (
                -entity.get(CharacterStatsComponent).stats.speed,  # 速度降序
                entity.get(IdentityComponent).creation_order,
            )
        )
        return eligible

    ############################################################################################################
    def shuffled_actors_by_round(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并随机打乱顺序。"""
        eligible: List[Entity] = [
            entity
            for entity in actors
            if entity.has(RoundStatsComponent)
            and entity.get(RoundStatsComponent).energy > 0
        ]
        random.shuffle(eligible)
        return eligible

    ############################################################################################################
    def sorted_actors_by_creation_order(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并按创建顺序升序排列。"""
        eligible: List[Entity] = [
            entity
            for entity in actors
            if entity.has(RoundStatsComponent)
            and entity.get(RoundStatsComponent).energy > 0
        ]
        eligible.sort(key=lambda entity: entity.get(IdentityComponent).creation_order)
        return eligible

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 状态守护：战斗未进行中 / 最新回合未完成 → 静默跳过
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过回合创建")
            return

        logger.debug("检查战斗回合状态，判断是否需要创建新回合...")

        current_rounds = self._game.current_dungeon.current_rounds or []

        if len(current_rounds) > 0:
            last_round = self._game.current_dungeon.latest_round
            assert last_round is not None, "latest_round is None"
            if not last_round.is_completed:
                return

        # 玩家角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 所有存活角色
        actors_in_stage = self._game.get_alive_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, "actors_in_stage is empty"
        for actor in actors_in_stage:
            assert actor.has(
                CharacterStatsComponent
            ), f"actor {actor.name} 缺少 CharacterStatsComponent"
            assert actor.has(
                IdentityComponent
            ), f"actor {actor.name} 缺少 IdentityComponent"

        # 当前舞台（必须是地下城）
        stage_entity = self._game.resolve_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        round_number = len(current_rounds) + 1
        new_round = self.start_new_round(actors_in_stage)

        # 快照必须在 start_new_round 之后构建，此时 RoundStatsComponent 已按新回合重置
        if self._strategy == ActionOrderStrategy.RANDOM:
            snapshot_entities = self.shuffled_actors_by_round(actors_in_stage)
        elif self._strategy == ActionOrderStrategy.SPEED_ORDER:
            snapshot_entities = self.sorted_actors_by_round_speed(actors_in_stage)
        else:  # CREATION_ORDER（含未知策略回退）
            snapshot_entities = self.sorted_actors_by_creation_order(actors_in_stage)

        new_round.actor_order_snapshots.append(
            [entity.name for entity in snapshot_entities]
        )
        new_round.current_turn_actor_name = (
            snapshot_entities[0].name if snapshot_entities else None
        )
        logger.debug(f"设置当前 turn 行动角色: {new_round.current_turn_actor_name}")
        logger.info(
            f"创建第 {round_number} 回合，快照行动顺序: {new_round.actor_order_snapshots[-1]}"
        )

    ################################################################################################################
