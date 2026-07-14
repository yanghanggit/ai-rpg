"""
战斗回合过渡系统
"""

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final, override
from loguru import logger
from ..entitas import Entity, ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_alive_actors_in_stage
from ..game.dbg_entity_ops import compute_character_stats, get_energy
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
    """

    ############################################################################################################
    def __init__(
        self,
        game: DBGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.RANDOM,
    ) -> None:
        self._game: Final[DBGGame] = game
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 状态守护：战斗未进行中 / 最新回合未完成 → 静默跳过
        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过回合创建")
            return

        logger.debug("检查战斗回合状态，判断是否需要创建新回合...")

        current_rounds = self._game.current_combat_room.combat.rounds or []

        if len(current_rounds) > 0:
            last_round = self._game.current_combat_room.combat.latest_round
            assert last_round is not None, "latest_round is None"
            if not last_round.is_completed:
                return

        # 玩家角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 所有存活角色
        actors_in_stage = get_alive_actors_in_stage(self._game, player_entity)
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
        new_round = self._start_new_round(actors_in_stage)

        # 快照必须在 start_new_round 之后构建，此时 RoundStatsComponent 已按新回合重置
        if self._strategy == ActionOrderStrategy.RANDOM:
            snapshot_entities = self._shuffled_actors_by_round(actors_in_stage)
        elif self._strategy == ActionOrderStrategy.SPEED_ORDER:
            snapshot_entities = self._sorted_actors_by_round_speed(actors_in_stage)
        else:  # CREATION_ORDER（含未知策略回退）
            snapshot_entities = self._sorted_actors_by_creation_order(actors_in_stage)

        new_round.action_order = [entity.name for entity in snapshot_entities]
        new_round.current_actor = (
            snapshot_entities[0].name if snapshot_entities else None
        )
        logger.debug(f"设置当前 turn 行动角色: {new_round.current_actor}")
        logger.info(f"创建第 {round_number} 回合，行动顺序: {new_round.action_order}")

    ############################################################################################################
    def _start_new_round(self, actors: set[Entity]) -> Round:
        """创建并追加新回合，同时重置所有参战角色的 RoundStatsComponent。"""
        assert (
            self._game.current_combat_room.combat.is_ongoing
        ), "当前战斗未进行中，无法开始新回合"

        # 守卫：若当前已有回合，则必须确保上一回合已完成
        current_rounds = self._game.current_combat_room.combat.rounds or []
        if len(current_rounds) > 0:
            last_round = self._game.current_combat_room.combat.latest_round
            assert last_round is not None, "latest_round is None"
            assert last_round.is_completed, "上一回合尚未完成，无法创建新回合"

        # 创建新回合并追加到当前战斗
        new_round = Round()
        self._game.current_combat_room.combat.rounds.append(new_round)

        # 重置所有参战角色的 RoundStatsComponent
        for actor in actors:
            assert not actor.has(
                RoundStatsComponent
            ), f"{actor.name} 已存在 RoundStatsComponent"
            assert not actor.has(DeathComponent), f"{actor.name} 已死亡，不应参与新回合"
            computed = compute_character_stats(actor)
            actor.replace(RoundStatsComponent, actor.name, computed.energy)

        return new_round

    ############################################################################################################
    def _sorted_actors_by_round_speed(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并按速度降序排列。"""
        eligible: List[Entity] = [entity for entity in actors if get_energy(entity) > 0]
        eligible.sort(
            key=lambda entity: (
                -compute_character_stats(entity).speed,  # 速度降序（含装备加成）
                entity.get(IdentityComponent).creation_order,
            )
        )
        return eligible

    ############################################################################################################
    def _shuffled_actors_by_round(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并随机打乱顺序。"""
        eligible: List[Entity] = [entity for entity in actors if get_energy(entity) > 0]
        random.shuffle(eligible)
        return eligible

    ############################################################################################################
    def _sorted_actors_by_creation_order(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并按创建顺序升序排列。"""
        eligible: List[Entity] = [entity for entity in actors if get_energy(entity) > 0]
        eligible.sort(key=lambda entity: entity.get(IdentityComponent).creation_order)
        return eligible

    ################################################################################################################
